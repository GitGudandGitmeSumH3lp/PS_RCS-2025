# knowledge_base.py (V5 - Tunable Threshold)
import re

# This value determines the minimum number of matching keywords required for a confident result.
# With your labels, a score of 3 or 4 is a good target.
SCORE_THRESHOLD = 3

LABEL_MODEL = [
    {"name": "Bagong Silang", "districts": [
        {"name": "BS02", "rider": "GY15", "rtsCode": "FEX-BUL-SJDM-BS02-GY15"}
    ]},
    {"name": "Muzon", "districts": [
        {"name": "Central", "code": "MZN3", "rider": "GY03", "rtsCode": "FEX-BUL-SJDM-MZN3-GY03"}
    ]},
    {"name": "Tungko", "districts": [
        {"name": "Main", "code": "TKO1", "rider": "GY22", "rtsCode": "FEX-BUL-SJDM-TKO1-GY22"}
    ]},
    {"name": "Sapang Palay", "districts": [
        {"name": "East", "code": "SPY2", "rider": "GY20", "rtsCode": "FEX-BUL-SJDM-SPY2-GY20"}
    ]},
    {"name": "Graceville", "districts": [
        {"name": "Commercial", "code": "GRC3", "rider": "GY07", "rtsCode": "FEX-BUL-SJDM-GRC3-GY07"}
    ]}
]

# --- Pre-processing for the Keyword Scoring system ---
VALID_RTS_CODES_WITH_PARTS = {}
for barangay in LABEL_MODEL:
    for district in barangay["districts"]:
        rts_code = district["rtsCode"]
        VALID_RTS_CODES_WITH_PARTS[rts_code] = rts_code.split('-')

TYPO_CORRECTIONS = { 'DRDER': 'ORDER', '5': 'S', '0': 'O', '1': 'I', '8': 'B', '\n': ' ' }