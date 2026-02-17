# src/services/extraction_guide.py

import json
import re
from typing import Dict, List, Optional, Set, Tuple, Any

from rapidfuzz import fuzz

_GROUND_TRUTH_PATH = 'data/dictionaries/ground_truth_parcel_gen.json'

def _load_courier_data(path: str, courier: str) -> Dict[str, Any]:
    with open(path, 'r') as f:
        root = json.load(f)
    shared = root.get('shared', {})
    courier_data = root['couriers'][courier]
    courier_data['_shared'] = shared
    return courier_data

_DATA: Dict[str, Any] = _load_courier_data(_GROUND_TRUTH_PATH, 'flash-express')

_BARANGAYS: List[str] = _DATA['dictionaries']['barangays']
_DISTRICTS: Dict[str, List[Dict[str, str]]] = _DATA['dictionaries']['districts']
_CITIES: List[str] = _DATA['dictionaries']['cities']
_PROVINCES: List[str] = _DATA['dictionaries']['provinces']
_RIDER_CODES: Set[str] = set(_DATA['fieldEnumerations']['riderCodes'])
_SORT_CODES: Set[str] = set(_DATA['fieldEnumerations']['sortCode'])
_FIELD_PATTERNS: Dict[str, Any] = _DATA['fieldPatterns']
_FIRST_NAMES: List[str] = _DATA['_shared'].get('firstNames', [])
_LAST_NAMES: List[str] = _DATA['_shared'].get('lastNames', [])
_ALL_NAMES: List[str] = _FIRST_NAMES + _LAST_NAMES

OCR_CHAR_MAP: Dict[str, str] = {
    'O': '0', 'I': '1', 'Z': '2', 'S': '5', 'B': '8',
    'o': '0', 'i': '1', 'z': '2', 's': '5', 'b': '8',
    'L': '1', 'l': '1', '|': '1'
}

_COMPILED_PATTERNS: Dict[str, re.Pattern] = {}
for _field, _pdata in _FIELD_PATTERNS.items():
    if isinstance(_pdata, dict) and 'pattern' in _pdata:
        try:
            _COMPILED_PATTERNS[_field] = re.compile(_pdata['pattern'])
        except re.error:
            pass


def fix_ocr_digits(text: str) -> str:
    return ''.join(OCR_CHAR_MAP.get(ch, ch) for ch in text)


def validate_and_fix_field(candidate: str, field_type: str) -> Tuple[Optional[str], bool]:
    if not candidate:
        return None, False
    pattern = _COMPILED_PATTERNS.get(field_type)
    if pattern is None:
        return candidate, False
    if pattern.match(candidate):
        return candidate, True
    fixed = fix_ocr_digits(candidate)
    if pattern.match(fixed):
        return fixed, True
    return candidate, False


def validate_code(candidate: str, code_type: str, threshold: float = 80.0) -> Optional[str]:
    if not candidate:
        return None
    if code_type == 'rider':
        code_set = _RIDER_CODES
    elif code_type == 'sort':
        code_set = _SORT_CODES
    else:
        return None

    clean = candidate.strip().upper()
    if clean in code_set:
        return clean

    fixed = fix_ocr_digits(clean).upper()
    if fixed in code_set:
        return fixed

    best: Optional[str] = None
    best_score: float = 0.0
    for code in code_set:
        score = fuzz.ratio(fixed, code)
        if score > best_score and score >= threshold:
            best_score = score
            best = code
    return best


def score_address_line(line: str, barangay_threshold: float = 75.0, place_threshold: float = 85.0) -> float:
    if not line:
        return 0.0
    tokens = line.split()
    if not tokens:
        return 0.0
    hits = 0
    for token in tokens:
        token_clean = re.sub(r'[^\w]', '', token)
        if not token_clean:
            continue
        matched = False
        for barangay in _BARANGAYS:
            if fuzz.partial_ratio(token_clean.lower(), barangay.lower()) >= barangay_threshold:
                hits += 1
                matched = True
                break
        if not matched:
            for place in _CITIES + _PROVINCES:
                if fuzz.partial_ratio(token_clean.lower(), place.lower()) >= place_threshold:
                    hits += 1
                    break
    return hits / len(tokens)


def cross_validate_weight_quantity(
    weight: Optional[int],
    quantity: Optional[int]
) -> Tuple[Optional[int], bool]:
    if weight is None:
        return quantity, False
    derived = max(1, weight // 500)
    if quantity is None:
        return derived, True
    if quantity != derived:
        return derived, True
    return quantity, False


def score_name_line(line: str, threshold: float = 85.0) -> float:
    if not line:
        return 0.0
    tokens = line.split()
    if not tokens:
        return 0.0
    hits = 0
    for token in tokens:
        token_clean = re.sub(r'[^\w]', '', token)
        if not token_clean:
            continue
        for name in _ALL_NAMES:
            if fuzz.ratio(token_clean.lower(), name.lower()) >= threshold:
                hits += 1
                break
    return hits / len(tokens)