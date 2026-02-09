"""Flash Express OCR Processor.

This module provides specialized OCR for Flash Express thermal receipts.
Refactored to meet strict 50-line function limits while maintaining
full functionality and type safety.
"""

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
        'tracking_id': r'FE\d{10}',
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
        tesseract_config: str = '--oem 1 --psm 6 -l eng'
    ) -> None:
        """Initialize the OCR processor."""
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(f"confidence_threshold must be 0.0-1.0, got {confidence_threshold}")
        
        self.use_paddle_fallback: bool = use_paddle_fallback
        self.confidence_threshold: float = confidence_threshold
        self.tesseract_config: str = tesseract_config
        self._lock: threading.Lock = threading.Lock()
        
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
        """Process a single image frame to extract receipt data.
        
        Coordinates validation, execution, and formatting.
        """
        scan_id, start_time = self._validate_and_prepare(bgr_frame, scan_id)
        
        try:
            text, confidence, engine = self._execute_pipeline(bgr_frame)
            return self._format_result(scan_id, start_time, text, confidence, engine)
        except Exception as e:
            logger.error("OCR Processing failed: %s", str(e))
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
        engine: str
    ) -> Dict[str, Any]:
        """Format the final output dictionary with metadata."""
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
        """Generate a unique scan ID based on high-precision timestamp."""
        return int(datetime.now().timestamp() * 1000000)
    
    def _preprocess_thermal_receipt(self, bgr_frame: np.ndarray) -> np.ndarray:
        """Apply specialized CV pipeline for thermal paper receipts."""
        # Standardization
        if bgr_frame.shape[1] > 800:
            scale = 800.0 / bgr_frame.shape[1]
            height = int(bgr_frame.shape[0] * scale)
            resized = cv2.resize(bgr_frame, (800, height), interpolation=cv2.INTER_LANCZOS4)
        else:
            resized = bgr_frame
        
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        
        # Color Segmentation & Inpainting
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([10, 100, 100]), np.array([25, 255, 255]))
        cleaned = cv2.inpaint(gray, mask, 3, cv2.INPAINT_TELEA)
        
        # Denoising & Binarization
        denoised = cv2.fastNlMeansDenoising(cleaned, None, 10, 7, 21)
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # QR Masking
        h, w = binary.shape
        binary[int(h*0.75):, int(w*0.35):int(w*0.65)] = 255
        
        return binary
    
    def _ocr_tesseract(self, image: np.ndarray) -> Tuple[str, float]:
        """Run Tesseract OCR."""
        data = pytesseract.image_to_data(
            image, config=self.tesseract_config, output_type=pytesseract.Output.DICT
        )
        confs = [c for c in data['conf'] if c > 0]
        avg = sum(confs) / len(confs) if confs else 0.0
        text = pytesseract.image_to_string(image, config=self.tesseract_config)
        return text, avg / 100.0
    
    def _ocr_paddle(self, image: np.ndarray) -> Tuple[str, float]:
        """Run PaddleOCR fallback."""
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
        """Coordinate field extraction strategies."""
        fields = self._extract_regex_fields(ocr_text)
        self._extract_special_fields(ocr_text, fields)
        self._convert_field_types(fields)
        return fields

    def _extract_regex_fields(self, text: str) -> Dict[str, Any]:
        """Extract simple fields using regex patterns."""
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
        """Parse complex fields like names and addresses."""
        fields['buyer_name'] = self._parse_buyer_name(text)
        fields['buyer_address'] = self._parse_philippine_address(text)

    def _convert_field_types(self, fields: Dict[str, Any]) -> None:
        """Convert string extractions to proper types."""
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
        """Extract buyer name looking for 'BUYER' keyword."""
        buyer_pattern = r'BUYER\s*\n([A-Z][a-z]+ [A-Z][a-z]+)'
        match = re.search(buyer_pattern, text)
        return match.group(1) if match else None
    
    def _parse_philippine_address(self, text: str) -> Optional[str]:
        """Parse Philippine address formats."""
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