# src/services/ocr_processor.py (modified)

"""Flash Express OCR Processor."""
import os
from src.services.image_utils import align_receipt
import threading
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List, Any, ClassVar
from dataclasses import dataclass
import cv2
import numpy as np
import pytesseract
import re

from src.services.ocr_correction import FlashExpressCorrector

logger = logging.getLogger(__name__)

__all__ = ['ReceiptFields', 'FlashExpressOCR']


@dataclass
class ReceiptFields:
    tracking_id: Optional[str] = None
    order_id: Optional[str] = None
    rts_code: Optional[str] = None
    rider_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    weight_g: Optional[int] = None
    quantity: Optional[int] = None
    payment_type: Optional[str] = None
    scan_datetime: Optional[str] = None
    processing_time_ms: Optional[int] = None
    confidence: float = 0.0
    timestamp: str = ""


class FlashExpressOCR:
    PATTERNS: ClassVar[Dict[str, str]] = {
        'tracking_id': r'FE\s?\d{10}',
        'order_id': r'FE\d{8}J\d{5}',
        'rts_code': r'FEX-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2}', 
        'rider_id': r'Rider:\s*([A-Z]{1,2}\d{1,2})',
        'weight': r'(\d{3,5})g',
        'quantity': r'Quantity:\s*(\d{1,3})',
        'payment_type': r'\b(COD|Paid|Prepaid)\b'
    }

    def __init__(
        self,
        use_paddle_fallback: bool = False,
        confidence_threshold: float = 0.85,
        tesseract_config: str = '--oem 1 --psm 6 -l eng',
        debug_align: bool = False,
        enable_correction: bool = False,
        correction_dict_path: Optional[str] = None
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(f"confidence_threshold must be 0.0-1.0, got {confidence_threshold}")
        
        self.use_paddle_fallback: bool = use_paddle_fallback
        self.confidence_threshold: float = confidence_threshold
        self.tesseract_config: str = tesseract_config
        self.debug_align: bool = debug_align
        self._lock: threading.Lock = threading.Lock()
        self.corrector: Optional[FlashExpressCorrector] = None
        if enable_correction:
            if correction_dict_path is None:
                raise ValueError("correction_dict_path required when enable_correction=True")
            self.corrector = FlashExpressCorrector(correction_dict_path)
        
        if use_paddle_fallback:
            try:
                from paddleocr import PaddleOCR
                self.paddle_ocr: Any = None
                self._paddle_ocr_class = PaddleOCR
            except ImportError:
                raise ImportError("PaddleOCR requested but not installed.")

    def _align_receipt_internal(self, frame: np.ndarray) -> np.ndarray:
        aligned_frame, success = align_receipt(frame)
        if self.debug_align:
            debug_dir = "debug_alignment"
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_original.jpg"), frame)
            cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_aligned.jpg"), aligned_frame)
            logger.info(f"Alignment {'successful' if success else 'failed'} - saved debug images")
        if success:
            logger.info("Receipt alignment successful")
        else:
            logger.warning("Receipt alignment failed - using original frame")
        return aligned_frame
        
    def _clean_address(self, address: str) -> str:
        if not address:
            return address
        address = re.sub(r'^[^\w\d]+', '', address)
        address = re.sub(r'[^\w\d]+$', '', address)
        address = re.sub(r'\bmi\s+(\d{4})\b', r'\1', address)
        address = re.sub(r'\s+', ' ', address)
        return address.strip()

    def process_frame(
        self,
        bgr_frame: np.ndarray,
        scan_id: Optional[int] = None
    ) -> Dict[str, Any]:
        scan_id, start_time = self._validate_and_prepare(bgr_frame, scan_id)
        try:
            aligned_frame = self._align_receipt_internal(bgr_frame)
            zone_results = self._process_zones(aligned_frame)
            fields = self._merge_zone_fields(zone_results)
            raw_texts = []
            for zone_name, zone_data in zone_results.items():
                if zone_data and 'raw_text' in zone_data:
                    raw_texts.append(f"=== {zone_name.upper()} ===")
                    raw_texts.append(zone_data['raw_text'])
            raw_text = '\n'.join(raw_texts)
            engine = 'tesseract'
            if self.corrector:
                fields = self._apply_correction(fields)
            return self._format_result(
                scan_id, 
                start_time, 
                raw_text, 
                fields['confidence'], 
                engine,
                fields
            )
        except Exception as e:
            logger.error(f"Zonal OCR failed: {e}")
            try:
                text, confidence, engine = self._execute_pipeline(bgr_frame)
                fields = self._extract_fields(text)
                if self.corrector:
                    fields = self._apply_correction(fields)
                return self._format_result(scan_id, start_time, text, confidence, engine, fields)
            except Exception as fallback_e:
                logger.error(f"Fallback OCR also failed: {fallback_e}")
                raise RuntimeError(f"All OCR engines failed. Last error: {str(e)}")

    def _apply_correction(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        if not self.corrector:
            return fields
        corr = self.corrector
        if fields.get('buyer_address'):
            fields['buyer_address'] = corr.clean_address(fields['buyer_address'])
        if fields.get('barangay'):
            fields['barangay'] = corr.correct_barangay(fields['barangay'])
        if fields.get('district') and fields.get('barangay'):
            fields['district'] = corr.correct_district(fields['barangay'], fields['district'])
        if fields.get('tracking_id'):
            valid, corrected = corr.validate_tracking_number(fields['tracking_id'])
            if valid:
                fields['tracking_id'] = corrected
            else:
                logger.warning(f"Tracking number validation failed: {fields['tracking_id']}")
        if fields.get('ph_number'):
            valid, corrected = corr.validate_phone(fields['ph_number'])
            if valid:
                fields['ph_number'] = corrected
        if fields.get('rider_id'):
            fields['rider_id'] = corr.correct_rider_code(fields['rider_id'])
        if fields.get('rts_code'):
            fields['rts_code'] = corr.correct_sort_code(fields['rts_code'])
        if fields.get('weight_g') is not None and fields.get('quantity') is None:
            fields['quantity'] = corr.derive_quantity_from_weight(fields['weight_g'])
        return fields

    def _validate_and_prepare(
        self, 
        bgr_frame: np.ndarray, 
        scan_id: Optional[int]
    ) -> Tuple[int, int]:
        if not isinstance(bgr_frame, np.ndarray):
            raise TypeError("bgr_frame must be numpy.ndarray")
        if bgr_frame.ndim != 3 or bgr_frame.shape[2] != 3:
            raise ValueError(f"Expected BGR frame (H, W, 3), got {bgr_frame.shape}")
        if bgr_frame.dtype != np.uint8:
            raise ValueError(f"Expected uint8 array, got {bgr_frame.dtype}")
        final_scan_id = scan_id if scan_id is not None else self._generate_scan_id()
        return final_scan_id, cv2.getTickCount()

    def _execute_pipeline(self, frame: np.ndarray) -> Tuple[str, float, str]:
        processed = self._preprocess_thermal_receipt(frame)
        text, confidence = self._ocr_tesseract(processed)
        engine = 'tesseract'
        if confidence < self.confidence_threshold and self.use_paddle_fallback:
            logger.info("Low conf (%.2f). Fallback to Paddle.", confidence)
            text, confidence = self._ocr_paddle(processed)
            engine = 'paddle'
        return text, confidence, engine

    def _format_result(
        self,
        scan_id: int,
        start_time: int,
        text: str,
        confidence: float,
        engine: str,
        fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if fields is None:
            fields = self._extract_fields(text)
        fields['confidence'] = confidence
        fields['timestamp'] = datetime.now(timezone.utc).isoformat()
        freq = cv2.getTickFrequency()
        duration_ms = int((cv2.getTickCount() - start_time) * 1000 / freq)
        fields['processing_time_ms'] = duration_ms
        fields['scan_datetime'] = fields['timestamp']
        return {
            'success': True,
            'scan_id': scan_id,
            'fields': fields,
            'raw_text': text,
            'engine': engine,
            'processing_time_ms': duration_ms
        }

    def _generate_scan_id(self) -> int:
        return int(datetime.now().timestamp() * 1000000)

    def _preprocess_thermal_receipt(self, bgr_frame: np.ndarray) -> np.ndarray:
        if bgr_frame.shape[1] > 800:
            scale = 800.0 / bgr_frame.shape[1]
            height = int(bgr_frame.shape[0] * scale)
            resized = cv2.resize(bgr_frame, (800, height), interpolation=cv2.INTER_LANCZOS4)
        else:
            resized = bgr_frame
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([10, 100, 100]), np.array([25, 255, 255]))
        cleaned = cv2.inpaint(gray, mask, 3, cv2.INPAINT_TELEA)
        denoised = cv2.fastNlMeansDenoising(cleaned, None, 10, 7, 21)
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        h, w = binary.shape
        binary[int(h*0.75):, int(w*0.35):int(w*0.65)] = 255
        return binary

    def _ocr_tesseract(self, image: np.ndarray, config: Optional[str] = None) -> Tuple[str, float]:
        if config is None:
            config = self.tesseract_config
        data = pytesseract.image_to_data(
            image, config=config, output_type=pytesseract.Output.DICT
        )
        confs = [c for c in data['conf'] if c > 0]
        avg = sum(confs) / len(confs) if confs else 0.0
        text = pytesseract.image_to_string(image, config=config)
        return text, avg / 100.0

    def _ocr_paddle(self, image: np.ndarray) -> Tuple[str, float]:
        if not hasattr(self, 'paddle_ocr') or self.paddle_ocr is None:
            self.paddle_ocr = self._paddle_ocr_class(
                use_angle_cls=True, lang='en', show_log=False, use_gpu=False
            )
        result = self.paddle_ocr.ocr(image, cls=True)
        if not result or not result[0]:
            return "", 0.0
        texts = [line[1][0] for line in result[0]]
        confs = [line[1][1] for line in result[0]]
        avg = sum(confs) / len(confs) if confs else 0.0
        return "\n".join(texts), avg

    def _extract_fields(self, ocr_text: str) -> Dict[str, Any]:
        fields = self._extract_regex_fields(ocr_text)
        self._extract_special_fields(ocr_text, fields)
        self._convert_field_types(fields)
        return fields

    def _extract_regex_fields(self, text: str) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            'tracking_id': None, 'order_id': None, 'rts_code': None,
            'rider_id': None, 'buyer_name': None, 'buyer_address': None,
            'weight_g': None, 'quantity': None, 'payment_type': None,
            'scan_datetime': None, 'processing_time_ms': None,
            'confidence': 0.0, 'timestamp': ""
        }
        for field_name, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                val = matches[0][0] if isinstance(matches[0], tuple) else matches[0]
                fields[field_name] = str(val).strip()
        return fields

    def _extract_special_fields(self, text: str, fields: Dict[str, Any]) -> None:
        fields['buyer_name'] = self._parse_buyer_name(text)
        fields['buyer_address'] = self._parse_philippine_address(text)

    def _convert_field_types(self, fields: Dict[str, Any]) -> None:
        if fields.get('weight'):
            try:
                w_str = str(fields['weight']).replace('g', '')
                fields['weight_g'] = int(w_str)
            except ValueError:
                fields['weight_g'] = None
            fields.pop('weight', None)
        if fields.get('quantity'):
            try:
                fields['quantity'] = int(fields['quantity'])
            except ValueError:
                fields['quantity'] = None

    def _parse_buyer_name(self, text: str) -> Optional[str]:
        buyer_pattern = r'BUYER\s*\n([A-Z][a-z]+ [A-Z][a-z]+)'
        match = re.search(buyer_pattern, text)
        return match.group(1) if match else None

    def _parse_philippine_address(self, text: str) -> Optional[str]:
        pattern = r'(\d+[\w\s]+St(?:reet)?,?\s+Brgy\.[\w\s]+,?\s+[\w\s]+,?\s+[\w\s]+\s+\d{4})'
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            lines = [line.strip() for line in text.split('\n')]
            keywords = ['brgy', 'barangay', 'city', 'province']
            for i, line in enumerate(lines):
                if any(k in line.lower() for k in keywords):
                    parts = []
                    for j in range(max(0, i - 1), min(i + 3, len(lines))):
                        if lines[j] and not lines[j].startswith(('FE', 'FEX', 'Rider')):
                            parts.append(lines[j])
                    if len(parts) >= 2:
                        return ', '.join(parts)
        return match.group(1) if match else None

    def _process_zones(self, bgr_frame: np.ndarray) -> Dict[str, Dict[str, Any]]:
        H, W = bgr_frame.shape[:2]
        zones = {}
        try:
            zones['header'] = self._process_zone_header(bgr_frame, H, W)
        except Exception as e:
            logger.error(f"Zone 1 (header) failed: {e}")
            zones['header'] = {}
        try:
            zones['buyer'] = self._process_zone_buyer(bgr_frame, H, W)
        except Exception as e:
            logger.error(f"Zone 3 (buyer) failed: {e}")
            zones['buyer'] = {}
        try:
            zones['footer'] = self._process_zone_footer(bgr_frame, H, W)
        except Exception as e:
            logger.error(f"Zone 5 (footer) failed: {e}")
            zones['footer'] = {}
        return zones

    def _process_zone_header(self, bgr_frame, H, W):
        y1, y2 = 0, int(H * 0.45)
        region = bgr_frame[y1:y2, :]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text, conf = self._ocr_tesseract(binary)
        tracking_pattern = r'FE\s*\d{10}'
        match = re.search(tracking_pattern, text)
        tracking_id = match.group(0).replace(' ', '') if match else None
        fields = {
            'tracking_id': None,
            'order_id': None,
            'rts_code': None,
            'rider_id': None,
            'confidence': conf,
            'raw_text': text
        }
        for field_name, pattern in self.PATTERNS.items():
            if field_name in ['tracking_id', 'order_id', 'rts_code', 'rider_id']:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    val = matches[0][0] if isinstance(matches[0], tuple) else matches[0]
                    fields[field_name] = str(val).strip()
        print(f"[HEADER RAW] {text}")
        return fields

    def _process_zone_buyer(
        self, 
        bgr_frame: np.ndarray, 
        H: int, 
        W: int
    ) -> Dict[str, Any]:
        y1, y2 = int(H * 0.40), int(H * 0.58)
        x1, x2 = 150, int(W * 0.95)
        region = bgr_frame[y1:y2, x1:x2]
        processed = self._preprocess_buyer_zone(region)
        config = '--oem 1 --psm 6 -l eng'
        text, conf = self._ocr_tesseract(processed, config=config)
        buyer_name, buyer_address = self._extract_buyer_info(text)
        return {
            'buyer_name': buyer_name,
            'buyer_address': buyer_address,
            'confidence': conf,
            'raw_text': text
        }

    def _preprocess_buyer_zone(self, region: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def _extract_buyer_info(self, ocr_text: str) -> Tuple[Optional[str], Optional[str]]:
        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
        if not lines:
            return None, None
        name_pattern = re.compile(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b')
        buyer_name = None
        name_index = -1
        for i, line in enumerate(lines):
            match = name_pattern.search(line)
            if match:
                buyer_name = match.group(1)
                name_index = i
                break
        if not buyer_name:
            for i, line in enumerate(lines):
                if len(line) < 5:
                    continue
                if re.search(r'\d', line):
                    continue
                if re.search(r'(district|city|zip|province|street|buyer|seller|flash express)', line.lower()):
                    continue
                words = line.split()
                capitalized_words = [w for w in words if w and w[0].isupper()]
                if len(capitalized_words) >= 2 and len(words) <= 4:
                    buyer_name = line
                    name_index = i
                    break
        if not buyer_name:
            return None, None
        buyer_name = re.sub(r'\s+(PDG|COD|Paid|Prepaid)$', '', buyer_name, flags=re.IGNORECASE)
        buyer_name = buyer_name.replace('|', 'I').replace('0', 'O')
        address_lines = []
        template_keywords = ['district', 'street', 'city', 'province', 'zip code', 'seller', 'flash express', 'gaya-gaya']
        for line in lines[name_index+1:]:
            line_lower = line.lower()
            if any(kw in line_lower for kw in template_keywords):
                break
            if line_lower in ['buyer', 'seller', 'pdg', 'cod']:
                continue
            address_lines.append(line)
        address = ', '.join(address_lines) if address_lines else None
        return buyer_name, address

    def _process_zone_footer(
        self, 
        bgr_frame: np.ndarray, 
        H: int, 
        W: int
    ) -> Dict[str, Any]:
        y1, y2 = int(H * 0.70), int(H * 0.85)
        x1, x2 = 0, int(W * 0.45)
        region = bgr_frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        config = '--oem 1 --psm 11 -l eng'
        text, conf = self._ocr_tesseract(processed, config=config)
        fields = self._extract_footer_fields(text)
        fields['confidence'] = conf
        fields['raw_text'] = text
        return fields

    def _extract_footer_fields(self, ocr_text: str) -> Dict[str, Any]:
        fields = {'weight_g': None, 'quantity': None}
        weight_match = re.search(r'(\d{3,5})\s*g', ocr_text, re.IGNORECASE)
        if weight_match:
            try:
                fields['weight_g'] = int(weight_match.group(1))
            except ValueError:
                pass
        qty_match = re.search(r'quantity:\s*(\d{1,3})', ocr_text, re.IGNORECASE)
        if qty_match:
            try:
                fields['quantity'] = int(qty_match.group(1))
            except ValueError:
                pass
        return fields

    def _validate_buyer_name(self, name: Optional[str]) -> bool:
        if not name:
            return False
        words = name.split()
        if not (2 <= len(words) <= 4):
            return False
        if not all(w[0].isupper() for w in words if w):
            return False
        if any(char.isdigit() for char in name):
            return False
        artifacts = ['|', '_', '~', '^']
        if any(art in name for art in artifacts):
            return False
        return True

    def _validate_address(self, address: Optional[str]) -> bool:
        if not address or len(address) < 20:
            return False
        if not re.search(r'brgy|barangay', address, re.IGNORECASE):
            return False
        if not re.search(r'san jose del monte|sjdm', address, re.IGNORECASE):
            return False
        if not re.search(r'\b302[0-9]\b', address):
            return False
        bad_keywords = ['district', 'zip code']
        if any(kw in address.lower() for kw in bad_keywords):
            return False
        return True

    def _merge_zone_fields(self, zone_results: Dict[str, Dict]) -> Dict[str, Any]:
        fields = {
            'tracking_id': None,
            'order_id': None,
            'rts_code': None,
            'rider_id': None,
            'buyer_name': None,
            'buyer_address': None,
            'weight_g': None,
            'quantity': None,
            'payment_type': None,
            'confidence': 0.0
        }
        if 'header' in zone_results:
            header = zone_results['header']
            fields['tracking_id'] = header.get('tracking_id')
            fields['order_id'] = header.get('order_id')
            fields['rts_code'] = header.get('rts_code')
            fields['rider_id'] = header.get('rider_id')
        if 'buyer' in zone_results:
            buyer = zone_results['buyer']
            name = buyer.get('buyer_name')
            if self._validate_buyer_name(name):
                fields['buyer_name'] = name
            else:
                logger.warning(f"Buyer name validation failed: {name}")
            address = buyer.get('buyer_address')
            if self._validate_address(address):
                fields['buyer_address'] = address
            else:
                logger.warning(f"Address validation failed: {address}")
        if 'footer' in zone_results:
            footer = zone_results['footer']
            fields['weight_g'] = footer.get('weight_g')
            fields['quantity'] = footer.get('quantity')
        confidences = []
        for zone in zone_results.values():
            if zone and 'confidence' in zone:
                confidences.append(zone['confidence'])
        fields['confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
        return fields

# (debug_zone_preprocessing function omitted for brevity, can be kept as is)