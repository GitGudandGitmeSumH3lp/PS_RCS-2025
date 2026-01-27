# knowledge_base_optimized.py - High-Performance Pattern Matching & Data Structures

import re
import Levenshtein
from typing import Dict, List, Optional, Set, Tuple
from functools import lru_cache
from dataclasses import dataclass
import numpy as np
from collections import defaultdict

# Master Data Model - Enhanced with metadata
@dataclass
class District:
    name: str
    code: str
    rider: str
    rts_code: str
    name_variations: Set[str]

@dataclass
class Barangay:
    name: str
    districts: List[District]
    name_variations: Set[str]

# Enhanced data with common variations and typos
ENHANCED_LABEL_MODEL = [
    {
        "name": "Muzon", 
        "variations": {"MUZON", "MUZOM", "MUZ0N", "MUZ0M"},
        "districts": [
            {"name": "North", "code": "MZN1", "rider": "GY01", "rtsCode": "FEX-BUL-SJDM-MZN1-GY01", "variations": {"NORTH", "N0RTH", "MORTH"}},
            {"name": "South", "code": "MZN2", "rider": "GY02", "rtsCode": "FEX-BUL-SJDM-MZN2-GY02", "variations": {"SOUTH", "S0UTH", "SOUT"}},
            {"name": "Central", "code": "MZN3", "rider": "GY03", "rtsCode": "FEX-BUL-SJDM-MZN3-GY03", "variations": {"CENTRAL", "CENTR4L", "GENTRAL"}},
            {"name": "Proper", "code": "MZN4", "rider": "GY04", "rtsCode": "FEX-BUL-SJDM-MZN4-GY04", "variations": {"PROPER", "PR0PER", "PROP3R"}}
        ]
    },
    {
        "name": "Graceville", 
        "variations": {"GRACEVILLE", "GR4CEVILLE", "GRACEVILE", "GRACVILE"},
        "districts": [
            {"name": "Subdivision", "code": "TKO2", "rider": "GY23", "rtsCode": "FEX-BUL-SJDM-TKO2-GY23", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    }
]

# Pre-compute lookup structures for O(1) access
VALID_RTS_CODES = []
RTS_CODE_TO_ADDRESS = {}
BARANGAY_VARIATIONS = defaultdict(str)  # variation -> canonical name
DISTRICT_VARIATIONS = defaultdict(str)  # variation -> canonical name
RTS_CODE_TRIE = {}  # For fast prefix matching

for barangay in ENHANCED_LABEL_MODEL:
    barangay_name = barangay["name"]
    
    # Add barangay variations
    for variation in barangay["variations"]:
        BARANGAY_VARIATIONS[variation] = barangay_name
    
    for district in barangay["districts"]:
        rts_code = district["rtsCode"]
        district_name = district["name"]
        
        VALID_RTS_CODES.append(rts_code)
        RTS_CODE_TO_ADDRESS[rts_code] = {
            "barangay": barangay_name, 
            "district": district_name
        }
        
        # Add district variations
        for variation in district["variations"]:
            DISTRICT_VARIATIONS[variation] = district_name

# Build optimized regex patterns with performance focus
FIELD_PATTERNS = {
    # Exact patterns - fastest matching
    "tracking_number": re.compile(r'\bFE\d{10}\b', re.IGNORECASE),
    "ph_number": re.compile(r'\bFE\s?\d{12}\b', re.IGNORECASE),
    
    # Enhanced order ID pattern with common OCR errors
    "order_id": re.compile(
        r'(?:Order|0rder|Drder|0rder)\s*I[D0O]?\s*:?\s*(FE\d{6}[A-Z0-9]{6})', 
        re.IGNORECASE
    ),
    
    # Multi-pattern RTS code matching
    "rts_code_label": re.compile(
        r'(?:RTS|RT5|R7S)\s*(?:Sort|S0rt|50rt)?\s*(?:Code|C0de|G0de)\s*:?\s*([A-Z0-9-]{15,})', 
        re.IGNORECASE
    ),
    
    # Direct RTS pattern with flexibility
    "rts_code_pattern": re.compile(
        r'\b(FEX-[A-Z0-9-]{15,}|F3X-[A-Z0-9-]{15,}|FEX[A-Z0-9-]{15,})\b', 
        re.IGNORECASE
    ),
    
    # Enhanced address pattern with multiple formats
    "address": re.compile(
        r'(?:Brgy|8rgy|Brg|Barangay)\.?\s+([A-Za-z\s\(\)]+?)[\s,]+([A-Za-z\s\(\)1-9]+?)(?:,|$|\n)', 
        re.IGNORECASE | re.MULTILINE
    ),
    
    # Additional patterns for better extraction
    "confidence_indicators": re.compile(r'(CONFIRMED|VERIFIED|VALIDATED)', re.IGNORECASE),
    "quality_markers": re.compile(r'(PRIORITY|URGENT|EXPRESS)', re.IGNORECASE)
}

# Comprehensive typo correction mapping
TYPO_CORRECTIONS = {
    # Number/Letter substitutions
    '0': 'O', '1': 'I', '3': 'E', '4': 'A', '5': 'S', '6': 'G', '7': 'T', '8': 'B', '9': 'G',
    
    # Common OCR errors
    'DRDER': 'ORDER', 'QRDER': 'ORDER', '0RDER': 'ORDER',
    'C0DE': 'CODE', 'G0DE': 'CODE', 'GODE': 'CODE',
    'RT5': 'RTS', 'R7S': 'RTS', 'RT
            {"name": "Main", "code": "GRC2", "rider": "GY06", "rtsCode": "FEX-BUL-SJDM-GRC2-GY06", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Commercial", "code": "GRC3", "rider": "GY07", "rtsCode": "FEX-BUL-SJDM-GRC3-GY07", "variations": {"COMMERCIAL", "COMMERC1AL", "GOMMERC1AL"}}
        ]
    },
    {
        "name": "Citrus", 
        "variations": {"CITRUS", "C1TRUS", "GITRUS", "C1TR0S"},
        "districts": [
            {"name": "Main", "code": "CTR1", "rider": "GY08", "rtsCode": "FEX-BUL-SJDM-CTR1-GY08", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Extension", "code": "CTR2", "rider": "GY09", "rtsCode": "FEX-BUL-SJDM-CTR2-GY09", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Assumption", 
        "variations": {"ASSUMPTION", "ASSUMPT10N", "ASUMPTION", "ASSUMPT1ON"},
        "districts": [
            {"name": "Main", "code": "ASM1", "rider": "GY10", "rtsCode": "FEX-BUL-SJDM-ASM1-GY10", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "ASM2", "rider": "GY11", "rtsCode": "FEX-BUL-SJDM-ASM2-GY11", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Dulong Bayan", 
        "variations": {"DULONG BAYAN", "DUL0NG BAYAN", "DULONG BAY4N", "DUL0NG B4YAN"},
        "districts": [
            {"name": "Proper", "code": "DLB1", "rider": "GY12", "rtsCode": "FEX-BUL-SJDM-DLB1-GY12", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "Extension", "code": "DLB2", "rider": "GY13", "rtsCode": "FEX-BUL-SJDM-DLB2-GY13", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Francisco Homes", 
        "variations": {"FRANCISCO HOMES", "FRANC1SCO HOMES", "FRANCISC0 H0MES", "FRANSISCO HOMES"},
        "districts": [
            {"name": "Guijo", "code": "FRH1", "rider": "GY14", "rtsCode": "FEX-BUL-SJDM-FRH1-GY14", "variations": {"GUIJO", "GU1JO", "GUIJ0"}},
            {"name": "Narra", "code": "FRH2", "rider": "GY15", "rtsCode": "FEX-BUL-SJDM-FRH2-GY15", "variations": {"NARRA", "NARA", "N4RRA"}},
            {"name": "Yakal", "code": "FRH3", "rider": "GY16", "rtsCode": "FEX-BUL-SJDM-FRH3-GY16", "variations": {"YAKAL", "YAK4L", "Y4KAL"}}
        ]
    },
    {
        "name": "Kaypian", 
        "variations": {"KAYPIAN", "K4YPIAN", "KAYP1AN", "K4YP14N"},
        "districts": [
            {"name": "Main", "code": "KYP1", "rider": "GY17", "rtsCode": "FEX-BUL-SJDM-KYP1-GY17", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "KYP2", "rider": "GY18", "rtsCode": "FEX-BUL-SJDM-KYP2-GY18", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Minuyan", 
        "variations": {"MINUYAN", "M1NUYAN", "MINUY4N", "M1NUY4N"},
        "districts": [
            {"name": "Proper", "code": "MNY1", "rider": "GY19", "rtsCode": "FEX-BUL-SJDM-MNY1-GY19", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "1st", "code": "MNY2", "rider": "GY20", "rtsCode": "FEX-BUL-SJDM-MNY2-GY20", "variations": {"1ST", "15T", "1S7"}},
            {"name": "2nd", "code": "MNY3", "rider": "GY21", "rtsCode": "FEX-BUL-SJDM-MNY3-GY21", "variations": {"2ND", "2N0", "2MD"}}
        ]
    },
    {
        "name": "Tungko", 
        "variations": {"TUNGKO", "TUNGK0", "TUNK0", "7UNGKO"},
        "districts": [
            {"name": "Main", "code": "TKO1", "rider": "GY22", "rtsCode": "FEX-BUL-SJDM-TKO1-GY22", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision: 'RTS',
    'S0RT': 'SORT', '50RT': 'SORT', '$ORT': 'SORT',
    'FE><': 'FEX', 'F3X': 'FEX', 'F£X': 'FEX',
    'BUL': 'BUL', '8UL': 'BUL', 'BUt': 'BUL',
    'SJDM': 'SJDM', '5JDM': 'SJDM', 'SJ0M': 'SJDM',
    
    # Common word corrections
    'SUBDIV': 'SUBDIVISION', 'SUB0IV': 'SUBDIVISION',
    'EXTENS10N': 'EXTENSION', 'EXT': 'EXTENSION',
    'PR0PER': 'PROPER', 'PROP3R': 'PROPER',
    'M41N': 'MAIN', 'MA1N': 'MAIN',
    'COMMERC1AL': 'COMMERCIAL', 'GOMMERC1AL': 'COMMERCIAL'
}

class RTSCodeMatcher:
    """High-performance RTS code matching with fuzzy logic and caching"""
    
    def __init__(self):
        self.valid_codes = VALID_RTS_CODES
        self.code_variations = self._build_code_variations()
        self._match_cache = {}
    
    def _build_code_variations(self) -> Dict[str, str]:
        """Pre-compute common variations of RTS codes"""
        variations = {}
        
        for code in self.valid_codes:
            # Add the original code
            variations[code] = code
            
            # Add common OCR error variations
            error_code = code
            for old, new in TYPO_CORRECTIONS.items():
                error_code = error_code.replace(old, new)
            variations[error_code] = code
            
            # Add variations with missing/extra hyphens
            no_hyphens = code.replace('-', '')
            variations[no_hyphens] = code
            
            # Add variations with spaces instead of hyphens
            with_spaces = code.replace('-', ' ')
            variations[with_spaces] = code
        
        return variations
    
    @lru_cache(maxsize=1000)
    def find_best_match(self, candidate: str, max_distance: int = 8) -> Optional[str]:
        """Find best matching RTS code with caching"""
        if not candidate:
            return None
        
        candidate = candidate.strip().upper()
        
        # Exact match (fastest)
        if candidate in self.code_variations:
            return self.code_variations[candidate]
        
        # Apply typo corrections first
        corrected = candidate
        for error, correction in TYPO_CORRECTIONS.items():
            corrected = corrected.replace(error, correction)
        
        if corrected in self.code_variations:
            return self.code_variations[corrected]
        
        # Fuzzy matching with early termination
        best_match = None
        best_distance = float('inf')
        
        for code in self.valid_codes:
            # Quick length check to skip obviously bad matches
            if abs(len(candidate) - len(code)) > max_distance:
                continue
            
            distance = Levenshtein.distance(candidate, code)
            if distance < best_distance and distance <= max_distance:
                best_distance = distance
                best_match = code
                
                # Early termination for very close matches
                if distance <= 2:
                    break
        
        return best_match if best_distance <= max_distance else None
    
    def get_match_confidence(self, candidate: str, matched_code: str) -> float:
        """Calculate confidence score for a match"""
        if not candidate or not matched_code:
            return 0.0
        
        distance = Levenshtein.distance(candidate.upper(), matched_code.upper())
        max_length = max(len(candidate), len(matched_code))
        
        # Confidence score based on similarity
        similarity = 1.0 - (distance / max_length)
        return max(0.0, similarity)

class SmartAddressMatcher:
    """Advanced address matching with geographic context"""
    
    def __init__(self):
        self.barangay_variations = BARANGAY_VARIATIONS
        self.district_variations = DISTRICT_VARIATIONS
        self._address_cache = {}
    
    @lru_cache(maxsize=500)
    def match_barangay(self, candidate: str) -> Optional[str]:
        """Match barangay name with variations support"""
        if not candidate:
            return None
        
        candidate = candidate.strip().upper()
        
        # Exact match in variations
        if candidate in self.barangay_variations:
            return self.barangay_variations[candidate]
        
        # Fuzzy matching
        best_match = None
        best_score = 0.0
        
        for variation, canonical in self.barangay_variations.items():
            similarity = self._calculate_similarity(candidate, variation)
            if similarity > best_score and similarity > 0.7:
                best_score = similarity
                best_match = canonical
        
        return best_match
    
    @lru_cache(maxsize=500)
    def match_district(self, candidate: str) -> Optional[str]:
        """Match district name with variations support"""
        if not candidate:
            return None
        
        candidate = candidate.strip().upper()
        
        # Exact match in variations
        if candidate in self.district_variations:
            return self.district_variations[candidate]
        
        # Fuzzy matching
        best_match = None
        best_score = 0.0
        
        for variation, canonical in self.district_variations.items():
            similarity = self._calculate_similarity(candidate, variation)
            if similarity > best_score and similarity > 0.7:
                best_score = similarity
                best_match = canonical
        
        return best_match
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate normalized similarity score"""
        if not str1 or not str2:
            return 0.0
        
        distance = Levenshtein.distance(str1, str2)
        max_length = max(len(str1), len(str2))
        
        return 1.0 - (distance / max_length) if max_length > 0 else 0.0
    
    def validate_address_pair(self, barangay: str, district: str, rts_code: str) -> Tuple[bool, float]:
        """Validate if barangay-district pair matches expected from RTS code"""
        if not rts_code or rts_code not in RTS_CODE_TO_ADDRESS:
            return False, 0.0
        
        expected = RTS_CODE_TO_ADDRESS[rts_code]
        
        # Match extracted names to expected
        matched_barangay = self.match_barangay(barangay)
        matched_district = self.match_district(district)
        
        barangay_match = matched_barangay == expected["barangay"]
        district_match = matched_district == expected["district"]
        
        # Calculate confidence
        confidence = 0.0
        if barangay_match:
            confidence += 0.5
        if district_match:
            confidence += 0.5
        
        return (barangay_match and district_match), confidence

# Performance monitoring utilities
class PerformanceProfiler:
    """Simple performance profiling for optimization"""
    
    def __init__(self):
        self.timings = defaultdict(list)
    
    def time_function(self, func_name: str):
        """Decorator for timing function execution"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import time
                start = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                self.timings[func_name].append(elapsed)
                return result
            return wrapper
        return decorator
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics"""
        stats = {}
        for func_name, times in self.timings.items():
            if times:
                stats[func_name] = {
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'count': len(times)
                }
        return stats

# Global instances
rts_matcher = RTSCodeMatcher()
address_matcher = SmartAddressMatcher()
profiler = PerformanceProfiler()

# Utility functions for backward compatibility
def get_valid_rts_codes() -> List[str]:
    return VALID_RTS_CODES.copy()

def get_rts_code_to_address() -> Dict[str, Dict[str, str]]:
    return RTS_CODE_TO_ADDRESS.copy()

def get_field_patterns() -> Dict[str, re.Pattern]:
    return FIELD_PATTERNS.copy()

def get_typo_corrections() -> Dict[str, str]:
    return TYPO_CORRECTIONS.copy()", "code": "GRC1", "rider": "GY05", "rtsCode": "FEX-BUL-SJDM-GRC1-GY05", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}},
            {"name": "Main", "code": "GRC2", "rider": "GY06", "rtsCode": "FEX-BUL-SJDM-GRC2-GY06", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Commercial", "code": "GRC3", "rider": "GY07", "rtsCode": "FEX-BUL-SJDM-GRC3-GY07", "variations": {"COMMERCIAL", "COMMERC1AL", "GOMMERC1AL"}}
        ]
    },
    {
        "name": "Citrus", 
        "variations": {"CITRUS", "C1TRUS", "GITRUS", "C1TR0S"},
        "districts": [
            {"name": "Main", "code": "CTR1", "rider": "GY08", "rtsCode": "FEX-BUL-SJDM-CTR1-GY08", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Extension", "code": "CTR2", "rider": "GY09", "rtsCode": "FEX-BUL-SJDM-CTR2-GY09", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Assumption", 
        "variations": {"ASSUMPTION", "ASSUMPT10N", "ASUMPTION", "ASSUMPT1ON"},
        "districts": [
            {"name": "Main", "code": "ASM1", "rider": "GY10", "rtsCode": "FEX-BUL-SJDM-ASM1-GY10", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "ASM2", "rider": "GY11", "rtsCode": "FEX-BUL-SJDM-ASM2-GY11", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Dulong Bayan", 
        "variations": {"DULONG BAYAN", "DUL0NG BAYAN", "DULONG BAY4N", "DUL0NG B4YAN"},
        "districts": [
            {"name": "Proper", "code": "DLB1", "rider": "GY12", "rtsCode": "FEX-BUL-SJDM-DLB1-GY12", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "Extension", "code": "DLB2", "rider": "GY13", "rtsCode": "FEX-BUL-SJDM-DLB2-GY13", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Francisco Homes", 
        "variations": {"FRANCISCO HOMES", "FRANC1SCO HOMES", "FRANCISC0 H0MES", "FRANSISCO HOMES"},
        "districts": [
            {"name": "Guijo", "code": "FRH1", "rider": "GY14", "rtsCode": "FEX-BUL-SJDM-FRH1-GY14", "variations": {"GUIJO", "GU1JO", "GUIJ0"}},
            {"name": "Narra", "code": "FRH2", "rider": "GY15", "rtsCode": "FEX-BUL-SJDM-FRH2-GY15", "variations": {"NARRA", "NARA", "N4RRA"}},
            {"name": "Yakal", "code": "FRH3", "rider": "GY16", "rtsCode": "FEX-BUL-SJDM-FRH3-GY16", "variations": {"YAKAL", "YAK4L", "Y4KAL"}}
        ]
    },
    {
        "name": "Kaypian", 
        "variations": {"KAYPIAN", "K4YPIAN", "KAYP1AN", "K4YP14N"},
        "districts": [
            {"name": "Main", "code": "KYP1", "rider": "GY17", "rtsCode": "FEX-BUL-SJDM-KYP1-GY17", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "KYP2", "rider": "GY18", "rtsCode": "FEX-BUL-SJDM-KYP2-GY18", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Minuyan", 
        "variations": {"MINUYAN", "M1NUYAN", "MINUY4N", "M1NUY4N"},
        "districts": [
            {"name": "Proper", "code": "MNY1", "rider": "GY19", "rtsCode": "FEX-BUL-SJDM-MNY1-GY19", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "1st", "code": "MNY2", "rider": "GY20", "rtsCode": "FEX-BUL-SJDM-MNY2-GY20", "variations": {"1ST", "15T", "1S7"}},
            {"name": "2nd", "code": "MNY3", "rider": "GY21", "rtsCode": "FEX-BUL-SJDM-MNY3-GY21", "variations": {"2ND", "2N0", "2MD"}}
        ]
    },
    {
        "name": "Tungko", 
        "variations": {"TUNGKO", "TUNGK0", "TUNK0", "7UNGKO"},
        "districts": [
            {"name": "Main", "code": "TKO1", "rider": "GY22", "rtsCode": "FEX-BUL-SJDM-TKO1-GY22", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision: 'RTS',
            {"name": "Main", "code": "GRC2", "rider": "GY06", "rtsCode": "FEX-BUL-SJDM-GRC2-GY06", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Commercial", "code": "GRC3", "rider": "GY07", "rtsCode": "FEX-BUL-SJDM-GRC3-GY07", "variations": {"COMMERCIAL", "COMMERC1AL", "GOMMERC1AL"}}
        ]
    },
    {
        "name": "Citrus", 
        "variations": {"CITRUS", "C1TRUS", "GITRUS", "C1TR0S"},
        "districts": [
            {"name": "Main", "code": "CTR1", "rider": "GY08", "rtsCode": "FEX-BUL-SJDM-CTR1-GY08", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Extension", "code": "CTR2", "rider": "GY09", "rtsCode": "FEX-BUL-SJDM-CTR2-GY09", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Assumption", 
        "variations": {"ASSUMPTION", "ASSUMPT10N", "ASUMPTION", "ASSUMPT1ON"},
        "districts": [
            {"name": "Main", "code": "ASM1", "rider": "GY10", "rtsCode": "FEX-BUL-SJDM-ASM1-GY10", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "ASM2", "rider": "GY11", "rtsCode": "FEX-BUL-SJDM-ASM2-GY11", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Dulong Bayan", 
        "variations": {"DULONG BAYAN", "DUL0NG BAYAN", "DULONG BAY4N", "DUL0NG B4YAN"},
        "districts": [
            {"name": "Proper", "code": "DLB1", "rider": "GY12", "rtsCode": "FEX-BUL-SJDM-DLB1-GY12", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "Extension", "code": "DLB2", "rider": "GY13", "rtsCode": "FEX-BUL-SJDM-DLB2-GY13", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Francisco Homes", 
        "variations": {"FRANCISCO HOMES", "FRANC1SCO HOMES", "FRANCISC0 H0MES", "FRANSISCO HOMES"},
        "districts": [
            {"name": "Guijo", "code": "FRH1", "rider": "GY14", "rtsCode": "FEX-BUL-SJDM-FRH1-GY14", "variations": {"GUIJO", "GU1JO", "GUIJ0"}},
            {"name": "Narra", "code": "FRH2", "rider": "GY15", "rtsCode": "FEX-BUL-SJDM-FRH2-GY15", "variations": {"NARRA", "NARA", "N4RRA"}},
            {"name": "Yakal", "code": "FRH3", "rider": "GY16", "rtsCode": "FEX-BUL-SJDM-FRH3-GY16", "variations": {"YAKAL", "YAK4L", "Y4KAL"}}
        ]
    },
    {
        "name": "Kaypian", 
        "variations": {"KAYPIAN", "K4YPIAN", "KAYP1AN", "K4YP14N"},
        "districts": [
            {"name": "Main", "code": "KYP1", "rider": "GY17", "rtsCode": "FEX-BUL-SJDM-KYP1-GY17", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "KYP2", "rider": "GY18", "rtsCode": "FEX-BUL-SJDM-KYP2-GY18", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Minuyan", 
        "variations": {"MINUYAN", "M1NUYAN", "MINUY4N", "M1NUY4N"},
        "districts": [
            {"name": "Proper", "code": "MNY1", "rider": "GY19", "rtsCode": "FEX-BUL-SJDM-MNY1-GY19", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "1st", "code": "MNY2", "rider": "GY20", "rtsCode": "FEX-BUL-SJDM-MNY2-GY20", "variations": {"1ST", "15T", "1S7"}},
            {"name": "2nd", "code": "MNY3", "rider": "GY21", "rtsCode": "FEX-BUL-SJDM-MNY3-GY21", "variations": {"2ND", "2N0", "2MD"}}
        ]
    },
    {
        "name": "Tungko", 
        "variations": {"TUNGKO", "TUNGK0", "TUNK0", "7UNGKO"},
        "districts": [
            {"name": "Main", "code": "TKO1", "rider": "GY22", "rtsCode": "FEX-BUL-SJDM-TKO1-GY22", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision: 'RTS',
    'S0RT': 'SORT', '50RT': 'SORT', '$ORT': 'SORT',
    'FE><': 'FEX', 'F3X': 'FEX', 'F£X': 'FEX',
    'BUL': 'BUL', '8UL': 'BUL', 'BUt': 'BUL',
    'SJDM': 'SJDM', '5JDM': 'SJDM', 'SJ0M': 'SJDM',
    
    # Common word corrections
    'SUBDIV': 'SUBDIVISION', 'SUB0IV': 'SUBDIVISION',
    'EXTENS10N': 'EXTENSION', 'EXT': 'EXTENSION',
    'PR0PER': 'PROPER', 'PROP3R': 'PROPER',
    'M41N': 'MAIN', 'MA1N': 'MAIN',
    'COMMERC1AL': 'COMMERCIAL', 'GOMMERC1AL': 'COMMERCIAL'
}

class RTSCodeMatcher:
    """High-performance RTS code matching with fuzzy logic and caching"""
    
    def __init__(self):
        self.valid_codes = VALID_RTS_CODES
        self.code_variations = self._build_code_variations()
        self._match_cache = {}
    
    def _build_code_variations(self) -> Dict[str, str]:
        """Pre-compute common variations of RTS codes"""
        variations = {}
        
        for code in self.valid_codes:
            # Add the original code
            variations[code] = code
            
            # Add common OCR error variations
            error_code = code
            for old, new in TYPO_CORRECTIONS.items():
                error_code = error_code.replace(old, new)
            variations[error_code] = code
            
            # Add variations with missing/extra hyphens
            no_hyphens = code.replace('-', '')
            variations[no_hyphens] = code
            
            # Add variations with spaces instead of hyphens
            with_spaces = code.replace('-', ' ')
            variations[with_spaces] = code
        
        return variations
    
    @lru_cache(maxsize=1000)
    def find_best_match(self, candidate: str, max_distance: int = 8) -> Optional[str]:
        """Find best matching RTS code with caching"""
        if not candidate:
            return None
        
        candidate = candidate.strip().upper()
        
        # Exact match (fastest)
        if candidate in self.code_variations:
            return self.code_variations[candidate]
        
        # Apply typo corrections first
        corrected = candidate
        for error, correction in TYPO_CORRECTIONS.items():
            corrected = corrected.replace(error, correction)
        
        if corrected in self.code_variations:
            return self.code_variations[corrected]
        
        # Fuzzy matching with early termination
        best_match = None
        best_distance = float('inf')
        
        for code in self.valid_codes:
            # Quick length check to skip obviously bad matches
            if abs(len(candidate) - len(code)) > max_distance:
                continue
            
            distance = Levenshtein.distance(candidate, code)
            if distance < best_distance and distance <= max_distance:
                best_distance = distance
                best_match = code
                
                # Early termination for very close matches
                if distance <= 2:
                    break
        
        return best_match if best_distance <= max_distance else None
    
    def get_match_confidence(self, candidate: str, matched_code: str) -> float:
        """Calculate confidence score for a match"""
        if not candidate or not matched_code:
            return 0.0
        
        distance = Levenshtein.distance(candidate.upper(), matched_code.upper())
        max_length = max(len(candidate), len(matched_code))
        
        # Confidence score based on similarity
        similarity = 1.0 - (distance / max_length)
        return max(0.0, similarity)

class SmartAddressMatcher:
    """Advanced address matching with geographic context"""
    
    def __init__(self):
        self.barangay_variations = BARANGAY_VARIATIONS
        self.district_variations = DISTRICT_VARIATIONS
        self._address_cache = {}
    
    @lru_cache(maxsize=500)
    def match_barangay(self, candidate: str) -> Optional[str]:
        """Match barangay name with variations support"""
        if not candidate:
            return None
        
        candidate = candidate.strip().upper()
        
        # Exact match in variations
        if candidate in self.barangay_variations:
            return self.barangay_variations[candidate]
        
        # Fuzzy matching
        best_match = None
        best_score = 0.0
        
        for variation, canonical in self.barangay_variations.items():
            similarity = self._calculate_similarity(candidate, variation)
            if similarity > best_score and similarity > 0.7:
                best_score = similarity
                best_match = canonical
        
        return best_match
    
    @lru_cache(maxsize=500)
    def match_district(self, candidate: str) -> Optional[str]:
        """Match district name with variations support"""
        if not candidate:
            return None
        
        candidate = candidate.strip().upper()
        
        # Exact match in variations
        if candidate in self.district_variations:
            return self.district_variations[candidate]
        
        # Fuzzy matching
        best_match = None
        best_score = 0.0
        
        for variation, canonical in self.district_variations.items():
            similarity = self._calculate_similarity(candidate, variation)
            if similarity > best_score and similarity > 0.7:
                best_score = similarity
                best_match = canonical
        
        return best_match
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate normalized similarity score"""
        if not str1 or not str2:
            return 0.0
        
        distance = Levenshtein.distance(str1, str2)
        max_length = max(len(str1), len(str2))
        
        return 1.0 - (distance / max_length) if max_length > 0 else 0.0
    
    def validate_address_pair(self, barangay: str, district: str, rts_code: str) -> Tuple[bool, float]:
        """Validate if barangay-district pair matches expected from RTS code"""
        if not rts_code or rts_code not in RTS_CODE_TO_ADDRESS:
            return False, 0.0
        
        expected = RTS_CODE_TO_ADDRESS[rts_code]
        
        # Match extracted names to expected
        matched_barangay = self.match_barangay(barangay)
        matched_district = self.match_district(district)
        
        barangay_match = matched_barangay == expected["barangay"]
        district_match = matched_district == expected["district"]
        
        # Calculate confidence
        confidence = 0.0
        if barangay_match:
            confidence += 0.5
        if district_match:
            confidence += 0.5
        
        return (barangay_match and district_match), confidence

# Performance monitoring utilities
class PerformanceProfiler:
    """Simple performance profiling for optimization"""
    
    def __init__(self):
        self.timings = defaultdict(list)
    
    def time_function(self, func_name: str):
        """Decorator for timing function execution"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import time
                start = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                self.timings[func_name].append(elapsed)
                return result
            return wrapper
        return decorator
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics"""
        stats = {}
        for func_name, times in self.timings.items():
            if times:
                stats[func_name] = {
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'count': len(times)
                }
        return stats

# Global instances
rts_matcher = RTSCodeMatcher()
address_matcher = SmartAddressMatcher()
profiler = PerformanceProfiler()

# Utility functions for backward compatibility
def get_valid_rts_codes() -> List[str]:
    return VALID_RTS_CODES.copy()

def get_rts_code_to_address() -> Dict[str, Dict[str, str]]:
    return RTS_CODE_TO_ADDRESS.copy()

def get_field_patterns() -> Dict[str, re.Pattern]:
    return FIELD_PATTERNS.copy()

def get_typo_corrections() -> Dict[str, str]:
    return TYPO_CORRECTIONS.copy()", "code": "GRC1", "rider": "GY05", "rtsCode": "FEX-BUL-SJDM-GRC1-GY05", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}},
            {"name": "Main", "code": "GRC2", "rider": "GY06", "rtsCode": "FEX-BUL-SJDM-GRC2-GY06", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Commercial", "code": "GRC3", "rider": "GY07", "rtsCode": "FEX-BUL-SJDM-GRC3-GY07", "variations": {"COMMERCIAL", "COMMERC1AL", "GOMMERC1AL"}}
        ]
    },
    {
        "name": "Citrus", 
        "variations": {"CITRUS", "C1TRUS", "GITRUS", "C1TR0S"},
        "districts": [
            {"name": "Main", "code": "CTR1", "rider": "GY08", "rtsCode": "FEX-BUL-SJDM-CTR1-GY08", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Extension", "code": "CTR2", "rider": "GY09", "rtsCode": "FEX-BUL-SJDM-CTR2-GY09", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Assumption", 
        "variations": {"ASSUMPTION", "ASSUMPT10N", "ASUMPTION", "ASSUMPT1ON"},
        "districts": [
            {"name": "Main", "code": "ASM1", "rider": "GY10", "rtsCode": "FEX-BUL-SJDM-ASM1-GY10", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "ASM2", "rider": "GY11", "rtsCode": "FEX-BUL-SJDM-ASM2-GY11", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Dulong Bayan", 
        "variations": {"DULONG BAYAN", "DUL0NG BAYAN", "DULONG BAY4N", "DUL0NG B4YAN"},
        "districts": [
            {"name": "Proper", "code": "DLB1", "rider": "GY12", "rtsCode": "FEX-BUL-SJDM-DLB1-GY12", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "Extension", "code": "DLB2", "rider": "GY13", "rtsCode": "FEX-BUL-SJDM-DLB2-GY13", "variations": {"EXTENSION", "EXT", "EXTENS10N"}}
        ]
    },
    {
        "name": "Francisco Homes", 
        "variations": {"FRANCISCO HOMES", "FRANC1SCO HOMES", "FRANCISC0 H0MES", "FRANSISCO HOMES"},
        "districts": [
            {"name": "Guijo", "code": "FRH1", "rider": "GY14", "rtsCode": "FEX-BUL-SJDM-FRH1-GY14", "variations": {"GUIJO", "GU1JO", "GUIJ0"}},
            {"name": "Narra", "code": "FRH2", "rider": "GY15", "rtsCode": "FEX-BUL-SJDM-FRH2-GY15", "variations": {"NARRA", "NARA", "N4RRA"}},
            {"name": "Yakal", "code": "FRH3", "rider": "GY16", "rtsCode": "FEX-BUL-SJDM-FRH3-GY16", "variations": {"YAKAL", "YAK4L", "Y4KAL"}}
        ]
    },
    {
        "name": "Kaypian", 
        "variations": {"KAYPIAN", "K4YPIAN", "KAYP1AN", "K4YP14N"},
        "districts": [
            {"name": "Main", "code": "KYP1", "rider": "GY17", "rtsCode": "FEX-BUL-SJDM-KYP1-GY17", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "KYP2", "rider": "GY18", "rtsCode": "FEX-BUL-SJDM-KYP2-GY18", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}}
        ]
    },
    {
        "name": "Minuyan", 
        "variations": {"MINUYAN", "M1NUYAN", "MINUY4N", "M1NUY4N"},
        "districts": [
            {"name": "Proper", "code": "MNY1", "rider": "GY19", "rtsCode": "FEX-BUL-SJDM-MNY1-GY19", "variations": {"PROPER", "PR0PER", "PROP3R"}},
            {"name": "1st", "code": "MNY2", "rider": "GY20", "rtsCode": "FEX-BUL-SJDM-MNY2-GY20", "variations": {"1ST", "15T", "1S7"}},
            {"name": "2nd", "code": "MNY3", "rider": "GY21", "rtsCode": "FEX-BUL-SJDM-MNY3-GY21", "variations": {"2ND", "2N0", "2MD"}}
        ]
    },
            {"name": "Main", "code": "TKO1", "rider": "GY22", "rtsCode": "FEX-BUL-SJDM-TKO1-GY22", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision
    {
        "name": "Tungko", 
        "variations": {"TUNGKO", "TUNGK0", "TUNK0", "7UNGKO"},
        "districts": [
            {"name": "Main", "code": "TKO1", "rider": "GY22", "rtsCode": "FEX-BUL-SJDM-TKO1-GY22", "variations": {"MAIN", "M41N", "MA1N"}},
            {"name": "Subdivision", "code": "TKO2", "rider": "GY23", "rtsCode": "FEX-BUL-SJDM-TKO2-GY23", "variations": {"SUBDIVISION", "SUBDIV", "SUB0IV"}},
            {"name": "Proper", "code": "TKO3", "rider": "GY24", "rtsCode": "FEX-BUL-SJDM-TKO3-GY24", "variations": {"PROPER", "PR0PER", "PROP3R"}}
        ]
    },
