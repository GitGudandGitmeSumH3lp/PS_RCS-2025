# src/services/ocr_service.py

import concurrent.futures
import numpy as np
import pytesseract
from datetime import datetime
from typing import Dict, Any, Optional
from difflib import SequenceMatcher

from .ocr_patterns import (
    TRACKING_PATTERN,
    RTS_PATTERN,
    ORDER_PATTERN,
    VALID_RTS_CODES,
    BANGKOK_DISTRICTS,
    FUZZY_MATCH_THRESHOLD
)

class OCRService:
    def __init__(self, max_workers: int = 2, tesseract_lang: str = 'eng') -> None:
        if max_workers < 1 or max_workers > 4:
            raise ValueError("max_workers must be between 1 and 4")
        if tesseract_lang not in ['eng', 'tha', 'eng+tha']:
            raise ValueError("tesseract_lang must be 'eng', 'tha', or 'eng+tha'")
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.tesseract_config = f'--oem 3 --psm 6 -l {tesseract_lang}'

    def process_scan(self, frame: np.ndarray) -> concurrent.futures.Future:
        if not isinstance(frame, np.ndarray):
            raise ValueError("Frame must be a valid numpy array with shape (H, W, 3)")
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            raise ValueError("Frame must be a valid numpy array with shape (H, W, 3)")
        
        if self.executor._shutdown:
            raise RuntimeError("OCR service has been shut down")
        
        return self.executor.submit(self._run_scan, frame)

    def _run_scan(self, frame: np.ndarray) -> Dict[str, Any]:
        try:
            preprocessed = self._preprocess_legacy(frame)
        except Exception as e:
            return {
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'tracking_id': None,
                'order_id': None,
                'rts_code': None,
                'district': None,
                'confidence': 0.0,
                'raw_text': '',
                'error': f'Preprocessing failed: {str(e)}'
            }
        
        try:
            raw_text = pytesseract.image_to_string(preprocessed, config=self.tesseract_config)
        except Exception as e:
            return {
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'tracking_id': None,
                'order_id': None,
                'rts_code': None,
                'district': None,
                'confidence': 0.0,
                'raw_text': '',
                'error': f'OCR extraction failed: {str(e)}'
            }
        
        try:
            parsed = self._parse_flash_express(raw_text)
            
            confidence = 0.0
            field_count = 0
            found_count = 0
            
            if parsed['tracking_id']:
                found_count += 1
            field_count += 1
            
            if parsed['order_id']:
                found_count += 1
            field_count += 1
            
            if parsed['rts_code']:
                found_count += 1
            field_count += 1
            
            if parsed['district']:
                found_count += 1
            field_count += 1
            
            if field_count > 0:
                confidence = found_count / field_count
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'tracking_id': parsed['tracking_id'],
                'order_id': parsed['order_id'],
                'rts_code': parsed['rts_code'],
                'district': parsed['district'],
                'confidence': confidence,
                'raw_text': raw_text,
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'tracking_id': None,
                'order_id': None,
                'rts_code': None,
                'district': None,
                'confidence': 0.0,
                'raw_text': raw_text,
                'error': f'Parsing failed: {str(e)}'
            }

    def _preprocess_legacy(self, image: np.ndarray) -> np.ndarray:
        import cv2
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        largest_area = 0
        best_contour = None
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > largest_area and area > 1000:
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:
                    largest_area = area
                    best_contour = approx
        
        if best_contour is not None:
            pts1 = np.float32(best_contour.reshape(4, 2))
            
            width = max(np.linalg.norm(pts1[1] - pts1[0]), np.linalg.norm(pts1[3] - pts1[2]))
            height = max(np.linalg.norm(pts1[2] - pts1[0]), np.linalg.norm(pts1[3] - pts1[1]))
            
            pts2 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
            
            matrix = cv2.getPerspectiveTransform(pts1, pts2)
            warped = cv2.warpPerspective(thresh, matrix, (int(width), int(height)))
            return warped
        
        return thresh

    def _parse_flash_express(self, text: str) -> Dict[str, Optional[str]]:
        cleaned = ' '.join(text.split()).upper()
        
        tracking_match = TRACKING_PATTERN.search(cleaned)
        tracking_id = tracking_match.group(0) if tracking_match else None
        
        rts_match = RTS_PATTERN.search(cleaned)
        rts_code = rts_match.group(0) if rts_match else None
        if rts_code and rts_code not in VALID_RTS_CODES:
            rts_code = None
        
        order_match = ORDER_PATTERN.search(cleaned)
        order_id = order_match.group(0) if order_match else None
        
        district = None
        for district_name in BANGKOK_DISTRICTS:
            ratio = SequenceMatcher(None, cleaned, district_name.upper()).ratio()
            if ratio >= FUZZY_MATCH_THRESHOLD:
                district = district_name
                break
        
        return {
            'tracking_id': tracking_id,
            'order_id': order_id,
            'rts_code': rts_code,
            'district': district
        }

    def shutdown(self, wait: bool = True) -> None:
        self.executor.shutdown(wait=wait)