"""
PS_RCS_PROJECT
Copyright (c) 2026. All rights reserved.
File: src/services/ocr_patterns.py
Description: Regex patterns and constants for OCR parsing logic.
"""

import re
from typing import List, Dict

# Regex pattern for tracking numbers (e.g., TH1234567890)
TRACKING_PATTERN: re.Pattern = re.compile(r'TH[0-9]{10,12}')

# Regex pattern for Return To Sender codes (e.g., RTS-01)
RTS_PATTERN: re.Pattern = re.compile(r'RTS-[0-9]{2}')

# Regex pattern for Order IDs (e.g., ORD123456)
ORDER_PATTERN: re.Pattern = re.compile(r'ORD[0-9]{6,8}')

# Mapping of valid RTS codes to their human-readable descriptions
VALID_RTS_CODES: Dict[str, str] = {
    'RTS-01': 'Return to Sender - Address Not Found',
    'RTS-02': 'Return to Sender - Refused',
    'RTS-03': 'Return to Sender - Damaged'
}

# List of Bangkok districts for fuzzy matching location data
BANGKOK_DISTRICTS: List[str] = [
    'Bang Khen', 'Bang Kapi', 'Pathum Wan', 'Pom Prap Sattru Phai',
    'Phra Nakhon', 'Min Buri', 'Lat Krabang', 'Yan Nawa',
    'Samphanthawong', 'Phaya Thai', 'Thon Buri', 'Bang Khun Thian'
]

# Threshold for string similarity (0.0 to 1.0)
FUZZY_MATCH_THRESHOLD: float = 0.8