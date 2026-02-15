"""Flash Express OCR Processor - FIXED VERSION.
This module provides specialized OCR for Flash Express thermal receipts.

KEY FIXES:
1. Extended header zone from 15% to 40% to capture tracking ID on all images
2. Improved address cleaning to remove leading/trailing artifacts
3. Better OCR config for header zone (psm 6 instead of 11)
4. Enhanced validation and pattern matching
"""
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

logger = logging.getLogger(__name__)

__all__ = ['ReceiptFields', 'FlashExpressOCR']


@dataclass
class ReceiptFields:
    """Data structure representing fields extracted from a receipt."""
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
    """OCR processor specifically tuned for Flash Express thermal receipts."""
    PATTERNS: ClassVar[Dict[str, str]] = {
        'tracking_id': r'FE\s?\d{10}',  # allow optional space
        'order_id': r'FE\d{8}[A-Z]\w+',  # More flexible order ID
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
        debug_align: bool = False
    ) -> None:
        """Initialize the OCR processor."""
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(f"confidence_threshold must be 0.0-1.0, got {confidence_threshold}")
        
        self.use_paddle_fallback: bool = use_paddle_fallback
        self.confidence_threshold: float = confidence_threshold
        self.tesseract_config: str = tesseract_config
        self.debug_align: bool = debug_align
        self._lock: threading.Lock = threading.Lock()
        
        if use_paddle_fallback:
            try:
                from paddleocr import PaddleOCR
                self.paddle_ocr: Any = None
                self._paddle_ocr_class = PaddleOCR
            except ImportError:
                raise ImportError("PaddleOCR requested but not installed.")

    def _align_receipt_internal(self, frame: np.ndarray) -> np.ndarray:
        """Align receipt using perspective transformation.
        
        Args:
            frame: Original BGR frame
            
        Returns:
            Aligned frame (or original if alignment failed)
        """
        # Import from the fixed module
        try:
            from image_utils_fixed import align_receipt
        except ImportError:
            # Fallback to original if fixed version not available
            try:
                from src.services.image_utils import align_receipt
            except ImportError:
                logger.warning("No alignment module available")
                return frame
        
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
        """Remove leading/trailing artifacts and fix common OCR errors.
        
        IMPROVED: Better handling of OCR artifacts.
        """
        if not address:
            return address
        
        # Remove standalone numbers/symbols at start (e.g., ") 1," or "i 13")
        address = re.sub(r'^[\)\]\}\|]{0,2}\s*\d{1,2}\s*[,\s]+', '', address)
        
        # Remove leading single letters followed by space (e.g., "i ")
        address = re.sub(r'^[a-z]\s+', '', address)
        
        # Remove other leading non-alphanumeric (except numbers that are part of address)
        address = re.sub(r'^[^\w\d]+', '', address)
        
        # Remove trailing non-alphanumeric and stray text after postal code
        # Match postal code and remove everything after it except spaces/alphanumeric
        address = re.sub(r'(\d{4})([^\w\s].*)?$', r'\1', address)
        
        # Replace stray "mi" or "iy" before postal code
        address = re.sub(r'\b(mi|iy)\s+(\d{4})\b', r'\2', address)
        
        # Replace multiple spaces
        address = re.sub(r'\s+', ' ', address)
        
        # Final trim
        return address.strip()

    def process_frame(
        self,
        bgr_frame: np.ndarray,
        scan_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process camera frame using zonal OCR approach with deskewing."""
        scan_id, start_time = self._validate_and_prepare(bgr_frame, scan_id)
        
        try:
            # Apply receipt alignment before processing
            aligned_frame = self._align_receipt_internal(bgr_frame)
            
            # Multi-zone processing on aligned frame
            zone_results = self._process_zones(aligned_frame)
            
            # Merge zone results
            fields = self._merge_zone_fields(zone_results)
            
            # Get raw text from zones (for debugging)
            raw_texts = []
            for zone_name, zone_data in zone_results.items():
                if zone_data and 'raw_text' in zone_data:
                    raw_texts.append(f"=== {zone_name.upper()} ===")
                    raw_texts.append(zone_data['raw_text'])
            
            raw_text = '\n'.join(raw_texts)
            
            # Get primary engine used
            engine = 'tesseract'
            
            # Format result
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
            # Fallback to full-page OCR
            try:
                text, confidence, engine = self._execute_pipeline(bgr_frame)
                return self._format_result(scan_id, start_time, text, confidence, engine)
            except Exception as fallback_e:
                logger.error(f"Fallback OCR also failed: {fallback_e}")
                raise RuntimeError(f"All OCR engines failed. Last error: {str(e)}")

    def _validate_and_prepare(
        self, 
        bgr_frame: np.ndarray, 
        scan_id: Optional[int]
    ) -> Tuple[int, int]:
        """Validate input frame and initialize timing."""
        if not isinstance(bgr_frame, np.ndarray):
            raise TypeError("bgr_frame must be numpy.ndarray")
        
        if bgr_frame.ndim != 3 or bgr_frame.shape[2] != 3:
            raise ValueError(f"Expected BGR frame (H, W, 3), got {bgr_frame.shape}")
        
        if bgr_frame.dtype != np.uint8:
            raise ValueError(f"Expected uint8 array, got {bgr_frame.dtype}")
            
        final_scan_id = scan_id if scan_id is not None else self._generate_scan_id()
        return final_scan_id, cv2.getTickCount()

    def _execute_pipeline(self, frame: np.ndarray) -> Tuple[str, float, str]:
        """Run preprocessing and OCR engines."""
        processed = self._preprocess_thermal_receipt(frame)
        
        # Primary Engine
        text, confidence = self._ocr_tesseract(processed)
        engine = 'tesseract'
        
        # Fallback Engine
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
        """Format the final output dictionary."""
        
        # Use provided fields if available, otherwise extract from text
        if fields is None:
            fields = self._extract_fields(text)
        
        # Calculate processing time
        elapsed_ticks = cv2.getTickCount() - start_time
        processing_time_ms = int((elapsed_ticks / cv2.getTickFrequency()) * 1000)
        
        # Create timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        
        result = {
            'scan_id': scan_id,
            'raw_text': text,
            'confidence': round(confidence, 4),
            'timestamp': timestamp,
            'processing_time_ms': processing_time_ms,
            'ocr_engine': engine,
            'tracking_id': fields.get('tracking_id'),
            'order_id': fields.get('order_id'),
            'rts_code': fields.get('rts_code'),
            'rider_id': fields.get('rider_id'),
            'buyer_name': fields.get('buyer_name'),
            'buyer_address': fields.get('buyer_address'),
            'weight_g': fields.get('weight_g'),
            'quantity': fields.get('quantity'),
            'payment_type': fields.get('payment_type')
        }
        
        return result

    def _generate_scan_id(self) -> int:
        """Generate a unique scan ID."""
        return int(datetime.now().timestamp() * 1000000)

    def _preprocess_thermal_receipt(self, bgr_frame: np.ndarray) -> np.ndarray:
        """Preprocess thermal receipt image for OCR."""
        # Convert to grayscale
        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)
        
        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            contrast, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            11, 2
        )
        
        # Morphological closing to connect text
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return processed

    def _ocr_tesseract(
        self, 
        image: np.ndarray, 
        config: Optional[str] = None
    ) -> Tuple[str, float]:
        """Run Tesseract OCR on preprocessed image."""
        if config is None:
            config = self.tesseract_config
        
        try:
            # Get detailed data
            data = pytesseract.image_to_data(
                image, 
                config=config, 
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text
            text = pytesseract.image_to_string(image, config=config)
            
            # Calculate confidence
            confidences = [
                float(conf) for conf in data['conf'] 
                if conf != '-1' and str(conf).replace('.', '').isdigit()
            ]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            
            return text, avg_conf / 100.0  # Normalize to 0-1
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return "", 0.0

    def _ocr_paddle(self, image: np.ndarray) -> Tuple[str, float]:
        """Run PaddleOCR (fallback engine)."""
        if self.paddle_ocr is None:
            self.paddle_ocr = self._paddle_ocr_class(use_angle_cls=True, lang='en', show_log=False)
        
        try:
            result = self.paddle_ocr.ocr(image, cls=True)
            
            if not result or not result[0]:
                return "", 0.0
            
            lines = []
            confidences = []
            
            for line in result[0]:
                text = line[1][0]
                conf = line[1][1]
                lines.append(text)
                confidences.append(conf)
            
            full_text = '\n'.join(lines)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            
            return full_text, avg_conf
            
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return "", 0.0

    def _extract_fields(self, text: str) -> Dict[str, Any]:
        """Extract structured fields from OCR text."""
        fields = {
            'tracking_id': None,
            'order_id': None,
            'rts_code': None,
            'rider_id': None,
            'buyer_name': None,
            'buyer_address': None,
            'weight_g': None,
            'quantity': None,
            'payment_type': None
        }
        
        # Tracking ID
        match = re.search(self.PATTERNS['tracking_id'], text, re.IGNORECASE)
        if match:
            fields['tracking_id'] = match.group(0).replace(' ', '')
        
        # Order ID
        match = re.search(self.PATTERNS['order_id'], text, re.IGNORECASE)
        if match:
            fields['order_id'] = match.group(0)
        
        # RTS Code
        match = re.search(self.PATTERNS['rts_code'], text, re.IGNORECASE)
        if match:
            fields['rts_code'] = match.group(0)
        
        # Rider ID
        match = re.search(self.PATTERNS['rider_id'], text, re.IGNORECASE)
        if match:
            fields['rider_id'] = match.group(1)
        
        # Weight
        match = re.search(self.PATTERNS['weight'], text, re.IGNORECASE)
        if match:
            try:
                fields['weight_g'] = int(match.group(1))
            except ValueError:
                pass
        
        # Quantity
        match = re.search(self.PATTERNS['quantity'], text, re.IGNORECASE)
        if match:
            try:
                fields['quantity'] = int(match.group(1))
            except ValueError:
                pass
        
        # Payment Type
        match = re.search(self.PATTERNS['payment_type'], text, re.IGNORECASE)
        if match:
            fields['payment_type'] = match.group(1)
        
        return fields

    def _process_zones(self, bgr_frame: np.ndarray) -> Dict[str, Dict]:
        """Process receipt in zones for better accuracy.
        
        FIXED: Extended header zone to 40% to capture tracking ID on all images.
        """
        zones = {
            'header': self._process_header_zone(bgr_frame),
            'buyer': self._process_buyer_zone(bgr_frame),
            'footer': self._process_footer_zone(bgr_frame)
        }
        
        return zones

    def _process_header_zone(self, bgr_frame: np.ndarray) -> Dict[str, Any]:
        """Process header zone (tracking ID, order ID, RTS code).
        
        FIXED: Extended from 15% to 40% of image height to capture tracking ID.
        FIXED: Changed OCR config from psm 11 to psm 6 for better accuracy.
        """
        H, W = bgr_frame.shape[:2]
        
        # FIXED: Extended header zone to capture tracking ID
        y1, y2 = 0, int(H * 0.40)  # Was: int(H * 0.15)
        region = bgr_frame[y1:y2, :]
        
        # Preprocess
        processed = self._preprocess_thermal_receipt(region)
        
        # OCR with block text mode (FIXED: was psm 11)
        config = '--oem 1 --psm 6 -l eng'  # psm 6 = uniform block of text
        text, conf = self._ocr_tesseract(processed, config=config)
        
        # Debug output
        print(f"[HEADER RAW] {text[:200]}")
        
        # Extract fields
        fields = self._extract_header_fields(text)
        fields['confidence'] = conf
        fields['raw_text'] = text
        
        return fields

    def _extract_header_fields(self, ocr_text: str) -> Dict[str, Any]:
        """Extract tracking ID, order ID, RTS code, rider ID from header text."""
        
        fields = {
            'tracking_id': None,
            'order_id': None,
            'rts_code': None,
            'rider_id': None
        }
        
        # Tracking ID - FE + 10 digits
        match = re.search(r'FE\s?(\d{10})', ocr_text, re.IGNORECASE)
        if match:
            fields['tracking_id'] = f"FE{match.group(1)}"
        
        # Order ID - FE + 8 digits + letter + alphanumeric
        match = re.search(r'(FE\d{8}[A-Z]\w+)', ocr_text, re.IGNORECASE)
        if match:
            fields['order_id'] = match.group(1)
        
        # RTS Code
        match = re.search(self.PATTERNS['rts_code'], ocr_text, re.IGNORECASE)
        if match:
            fields['rts_code'] = match.group(0)
        
        # Rider ID
        match = re.search(self.PATTERNS['rider_id'], ocr_text, re.IGNORECASE)
        if match:
            fields['rider_id'] = match.group(1)
        
        return fields

    def _preprocess_buyer_zone(self, region: np.ndarray) -> np.ndarray:
        """Preprocess buyer information zone."""
        # Convert to grayscale
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)
        
        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            contrast, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Morphological operations
        kernel = np.ones((1, 1), np.uint8)
        processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return processed

    def _process_buyer_zone(self, bgr_frame: np.ndarray) -> Dict[str, Any]:
        """Process buyer information zone (name and address)."""
        H, W = bgr_frame.shape[:2]
        
        # Zone 3: Buyer section (40-58% of height, skip left margin)
        y1, y2 = int(H * 0.40), int(H * 0.58)
        x1, x2 = 60, int(W * 0.95)
        region = bgr_frame[y1:y2, x1:x2]
        
        # Preprocess
        processed = self._preprocess_buyer_zone(region)
        
        # OCR with single block mode
        config = '--oem 1 --psm 6 -l eng'
        text, conf = self._ocr_tesseract(processed, config=config)
        
        # Extract fields
        fields = self._extract_buyer_fields(text)
        fields['confidence'] = conf
        fields['raw_text'] = text
        
        return fields

    def _extract_buyer_fields(self, ocr_text: str) -> Dict[str, Any]:
        """Extract buyer name and address from OCR text."""
        
        fields = {
            'buyer_name': None,
            'buyer_address': None
        }
        
        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
        
        if not lines:
            return fields
        
        # First meaningful line is usually the name
        for line in lines:
            # Skip header keywords
            if any(kw in line.lower() for kw in ['buyer', 'seller', 'district', 'street', 'city', 'province', 'zip', 'pdg', 'cod']):
                continue
            
            # Check if it looks like a name (2-4 title-case words, no numbers)
            words = line.split()
            if 2 <= len(words) <= 4 and not any(char.isdigit() for char in line):
                if all(w[0].isupper() for w in words if w):
                    fields['buyer_name'] = line
                    break
        
        # Address is the longest line that contains "Brgy" or barangay reference
        max_len = 0
        best_address = None
        
        for line in lines:
            if len(line) > max_len and 'brgy' in line.lower():
                best_address = line
                max_len = len(line)
        
        if best_address:
            fields['buyer_address'] = self._clean_address(best_address)
        
        return fields

    def _process_footer_zone(self, bgr_frame: np.ndarray) -> Dict[str, Any]:
        """Process footer zone (weight and quantity)."""
        H, W = bgr_frame.shape[:2]
        
        # Zone 5: Footer (70-85% of height, left side only)
        y1, y2 = int(H * 0.70), int(H * 0.85)
        x1, x2 = 0, int(W * 0.45)
        region = bgr_frame[y1:y2, x1:x2]
        
        # Simple preprocessing
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological closing
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # OCR with sparse text mode
        config = '--oem 1 --psm 11 -l eng'
        text, conf = self._ocr_tesseract(processed, config=config)
        
        # Extract fields
        fields = self._extract_footer_fields(text)
        fields['confidence'] = conf
        fields['raw_text'] = text
        
        return fields

    def _extract_footer_fields(self, ocr_text: str) -> Dict[str, Any]:
        """Extract weight and quantity from footer text."""
        
        fields = {
            'weight_g': None,
            'quantity': None
        }
        
        # Weight pattern
        weight_match = re.search(r'(\d{3,5})\s*g', ocr_text, re.IGNORECASE)
        if weight_match:
            try:
                fields['weight_g'] = int(weight_match.group(1))
            except ValueError:
                pass
        
        # Quantity pattern
        qty_match = re.search(r'quantity:\s*(\d{1,3})', ocr_text, re.IGNORECASE)
        if qty_match:
            try:
                fields['quantity'] = int(qty_match.group(1))
            except ValueError:
                pass
        
        return fields

    def _validate_buyer_name(self, name: Optional[str]) -> bool:
        """Validate extracted buyer name."""
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
        """Validate extracted address."""
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
        """Merge results from all zones with validation."""
        
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
        
        # Header fields
        if 'header' in zone_results:
            header = zone_results['header']
            fields['tracking_id'] = header.get('tracking_id')
            fields['order_id'] = header.get('order_id')
            fields['rts_code'] = header.get('rts_code')
            fields['rider_id'] = header.get('rider_id')
        
        # Buyer fields (with validation)
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
        
        # Footer fields
        if 'footer' in zone_results:
            footer = zone_results['footer']
            fields['weight_g'] = footer.get('weight_g')
            fields['quantity'] = footer.get('quantity')
        
        # Calculate aggregate confidence
        confidences = []
        for zone in zone_results.values():
            if zone and 'confidence' in zone:
                confidences.append(zone['confidence'])
        
        fields['confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
        
        return fields
