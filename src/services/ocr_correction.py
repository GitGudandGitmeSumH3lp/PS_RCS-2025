# src/services/ocr_correction.py

import json
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from rapidfuzz import fuzz

class FlashExpressCorrector:
    def __init__(self, dictionary_path: str, fuzzy_threshold: float = 80.0) -> None:
        with open(dictionary_path, 'r') as f:
            self.data: Dict[str, Any] = json.load(f)['couriers']['flash-express']
        self.barangays: List[str] = self.data['dictionaries']['barangays']
        self.districts: Dict[str, List[Dict[str, str]]] = self.data['dictionaries']['districts']
        self.rider_codes: Set[str] = set(self.data['fieldEnumerations']['riderCodes'])
        self.sort_codes: List[str] = self.data['fieldEnumerations']['sortCode']
        self.tracking_pattern: str = self.data['fieldPatterns']['trackingNumber']['pattern']
        self.phone_pattern: str = self.data['fieldPatterns']['phNumber']['pattern']
        self.fuzzy_threshold: float = fuzzy_threshold
        self.ocr_char_map: Dict[str, str] = {
            'O': '0', 'I': '1', 'Z': '2', 'S': '5', 'B': '8',
            'o': '0', 'i': '1', 'z': '2', 's': '5', 'b': '8',
            'L': '1', 'l': '1',   # added to fix 'l' -> '1'
            '|': '1'               # pipe often misread as 1 or I
        }

    def correct_barangay(self, text: str) -> str:
        if not text:
            return text
        best_match: Optional[str] = None
        best_score: float = 0.0
        for barangay in self.barangays:
            score = fuzz.ratio(text.lower(), barangay.lower())
            if score > best_score:
                best_score = score
                best_match = barangay
        if best_score >= self.fuzzy_threshold:
            return best_match
        return text

    def correct_district(self, barangay: str, text: str) -> str:
        if not barangay or not text or barangay not in self.districts:
            return text
        districts_list = [d['name'] for d in self.districts[barangay]]
        best_match: Optional[str] = None
        best_score: float = 0.0
        for district in districts_list:
            score = fuzz.ratio(text.lower(), district.lower())
            if score > best_score:
                best_score = score
                best_match = district
        if best_score >= self.fuzzy_threshold:
            return best_match
        return text

    def validate_tracking_number(self, text: str) -> Tuple[bool, str]:
        pattern = re.compile(self.tracking_pattern)
        if pattern.match(text):
            return True, text
        corrected = self._fix_ocr_digits(text)
        if pattern.match(corrected):
            return True, corrected
        return False, text

    def validate_phone(self, text: str) -> Tuple[bool, str]:
        pattern = re.compile(self.phone_pattern)
        if pattern.match(text):
            return True, text
        corrected = self._fix_ocr_digits(text)
        if pattern.match(corrected):
            return True, corrected
        return False, text

    def correct_rider_code(self, text: str) -> str:
        if not text:
            return text
        fixed = self._fix_ocr_digits(text)
        text_clean = fixed.strip().upper()
        if text_clean in self.rider_codes:
            return text_clean
        for code in self.rider_codes:
            if fuzz.ratio(text_clean, code) >= self.fuzzy_threshold:
                return code
        return text

    def correct_sort_code(self, text: str) -> str:
        if not text:
            return text
        fixed = self._fix_ocr_digits(text)
        text_clean = fixed.strip().upper()
        if text_clean in self.sort_codes:
            return text_clean
        for code in self.sort_codes:
            if fuzz.ratio(text_clean, code) >= self.fuzzy_threshold:
                return code
        return text

    def derive_quantity_from_weight(self, weight: int) -> int:
        return max(1, weight // 500)

    def clean_address(self, text: str) -> str:
        if not text:
            return text
        # Remove leading non-allowed characters
        text = re.sub(r'^[^\w\s,.-]+', '', text.strip())
        # Find the last 4-digit number (postal code)
        match = re.search(r'\b(\d{4})\b(?!.*\b\d{4}\b)', text)
        if match:
            end = match.end()
            text = text[:end].rstrip(' ,.-')
        else:
            # Fallback: remove trailing non-word/punctuation
            text = re.sub(r'[^\w\s,.-]+$', '', text)
            text = re.sub(r'\s+', ' ', text)
            text = text.strip(' ,.-')
        return text

    def _fix_ocr_digits(self, s: str) -> str:
        result = []
        for ch in s:
            if ch in self.ocr_char_map:
                result.append(self.ocr_char_map[ch])
            else:
                result.append(ch)
        return ''.join(result)