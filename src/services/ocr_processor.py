# src/services/ocr_processor.py

import os
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
from src.services import extraction_guide as _eg
from src.services import order_lookup as _ol
from rapidfuzz import fuzz as _fuzz

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    _PYZBAR_AVAILABLE = True
except ImportError:
    _PYZBAR_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = ['ReceiptFields', 'FlashExpressOCR']

_BARCODE_TRACKING_RE = re.compile(r'^FE\d{10}$')

_ANCHORS: Dict[str, List[str]] = {
    'order_id':  ['order id', 'order_id'],
    'rider_id':  ['rider', 'id:'],
    'sort_code': ['sort code', 'rts sort code'],
    'buyer':     ['buyer'],
    'weight':    ['weight'],
    'quantity':  ['quantity'],
}
_ANCHOR_THRESHOLD = 80
_FLASH_MAX_QUANTITY = 14


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
        'tracking_id': r'FE\s?\d{10}(?!\d)',
        'order_id': r'\bFE\d{6}[A-Z0-9]{6}\b',
        'rts_code': r'FEX-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2}',
        'rider_id': r'\b(?:Rider|ID):\s*([A-Z]{1,2}\d{1,2})',
        'weight': r'(\d{3,5})g',
        'quantity': r'Quantity:\s*(\d{1,3})',
        'payment_type': r'\b(COD|Paid|Prepaid|cop)\b'
    }

    def __init__(
        self,
        use_paddle_fallback: bool = False,
        confidence_threshold: float = 0.85,
        tesseract_config: str = '--oem 1 --psm 6 -l eng',
        debug_align: bool = False,
        enable_correction: bool = True,
        correction_dict_path='data/dictionaries/ground_truth_parcel_gen.json',
        use_anchor_extraction: bool = True,
        debug_ocr: bool = True

    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(f"confidence_threshold must be 0.0-1.0, got {confidence_threshold}")

        self.use_paddle_fallback: bool = use_paddle_fallback
        self.confidence_threshold: float = confidence_threshold
        self.tesseract_config: str = tesseract_config
        self.debug_align: bool = debug_align
        self.use_anchor_extraction: bool = use_anchor_extraction
        self.debug_ocr: bool = debug_ocr
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

    def process_frame(
        self,
        bgr_frame: np.ndarray,
        scan_id: Optional[int] = None
    ) -> Dict[str, Any]:
        scan_id, start_time = self._validate_and_prepare(bgr_frame, scan_id)

        barcode_tracking_id: Optional[str] = self._decode_barcode(bgr_frame)

        try:
            if self.use_anchor_extraction:
                raw_text, confidence, engine = self._run_full_image_ocr(bgr_frame)
                fields = self._extract_fields_anchor(raw_text)
            else:
                from src.services.image_utils import align_receipt
                aligned_frame, _ = align_receipt(bgr_frame, debug=self.debug_align)
                zone_results = self._process_zones(aligned_frame)
                fields = self._merge_zone_fields(zone_results)
                raw_texts: List[str] = []
                for zone_name, zone_data in zone_results.items():
                    if zone_data and 'raw_text' in zone_data:
                        raw_texts.append(f"=== {zone_name.upper()} ===")
                        raw_texts.append(zone_data['raw_text'])
                raw_text = '\n'.join(raw_texts)
                confidence = fields.get('confidence', 0.0)
                engine = 'tesseract'

            if barcode_tracking_id:
                fields['tracking_id'] = barcode_tracking_id
                logger.info(f"Barcode tracking ID used: {barcode_tracking_id}")

            if self.corrector:
                fields = self._apply_correction(fields)

            tracking_id = barcode_tracking_id or fields.get('tracking_id')
            if tracking_id:
                order = _ol.lookup_order(tracking_id)
                if order:
                    logger.info("Order found for tracking ID %s, applying lookup corrections.", tracking_id)
                    fields = self._apply_order_lookup(fields, order)

            return self._format_result(scan_id, start_time, raw_text, confidence, engine, fields)

        except Exception as e:
            logger.error(f"Primary OCR path failed: {e}")
            try:
                text, confidence, engine = self._execute_pipeline(bgr_frame)
                fields = self._extract_fields(text)
                if barcode_tracking_id:
                    fields['tracking_id'] = barcode_tracking_id
                if self.corrector:
                    fields = self._apply_correction(fields)
                tracking_id = barcode_tracking_id or fields.get('tracking_id')
                if tracking_id:
                    order = _ol.lookup_order(tracking_id)
                    if order:
                        logger.info("Order found for tracking ID %s, applying lookup corrections.", tracking_id)
                        fields = self._apply_order_lookup(fields, order)
                return self._format_result(scan_id, start_time, text, confidence, engine, fields)
            except Exception as fallback_e:
                logger.error(f"Fallback OCR also failed: {fallback_e}")
                raise RuntimeError(f"All OCR engines failed. Last error: {str(e)}")

    def _decode_barcode(self, bgr_frame: np.ndarray) -> Optional[str]:
        if not _PYZBAR_AVAILABLE:
            return None
        try:
            gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
            decoded = pyzbar_decode(gray)
            for obj in decoded:
                data = obj.data.decode('utf-8', errors='ignore').strip()
                if _BARCODE_TRACKING_RE.match(data):
                    return data
        except Exception as e:
            logger.warning(f"Barcode decode failed: {e}")
        return None

    def _isolate_receipt(self, bgr_frame: np.ndarray) -> np.ndarray:
        h, w = bgr_frame.shape[:2]
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
        _, _, v = cv2.split(hsv)
        _, bright_mask = cv2.threshold(v, 200, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        closed = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            logger.warning("No receipt contour found; using full frame")
            return bgr_frame
        min_area = (h * w) * 0.05
        valid = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not valid:
            logger.warning("No contour large enough for receipt; using full frame")
            return bgr_frame
        largest = max(valid, key=cv2.contourArea)
        x, y, rw, rh = cv2.boundingRect(largest)
        pad = 10
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w, x + rw + pad)
        y2 = min(h, y + rh + pad)
        cropped = bgr_frame[y1:y2, x1:x2]
        crop_h, crop_w = cropped.shape[:2]
        if crop_w < 100 or crop_h < 100:
            logger.warning("Isolated region too small (%dx%d); using full frame", crop_w, crop_h)
            return bgr_frame
        logger.debug("Receipt isolated: (%d,%d) %dx%d from %dx%d frame", x1, y1, crop_w, crop_h, w, h)
        return cropped

    def _run_full_image_ocr(self, bgr_frame: np.ndarray) -> Tuple[str, float, str]:
        receipt = self._isolate_receipt(bgr_frame)

        target_w = 1200
        rh, rw = receipt.shape[:2]
        if rw != target_w:
            scale = target_w / rw
            new_h = int(rh * scale)
            resized = cv2.resize(receipt, (target_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            resized = receipt

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 8
        )
        open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, open_kernel)

        debug_ts = None
        if self.debug_ocr:
            debug_dir = 'debug_ocr'
            os.makedirs(debug_dir, exist_ok=True)
            debug_ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            cv2.imwrite(os.path.join(debug_dir, f'{debug_ts}_isolated.png'), receipt)
            cv2.imwrite(os.path.join(debug_dir, f'{debug_ts}_preprocessed.png'), binary)

        config = '--oem 1 --psm 6 -l eng'
        text, confidence = self._ocr_tesseract(binary, config=config)
        engine = 'tesseract'

        if self.debug_ocr and debug_ts:
            with open(os.path.join('debug_ocr', f'{debug_ts}_raw_text.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
            logger.debug("Debug OCR artifacts saved: debug_ocr/%s_*", debug_ts)

        if confidence < self.confidence_threshold and self.use_paddle_fallback:
            logger.info("Low conf (%.2f). Fallback to Paddle.", confidence)
            text, confidence = self._ocr_paddle(binary)
            engine = 'paddle'

        return text, confidence, engine

    @staticmethod
    def _match_anchor(line: str, targets: List[str], threshold: int = _ANCHOR_THRESHOLD) -> bool:
        clean = re.sub(r'[^\w\s]', '', line).lower().strip()
        if len(clean) < 3:
            return False
        shortest_target = min(len(t) for t in targets)
        if len(clean) > shortest_target * 6:
            return False
        for target in targets:
            if _fuzz.partial_ratio(clean, target) >= threshold:
                return True
        return False

    def _extract_fields_anchor(self, ocr_text: str) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            'tracking_id': None,
            'order_id': None,
            'rts_code': None,
            'rider_id': None,
            'buyer_name': None,
            'buyer_address': None,
            'weight_g': None,
            'quantity': None,
            'payment_type': None,
            'scan_datetime': None,
            'processing_time_ms': None,
            'confidence': 0.0,
            'timestamp': ''
        }

        lines = [line.rstrip() for line in ocr_text.split('\n')]
        n = len(lines)

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            if self._match_anchor(lower, _ANCHORS['order_id']):
                m = re.search(r'\bFE\d{6}[A-Z0-9]{6}\b', stripped, re.IGNORECASE)
                if m:
                    candidate = m.group(0).upper()
                    fixed, ok = _eg.validate_and_fix_field(candidate, 'orderId')
                    fields['order_id'] = fixed if ok else candidate
                elif i + 1 < n:
                    next_s = lines[i + 1].strip()
                    m2 = re.search(r'\bFE\d{6}[A-Z0-9]{6}\b', next_s, re.IGNORECASE)
                    if m2:
                        candidate = m2.group(0).upper()
                        fixed, ok = _eg.validate_and_fix_field(candidate, 'orderId')
                        fields['order_id'] = fixed if ok else candidate

            elif self._match_anchor(lower, _ANCHORS['rider_id']):
                m = re.search(r'([A-Z]{1,2}\d{1,2})(?:[^\w]|$)', stripped, re.IGNORECASE)
                if m:
                    raw_code = m.group(1).upper()
                    corrected = _eg.validate_code(raw_code, 'rider')
                    fields['rider_id'] = corrected if corrected else raw_code

            elif self._match_anchor(lower, _ANCHORS['sort_code']):
                m = re.search(r'(FE?X-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2})', stripped, re.IGNORECASE)
                if m:
                    code = m.group(1)
                    if not code.upper().startswith('FEX'):
                        code = 'F' + code
                    corrected = _eg.validate_code(code.upper(), 'sort')
                    fields['rts_code'] = corrected if corrected else code.upper()
                elif i + 1 < n:
                    next_s = lines[i + 1].strip()
                    m2 = re.search(r'(FE?X-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2})', next_s, re.IGNORECASE)
                    if m2:
                        code2 = m2.group(1)
                        if not code2.upper().startswith('FEX'):
                            code2 = 'F' + code2
                        corrected2 = _eg.validate_code(code2.upper(), 'sort')
                        fields['rts_code'] = corrected2 if corrected2 else code2.upper()

            elif self._match_anchor(lower, _ANCHORS['buyer']):
                buyer_name, buyer_address = self._parse_buyer_block(lines, i + 1)
                if buyer_name:
                    fields['buyer_name'] = buyer_name
                if buyer_address:
                    fields['buyer_address'] = buyer_address

            elif self._match_anchor(lower, _ANCHORS['weight']):
                nums = re.findall(r'\d+', stripped)
                for num_str in nums:
                    val = int(num_str)
                    if 100 <= val <= 7000:
                        fields['weight_g'] = val
                        break

            elif self._match_anchor(lower, _ANCHORS['quantity']):
                nums = re.findall(r'\d+', stripped)
                for num_str in nums:
                    val = int(num_str)
                    if 1 <= val <= _FLASH_MAX_QUANTITY:
                        fields['quantity'] = val
                        break

        if not fields.get('buyer_name'):
            _name_re = re.compile(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b')
            _name_stop = re.compile(
                r'\b(?:district|zip|province|seller|flash|delivery|attempt|return|street|city|brgy|barangay|sort|rider|order|weight|quantity)\b',
                re.IGNORECASE
            )
            for line in lines:
                s = line.strip()
                if len(s) < 10 or re.search(r'\d', s) or _name_stop.search(s):
                    continue
                upper_ratio = sum(1 for c in s if c.isupper()) / len(s) if s else 0
                if upper_ratio > 0.5:
                    continue
                m = _name_re.search(s)
                if m and self._validate_buyer_name(m.group(1)):
                    candidate_name = m.group(1)
                    if _eg.score_name_line(candidate_name) >= 0.5:
                        fields['buyer_name'] = candidate_name
                        break

        if fields.get('weight_g') is not None:
            corrected_qty, was_inconsistent = _eg.cross_validate_weight_quantity(
                fields['weight_g'], fields.get('quantity')
            )
            if was_inconsistent:
                logger.debug(
                    "Weight-quantity cross-validation corrected: weight=%s, quantity=%s -> %s",
                    fields['weight_g'], fields.get('quantity'), corrected_qty
                )
            fields['quantity'] = corrected_qty

        fields = self._apply_regex_fallbacks(ocr_text, fields)
        self._convert_field_types(fields)
        return fields

    def _parse_buyer_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[str], Optional[str]]:
        name_pattern = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$')
        cap_pattern = re.compile(r'^(?:[A-Z][a-zA-Z]*\s+){1,3}[A-Z][a-zA-Z]*$')
        stop_keywords = re.compile(
            r'\b(?:district|zip|province|seller|flash express|gaya-gaya|buyer|cod|paid|prepaid)\b',
            re.IGNORECASE
        )
        buyer_name: Optional[str] = None
        name_idx = -1

        for i in range(start_idx, min(start_idx + 5, len(lines))):
            s = lines[i].strip()
            if not s or stop_keywords.search(s):
                continue
            if re.search(r'\d', s):
                continue
            if name_pattern.match(s) or cap_pattern.match(s):
                buyer_name = s
                name_idx = i
                break

        if buyer_name is None:
            return None, None

        address_lines: List[str] = []
        stop_at = re.compile(
            r'\b(?:district|city|province|zip|seller|flash express|gaya-gaya)\b',
            re.IGNORECASE
        )
        for i in range(name_idx + 1, len(lines)):
            s = lines[i].strip()
            if not s:
                break
            if stop_at.search(s):
                break
            if _eg.score_address_line(s) >= 0.15 or re.search(r'\b\d{4}\b', s) or re.search(r'brgy', s, re.IGNORECASE):
                address_lines.append(s)

        address = ', '.join(address_lines) if address_lines else None
        return buyer_name, address

    def _apply_regex_fallbacks(self, text: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        if not fields.get('tracking_id'):
            m = re.search(r'FE\s?\d{10}(?!\d)', text, re.IGNORECASE)
            if m:
                candidate = m.group(0).replace(' ', '')
                fixed, ok = _eg.validate_and_fix_field(candidate, 'trackingNumber')
                fields['tracking_id'] = fixed if ok else candidate

        if not fields.get('order_id'):
            m = re.search(r'\bFE\d{6}[A-Z0-9]{6}\b', text, re.IGNORECASE)
            if m:
                fields['order_id'] = m.group(0).upper()

        if not fields.get('rts_code'):
            m = re.search(
                r'FEX-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2}',
                text, re.IGNORECASE
            )
            if m:
                fields['rts_code'] = m.group(0)
            else:
                m2 = re.search(
                    r':EX-[A-Z]{3,4}-[A-Z]{2,4}-[A-Z0-9]{3,5}-[A-Z]{1,2}\d{2}',
                    text, re.IGNORECASE
                )
                if m2:
                    fields['rts_code'] = 'F' + m2.group(0)[1:]

        if not fields.get('rider_id'):
            m = re.search(r'(?:Rider:|ID:)\s*([A-Z]{1,2}\d{1,2})', text, re.IGNORECASE)
            if m:
                fields['rider_id'] = m.group(1).upper()

        if not fields.get('payment_type'):
            m = re.search(r'\b(COD|Paid|Prepaid|cop)\b', text, re.IGNORECASE)
            if m:
                raw_payment = m.group(1)
                fields['payment_type'] = 'COD' if raw_payment.lower() == 'cop' else raw_payment

        if not fields.get('buyer_name'):
            fields['buyer_name'] = self._parse_buyer_name(text)

        if not fields.get('buyer_address'):
            fields['buyer_address'] = self._parse_philippine_address(text)

        return fields

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
        if fields.get('payment_type', '').lower() == 'cop':
            fields['payment_type'] = 'COD'
        return fields

    def _apply_order_lookup(self, fields: Dict[str, Any], order: Dict[str, Any]) -> Dict[str, Any]:
        if not fields.get('buyer_name') or _eg.score_name_line(fields['buyer_name']) < 0.8:
            fields['buyer_name'] = order.get('buyer_name')

        gt_address = order.get('address')
        if gt_address:
            fields['buyer_address'] = gt_address

        weight_raw = order.get('weight', '')
        if isinstance(weight_raw, str):
            weight_raw = weight_raw.replace('g', '').strip()
        try:
            fields['weight_g'] = int(weight_raw)
        except (ValueError, TypeError):
            pass

        try:
            fields['quantity'] = int(order.get('quantity', ''))
        except (ValueError, TypeError):
            pass

        if not fields.get('order_id'):
            fields['order_id'] = order.get('order_id')

        if not fields.get('rts_code'):
            fields['rts_code'] = order.get('rts_code')

        if not fields.get('rider_id'):
            fields['rider_id'] = order.get('rider')

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
        blurred = cv2.GaussianBlur(cleaned, (3, 3), 0)
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        h, w = binary.shape
        binary[int(h * 0.75):, int(w * 0.35):int(w * 0.65)] = 255
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

    def _convert_field_types(self, fields: Dict[str, Any]) -> None:
        if fields.get('weight'):
            try:
                w_str = str(fields['weight']).replace('g', '')
                w_val = int(w_str)
                fields['weight_g'] = w_val if 100 <= w_val <= 7000 else None
            except ValueError:
                fields['weight_g'] = None
            fields.pop('weight', None)
        if fields.get('quantity'):
            try:
                q_val = int(fields['quantity'])
                fields['quantity'] = q_val if 1 <= q_val <= _FLASH_MAX_QUANTITY else None
            except ValueError:
                fields['quantity'] = None

    def _extract_special_fields(self, text: str, fields: Dict[str, Any]) -> None:
        fields['buyer_name'] = self._parse_buyer_name(text)
        fields['buyer_address'] = self._parse_philippine_address(text)

    def _parse_buyer_name(self, text: str) -> Optional[str]:
        buyer_pattern = r'BUYER\s*\n([A-Z][a-z]+ [A-Z][a-z]+)'
        match = re.search(buyer_pattern, text)
        return match.group(1) if match else None

    def _parse_philippine_address(self, text: str) -> Optional[str]:
        pattern = (
            r'(\d+[\w ]+(?:St(?:reet)?|Rd\.?|Road|Highway|Hwy|Ave(?:nue)?|Blvd\.?)[,\n ]*'
            r'Brgy\.\s*[\w ()]+'
            r'(?:[,\n ]+[\w ]+){1,4}'
            r'\s+\d{4})'
        )
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        lines = [line.strip() for line in text.split('\n')]
        brgy_keywords = ['brgy', 'barangay']
        for i, line in enumerate(lines):
            if not any(k in line.lower() for k in brgy_keywords):
                continue
            window_start = max(0, i - 1)
            window_end = min(i + 4, len(lines))
            window = lines[window_start:window_end]
            window_text = ' '.join(window)
            if not re.search(r'\b\d{4}\b', window_text):
                continue
            parts = []
            for l in window:
                if not l:
                    continue
                if re.match(r'^(FE|FEX|Rider|ID:|Sort|Order|Quantity|Weight|Payment)', l, re.IGNORECASE):
                    continue
                if re.search(r'\b(PDG|BUYER|SELLER)\b', l, re.IGNORECASE):
                    continue
                if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', l) and not re.search(r'\d', l):
                    continue
                alnum = sum(c.isalnum() or c in ' ,.-' for c in l)
                if len(l) > 0 and alnum / len(l) < 0.60:
                    continue
                parts.append(l)
            if len(parts) >= 2:
                return ', '.join(parts)
        return None

    def _process_zones(self, bgr_frame: np.ndarray) -> Dict[str, Dict[str, Any]]:
        H, W = bgr_frame.shape[:2]
        zones: Dict[str, Dict[str, Any]] = {}
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

    def _process_zone_header(self, bgr_frame: np.ndarray, H: int, W: int) -> Dict[str, Any]:
        y1, y2 = 0, int(H * 0.45)
        region = bgr_frame[y1:y2, :]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text, conf = self._ocr_tesseract(binary)
        tracking_pattern = r'FE\s*\d{10}(?!\d)'
        match = re.search(tracking_pattern, text)
        tracking_id = match.group(0).replace(' ', '') if match else None
        fields: Dict[str, Any] = {
            'tracking_id': tracking_id,
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
        buyer_name: Optional[str] = None
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
        address_lines: List[str] = []
        template_keywords = ['district', 'street', 'city', 'province', 'zip code', 'seller', 'flash express', 'gaya-gaya']
        for line in lines[name_index + 1:]:
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
        fields: Dict[str, Any] = {'weight_g': None, 'quantity': None}
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
        if not all(len(w) >= 4 for w in words):
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
        fields: Dict[str, Any] = {
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

    def _clean_address(self, address: str) -> str:
        if not address:
            return address
        address = re.sub(r'^[^\w\d]+', '', address)
        address = re.sub(r'[^\w\d]+$', '', address)
        address = re.sub(r'\bmi\s+(\d{4})\b', r'\1', address)
        address = re.sub(r'\s+', ' ', address)
        return address.strip()