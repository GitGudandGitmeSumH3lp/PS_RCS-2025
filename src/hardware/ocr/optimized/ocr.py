# ocr_optimized.py - High-Performance OCR System
import os
import sqlite3
import asyncio
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass
from functools import lru_cache
import time

# External dependencies
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import Levenshtein
from flask import Flask, jsonify, render_template
from flask_caching import Cache

from knowledge_base_optimized import (
    RTSCodeMatcher, FIELD_PATTERNS, TYPO_CORRECTIONS, 
    RTS_CODE_TO_ADDRESS, VALID_RTS_CODES
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    success: bool
    image_name: str
    rts_code: Optional[str] = None
    barangay: Optional[str] = None
    district: Optional[str] = None
    order_id: Optional[str] = None
    status: str = ""
    confidence: str = "0/7"
    confidence_details: List[str] = None
    processing_time: float = 0.0
    error: Optional[str] = None

class DatabaseManager:
    """Thread-safe database operations with connection pooling"""
    
    def __init__(self, db_file: str, pool_size: int = 5):
        self.db_file = db_file
        self.pool_size = pool_size
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self):
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_file, 
                check_same_thread=False,
                timeout=30.0
            )
            # Performance optimizations
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA cache_size=10000")
            self._local.connection.execute("PRAGMA temp_store=memory")
        return self._local.connection
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scanned_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                image_name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                confidence TEXT NOT NULL,
                corrected_rts_code TEXT,
                validated_barangay TEXT,
                validated_district TEXT,
                validated_order_id TEXT,
                processing_time REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX(image_name),
                INDEX(timestamp)
            )
        ''')
        conn.commit()
        conn.close()
    
    def insert_result(self, result: ProcessingResult):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO scanned_labels 
                (timestamp, image_name, status, confidence, corrected_rts_code, 
                 validated_barangay, validated_district, validated_order_id, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp, result.image_name, result.status, result.confidence,
                result.rts_code, result.barangay, result.district, 
                result.order_id, result.processing_time
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Database insert failed: {e}")
            raise
    
    def get_all_records(self) -> List[Dict]:
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scanned_labels ORDER BY id DESC LIMIT 1000")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Database select failed: {e}")
            return []

class AdvancedImageProcessor:
    """High-performance image preprocessing with multiple enhancement techniques"""
    
    @staticmethod
    @lru_cache(maxsize=32)
    def get_optimal_tesseract_config(image_type: str = "label") -> str:
        """Return optimized Tesseract configuration based on image type"""
        configs = {
            "label": "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-:",
            "document": "--oem 1 --psm 3",
            "single_line": "--oem 3 --psm 7"
        }
        return configs.get(image_type, configs["label"])
    
    @staticmethod
    def preprocess_image_advanced(image_path: str) -> np.ndarray:
        """Advanced image preprocessing pipeline for optimal OCR"""
        # Read image with OpenCV for better performance
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Noise reduction
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Adaptive thresholding for better text extraction
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up text
        kernel = np.ones((1, 1), np.uint8)
        processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Resize for consistent OCR performance
        height, width = processed.shape
        if width < 1500:  # Upscale small images
            scale = 1500 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return processed
    
    @staticmethod
    def extract_text_regions(image: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """Extract potential text regions for targeted OCR"""
        # Find contours
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_regions = []
        height, width = image.shape
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size (potential text regions)
            if 20 < w < width * 0.8 and 10 < h < height * 0.3:
                region = image[y:y+h, x:x+w]
                # Determine region type based on dimensions
                region_type = "single_line" if h < 50 else "label"
                text_regions.append((region_type, region))
        
        # If no regions found, use the whole image
        if not text_regions:
            text_regions.append(("label", image))
        
        return text_regions

class SmartTextExtractor:
    """Intelligent text extraction and field parsing"""
    
    def __init__(self):
        self.rts_matcher = RTSCodeMatcher()
    
    @lru_cache(maxsize=1000)
    def apply_typo_corrections_cached(self, text: str) -> str:
        """Cached version of typo corrections for performance"""
        corrected = text
        for error, correction in TYPO_CORRECTIONS.items():
            corrected = corrected.replace(error, correction)
        return corrected
    
    def extract_text_multipass(self, image: np.ndarray) -> str:
        """Multi-pass OCR extraction for maximum accuracy"""
        processor = AdvancedImageProcessor()
        
        # Get text regions
        regions = processor.extract_text_regions(image)
        
        all_text = []
        for region_type, region_img in regions:
            config = processor.get_optimal_tesseract_config(region_type)
            try:
                text = pytesseract.image_to_string(region_img, config=config)
                if text.strip():
                    all_text.append(text)
            except Exception as e:
                logger.warning(f"OCR failed for region: {e}")
        
        # Fallback to full image OCR if regions failed
        if not all_text:
            config = processor.get_optimal_tesseract_config("label")
            try:
                full_text = pytesseract.image_to_string(image, config=config)
                all_text.append(full_text)
            except Exception as e:
                logger.error(f"Full image OCR failed: {e}")
                return ""
        
        return "\n".join(all_text)
    
    def extract_all_fields(self, text: str) -> Dict[str, Any]:
        """Extract all fields with enhanced pattern matching"""
        extracted = {}
        clean_text = self.apply_typo_corrections_cached(
            text.upper().encode('ascii', 'ignore').decode('utf-8')
        )
        
        # Extract using patterns
        for key, pattern in FIELD_PATTERNS.items():
            matches = pattern.findall(clean_text)
            if matches:
                if key == "address" and matches:
                    extracted[key] = matches[0] if len(matches[0]) == 2 else matches[0]
                else:
                    extracted[key] = matches[0] if isinstance(matches[0], str) else matches[0]
        
        return extracted

class IntelligentReconciler:
    """Advanced data reconciliation and validation"""
    
    def __init__(self):
        self.rts_matcher = RTSCodeMatcher()
    
    def reconcile_and_correct(self, data: Dict[str, Any]) -> ProcessingResult:
        """Advanced reconciliation with confidence scoring"""
        result = ProcessingResult(
            success=True,
            image_name="",
            confidence_details=[]
        )
        
        confidence = 0
        status_parts = []
        
        # Validate basic fields
        if data.get("tracking_number"):
            confidence += 1
            result.confidence_details.append("Valid Tracking# Format")
        
        if data.get("ph_number"):
            confidence += 1
            result.confidence_details.append("Valid PH# Format")
        
        if data.get("order_id"):
            result.order_id = data["order_id"]
            confidence += 1
            result.confidence_details.append("Valid OrderID Format")
        
        # Advanced RTS code matching
        rts_candidate = data.get("rts_code_label") or data.get("rts_code_pattern")
        if rts_candidate:
            best_match = self.rts_matcher.find_best_match(rts_candidate)
            if best_match:
                result.rts_code = best_match
                confidence += 3
                result.confidence_details.append("RTS Code Matched")
                status_parts.append("RTS Code Corrected")
                
                # Get expected address
                expected = RTS_CODE_TO_ADDRESS[best_match]
                result.barangay = expected["barangay"]
                result.district = expected["district"]
                
                # Validate against extracted address
                if data.get("address"):
                    addr_confidence = self._validate_address(data["address"], expected)
                    if addr_confidence > 0.7:
                        confidence += 2
                        result.confidence_details.append("Address Cross-Validated")
                        status_parts.append("Address Validated")
                    else:
                        status_parts.append("Address Corrected by RTS")
                else:
                    status_parts.append("Address Inferred from RTS")
        
        result.confidence = f"{confidence}/7"
        result.status = ", ".join(status_parts) if status_parts else "Extraction Failed"
        
        return result
    
    def _validate_address(self, extracted_addr: Any, expected: Dict[str, str]) -> float:
        """Calculate address validation confidence"""
        if not extracted_addr:
            return 0.0
        
        if isinstance(extracted_addr, (list, tuple)) and len(extracted_addr) >= 2:
            brgy_raw, dist_raw = str(extracted_addr[0]), str(extracted_addr[1])
        else:
            # Try to parse string format
            addr_str = str(extracted_addr)
            parts = addr_str.split(',')
            if len(parts) >= 2:
                brgy_raw, dist_raw = parts[0].strip(), parts[1].strip()
            else:
                return 0.0
        
        # Calculate similarity scores
        brgy_score = 1.0 - (Levenshtein.distance(
            brgy_raw.upper(), expected["barangay"].upper()
        ) / max(len(brgy_raw), len(expected["barangay"])))
        
        dist_score = 1.0 - (Levenshtein.distance(
            dist_raw.upper(), expected["district"].upper()
        ) / max(len(dist_raw), len(expected["district"])))
        
        return (brgy_score + dist_score) / 2

class HighPerformanceOCRProcessor:
    """Main processing class with parallel execution capabilities"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.db_manager = DatabaseManager('scanned_data.db')
        self.image_processor = AdvancedImageProcessor()
        self.text_extractor = SmartTextExtractor()
        self.reconciler = IntelligentReconciler()
        
        # Thread pool for I/O bound operations
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        # Process pool for CPU intensive operations
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers//2)
    
    def process_single_image(self, image_path: str) -> ProcessingResult:
        """Process a single image with full error handling and timing"""
        start_time = time.time()
        image_name = os.path.basename(image_path)
        
        try:
            # Preprocess image
            processed_img = self.image_processor.preprocess_image_advanced(image_path)
            
            # Extract text using multi-pass approach
            raw_text = self.text_extractor.extract_text_multipass(processed_img)
            
            if not raw_text.strip():
                return ProcessingResult(
                    success=False,
                    image_name=image_name,
                    error="No text extracted from image",
                    processing_time=time.time() - start_time
                )
            
            # Extract fields
            extracted_data = self.text_extractor.extract_all_fields(raw_text)
            
            # Reconcile and validate
            result = self.reconciler.reconcile_and_correct(extracted_data)
            result.image_name = image_name
            result.processing_time = time.time() - start_time
            
            # Save to database
            self.db_manager.insert_result(result)
            
            logger.info(f"Processed {image_name} in {result.processing_time:.2f}s - {result.status}")
            return result
            
        except Exception as e:
            error_msg = str(e).encode('ascii', 'ignore').decode('utf-8')
            logger.error(f"Error processing {image_name}: {error_msg}")
            
            return ProcessingResult(
                success=False,
                image_name=image_name,
                error=error_msg,
                processing_time=time.time() - start_time
            )
    
    def process_batch(self, image_paths: List[str]) -> List[ProcessingResult]:
        """Process multiple images in parallel"""
        if not image_paths:
            return []
        
        logger.info(f"Starting batch processing of {len(image_paths)} images")
        start_time = time.time()
        
        # Use ThreadPoolExecutor for I/O bound operations
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.process_single_image, image_paths))
        
        total_time = time.time() - start_time
        successful = sum(1 for r in results if r.success)
        
        logger.info(f"Batch completed: {successful}/{len(image_paths)} successful in {total_time:.2f}s")
        return results

# Flask Application with Caching and Performance Optimizations
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Global state
IMAGE_FOLDER = 'images'
processor = HighPerformanceOCRProcessor(max_workers=4)
IMAGE_FILES = []
current_image_index = 0
processing_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan_image():
    global current_image_index
    
    if not IMAGE_FILES:
        return jsonify({"error": "No images found in 'images' folder."}), 404
    
    with processing_lock:
        image_to_process = IMAGE_FILES[current_image_index]
        current_image_index = (current_image_index + 1) % len(IMAGE_FILES)
    
    result = processor.process_single_image(image_to_process)
    
    response_data = {
        "success": result.success,
        "image_name": result.image_name,
        "status": result.status,
        "confidence": result.confidence,
        "corrected_rts_code": result.rts_code,
        "validated_barangay": result.barangay,
        "validated_district": result.district,
        "validated_order_id": result.order_id,
        "processing_time": f"{result.processing_time:.2f}s"
    }
    
    if not result.success:
        response_data["error"] = result.error
        return jsonify(response_data), 500
    
    return jsonify(response_data), 200

@app.route('/data')
@cache.cached(timeout=30)  # Cache for 30 seconds
def get_data():
    records = processor.db_manager.get_all_records()
    return jsonify(records)

@app.route('/batch_scan', methods=['POST'])
def batch_scan():
    """Process all images in batch mode"""
    if not IMAGE_FILES:
        return jsonify({"error": "No images found"}), 404
    
    results = processor.process_batch(IMAGE_FILES)
    summary = {
        "total_processed": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "average_time": sum(r.processing_time for r in results) / len(results) if results else 0
    }
    
    return jsonify(summary), 200

@app.route('/stats')
def get_stats():
    """Get processing statistics"""
    records = processor.db_manager.get_all_records()
    if not records:
        return jsonify({"message": "No data available"})
    
    stats = {
        "total_images": len(records),
        "success_rate": sum(1 for r in records if "Failed" not in r.get('status', '')) / len(records) * 100,
        "average_confidence": sum(float(r.get('confidence', '0/7').split('/')[0]) for r in records) / len(records),
        "average_processing_time": sum(r.get('processing_time', 0) for r in records if r.get('processing_time')) / len(records)
    }
    
    return jsonify(stats)

def initialize_application():
    """Initialize the application with error handling"""
    global IMAGE_FILES
    
    try:
        if not os.path.exists(IMAGE_FOLDER):
            os.makedirs(IMAGE_FOLDER)
            logger.warning(f"Created {IMAGE_FOLDER} directory")
        
        IMAGE_FILES = [
            os.path.join(IMAGE_FOLDER, f) 
            for f in os.listdir(IMAGE_FOLDER) 
            if f.lower().endswith(('png', 'jpg', 'jpeg', 'tiff', 'bmp'))
        ]
        
        if not IMAGE_FILES:
            logger.warning(f"No images found in '{IMAGE_FOLDER}'")
        else:
            logger.info(f"Found {len(IMAGE_FILES)} images to process")
            
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise

if __name__ == '__main__':
    initialize_application()
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)