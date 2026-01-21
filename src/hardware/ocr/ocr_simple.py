# ocr_simple.py - Simplified version for immediate compatibility

import os
import sqlite3
import time
from datetime import datetime
from PIL import Image, ImageEnhance
import cv2
import numpy as np
import pytesseract
import Levenshtein
from flask import Flask, jsonify, render_template_string
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simplified knowledge base - inline to avoid import issues
VALID_RTS_CODES = [
    "FEX-BUL-SJDM-MZN1-GY01", "FEX-BUL-SJDM-MZN2-GY02", 
    "FEX-BUL-SJDM-MZN3-GY03", "FEX-BUL-SJDM-MZN4-GY04",
    "FEX-BUL-SJDM-GRC1-GY05", "FEX-BUL-SJDM-GRC2-GY06", 
    "FEX-BUL-SJDM-GRC3-GY07", "FEX-BUL-SJDM-CTR1-GY08",
    "FEX-BUL-SJDM-CTR2-GY09", "FEX-BUL-SJDM-ASM1-GY10",
    "FEX-BUL-SJDM-ASM2-GY11", "FEX-BUL-SJDM-DLB1-GY12",
    "FEX-BUL-SJDM-DLB2-GY13", "FEX-BUL-SJDM-FRH1-GY14",
    "FEX-BUL-SJDM-FRH2-GY15", "FEX-BUL-SJDM-FRH3-GY16",
    "FEX-BUL-SJDM-KYP1-GY17", "FEX-BUL-SJDM-KYP2-GY18",
    "FEX-BUL-SJDM-MNY1-GY19", "FEX-BUL-SJDM-MNY2-GY20",
    "FEX-BUL-SJDM-MNY3-GY21", "FEX-BUL-SJDM-TKO1-GY22",
    "FEX-BUL-SJDM-TKO2-GY23"
]

RTS_CODE_TO_ADDRESS = {
    "FEX-BUL-SJDM-MZN1-GY01": {"barangay": "Muzon", "district": "North"},
    "FEX-BUL-SJDM-MZN2-GY02": {"barangay": "Muzon", "district": "South"},
    "FEX-BUL-SJDM-MZN3-GY03": {"barangay": "Muzon", "district": "Central"},
    "FEX-BUL-SJDM-MZN4-GY04": {"barangay": "Muzon", "district": "Proper"},
    "FEX-BUL-SJDM-GRC1-GY05": {"barangay": "Graceville", "district": "Subdivision"},
    "FEX-BUL-SJDM-GRC2-GY06": {"barangay": "Graceville", "district": "Main"},
    "FEX-BUL-SJDM-GRC3-GY07": {"barangay": "Graceville", "district": "Commercial"},
    "FEX-BUL-SJDM-CTR1-GY08": {"barangay": "Citrus", "district": "Main"},
    "FEX-BUL-SJDM-CTR2-GY09": {"barangay": "Citrus", "district": "Extension"},
    "FEX-BUL-SJDM-ASM1-GY10": {"barangay": "Assumption", "district": "Main"},
    "FEX-BUL-SJDM-ASM2-GY11": {"barangay": "Assumption", "district": "Subdivision"},
    "FEX-BUL-SJDM-DLB1-GY12": {"barangay": "Dulong Bayan", "district": "Proper"},
    "FEX-BUL-SJDM-DLB2-GY13": {"barangay": "Dulong Bayan", "district": "Extension"},
    "FEX-BUL-SJDM-FRH1-GY14": {"barangay": "Francisco Homes", "district": "Guijo"},
    "FEX-BUL-SJDM-FRH2-GY15": {"barangay": "Francisco Homes", "district": "Narra"},
    "FEX-BUL-SJDM-FRH3-GY16": {"barangay": "Francisco Homes", "district": "Yakal"},
    "FEX-BUL-SJDM-KYP1-GY17": {"barangay": "Kaypian", "district": "Main"},
    "FEX-BUL-SJDM-KYP2-GY18": {"barangay": "Kaypian", "district": "Subdivision"},
    "FEX-BUL-SJDM-MNY1-GY19": {"barangay": "Minuyan", "district": "Proper"},
    "FEX-BUL-SJDM-MNY2-GY20": {"barangay": "Minuyan", "district": "1st"},
    "FEX-BUL-SJDM-MNY3-GY21": {"barangay": "Minuyan", "district": "2nd"},
    "FEX-BUL-SJDM-TKO1-GY22": {"barangay": "Tungko", "district": "Main"},
    "FEX-BUL-SJDM-TKO2-GY23": {"barangay": "Tungko", "district": "Subdivision"}
}

import re

FIELD_PATTERNS = {
    "tracking_number": re.compile(r'\bFE\d{10}\b'),
    "ph_number": re.compile(r'\bFE \d{12}\b'),
    "order_id": re.compile(r'(?:Order|drder|0rder) I[D0]: ?(FE\d{6}[A-Z0-9]{6})', re.IGNORECASE),
    "rts_code_label": re.compile(r'RTS Sort.*?Code:\s*([A-Z0-9-]+)', re.IGNORECASE),
    "rts_code_pattern": re.compile(r'\b(FEX-[A-Z0-9-]{18,})\b', re.IGNORECASE),
    "address": re.compile(r'(?:Brgy|8rgy)\.? ([\w\s\(\)]+?)\s+([\w\s]+?),', re.IGNORECASE)
}

TYPO_CORRECTIONS = {
    'DRDER': 'ORDER', '5': 'S', '0': 'O', '1': 'I', '8': 'B',
    'C0DE': 'CODE', 'RT5': 'RTS', 'F3X': 'FEX', '8UL': 'BUL'
}

# Configuration
DATABASE_FILE = 'scanned_data.db'
IMAGE_FOLDER = 'images'
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

def init_db():
    """Initialize database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scanned_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            image_name TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence TEXT NOT NULL,
            corrected_rts_code TEXT,
            validated_barangay TEXT,
            validated_district TEXT,
            validated_order_id TEXT,
            processing_time REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

def preprocess_image_simple(image_path):
    """Simple but effective image preprocessing"""
    try:
        # Read with OpenCV for better performance
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Resize if too small
        height, width = binary.shape
        if width < 1200:
            scale = 1200 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            binary = cv2.resize(binary, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return binary
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        # Fallback to PIL
        img = Image.open(image_path).convert('L')
        img = img.resize((1200, int(img.height * 1200 / img.width)), Image.LANCZOS)
        return np.array(img)

def apply_typo_corrections(text):
    """Apply typo corrections"""
    for error, correction in TYPO_CORRECTIONS.items():
        text = text.replace(error, correction)
    return text

def extract_all_fields(text):
    """Extract fields from text"""
    extracted = {}
    for key, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            if len(match.groups()) > 1:
                extracted[key] = match.groups()
            else:
                extracted[key] = match.group(1) if match.groups() else match.group(0)
    return extracted

def find_best_rts_match(candidate, max_distance=5):
    """Find best RTS code match"""
    if not candidate:
        return None
    
    candidate = candidate.strip().upper()
    
    # Exact match first
    if candidate in VALID_RTS_CODES:
        return candidate
    
    # Fuzzy matching
    best_match = None
    best_distance = float('inf')
    
    for code in VALID_RTS_CODES:
        distance = Levenshtein.distance(candidate, code)
        if distance < best_distance and distance <= max_distance:
            best_distance = distance
            best_match = code
    
    return best_match

def reconcile_and_correct(data):
    """Reconcile and correct extracted data"""
    result = {
        "rts_code": None, "barangay": None, "district": None, 
        "order_id": data.get("order_id"), "status": [], "confidence_details": []
    }
    
    confidence = 0
    
    # Basic field validation
    if data.get("tracking_number"):
        confidence += 1
        result["confidence_details"].append("Valid Tracking# Format")
    if data.get("ph_number"):
        confidence += 1
        result["confidence_details"].append("Valid PH# Format")
    if result["order_id"]:
        confidence += 1
        result["confidence_details"].append("Valid OrderID Format")

    # RTS code matching
    rts_candidate = data.get("rts_code_label") or data.get("rts_code_pattern")
    if rts_candidate:
        best_match = find_best_rts_match(rts_candidate)
        if best_match:
            result["rts_code"] = best_match
            result["status"].append("RTS Code Corrected")
            confidence += 3
            result["confidence_details"].append("RTS Code Match")
            
            # Get expected address
            expected_address = RTS_CODE_TO_ADDRESS[best_match]
            result["barangay"] = expected_address["barangay"]
            result["district"] = expected_address["district"]
            result["status"].append("Address Inferred from RTS")

    result["final_confidence"] = f"{confidence}/7"
    result["status"] = ", ".join(result["status"]) if result["status"] else "Extraction Failed"
    return result

def process_single_image(image_path):
    """Process a single image"""
    start_time = time.time()
    image_name = os.path.basename(image_path)
    
    try:
        # Preprocess image
        processed_img = preprocess_image_simple(image_path)
        
        # OCR extraction
        tesseract_config = "--oem 3 --psm 6"
        raw_text = pytesseract.image_to_string(processed_img, config=tesseract_config)
        
        if not raw_text.strip():
            return {
                "success": False,
                "image_name": image_name,
                "error": "No text extracted",
                "processing_time": time.time() - start_time
            }
        
        # Process text
        clean_text = apply_typo_corrections(raw_text.upper())
        raw_data = extract_all_fields(clean_text)
        final_data = reconcile_and_correct(raw_data)
        
        processing_time = time.time() - start_time
        
        # Save to database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            """INSERT INTO scanned_labels (timestamp, image_name, status, confidence, 
               corrected_rts_code, validated_barangay, validated_district, 
               validated_order_id, processing_time) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, image_name, final_data["status"], final_data["final_confidence"],
             final_data["rts_code"], final_data["barangay"], final_data["district"], 
             final_data["order_id"], processing_time)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Processed {image_name} in {processing_time:.2f}s - {final_data['status']}")
        
        response_data = final_data.copy()
        response_data["success"] = True
        response_data["image_name"] = image_name
        response_data["processing_time"] = f"{processing_time:.2f}s"
        return response_data
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing {image_name}: {error_msg}")
        return {
            "success": False,
            "image_name": image_name,
            "error": error_msg,
            "processing_time": time.time() - start_time
        }

# Global variables
IMAGE_FILES = []
current_image_index = 0

# Simple HTML template - inline to avoid template file issues
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>OCR System - Simple</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .controls { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .btn { background: #3498db; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; margin-right: 10px; font-size: 14px; }
        .btn:hover { background: #2980b9; }
        .btn:disabled { background: #bdc3c7; cursor: not-allowed; }
        .status { padding: 15px; margin: 10px 0; border-radius: 4px; font-weight: bold; }
        .status-info { background: #d4edda; color: #155724; }
        .status-success { background: #d1ecf1; color: #0c5460; }
        .status-error { background: #f8d7da; color: #721c24; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #34495e; color: white; }
        tr:hover { background: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 OCR Processing System</h1>
            <p>Simple and Fast Document Processing</p>
        </div>
        
        <div class="controls">
            <button id="scan-button" class="btn">📸 Scan Next Image</button>
            <button id="refresh-button" class="btn">🔄 Refresh Data</button>
            <div id="status" class="status status-info">Ready to process images</div>
        </div>
        
        <table id="data-table">
            <thead>
                <tr>
                    <th>ID</th><th>Timestamp</th><th>Image</th><th>Status</th><th>Confidence</th>
                    <th>RTS Code</th><th>Barangay</th><th>District</th><th>Order ID</th><th>Time</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    </div>

    <script>
        const scanButton = document.getElementById('scan-button');
        const refreshButton = document.getElementById('refresh-button');
        const statusDiv = document.getElementById('status');
        const dataTableBody = document.querySelector('#data-table tbody');

        function setStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = 'status status-' + type;
        }

        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                
                dataTableBody.innerHTML = '';
                data.forEach(item => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${item.id}</td>
                        <td>${item.timestamp}</td>
                        <td><strong>${item.image_name}</strong></td>
                        <td>${item.status}</td>
                        <td>${item.confidence}</td>
                        <td>${item.corrected_rts_code || 'N/A'}</td>
                        <td>${item.validated_barangay || 'N/A'}</td>
                        <td>${item.validated_district || 'N/A'}</td>
                        <td>${item.validated_order_id || 'N/A'}</td>
                        <td>${item.processing_time ? parseFloat(item.processing_time).toFixed(2) + 's' : 'N/A'}</td>
                    `;
                    dataTableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error fetching data:', error);
                setStatus('Error fetching data', 'error');
            }
        }

        scanButton.addEventListener('click', async () => {
            scanButton.disabled = true;
            scanButton.textContent = '⏳ Processing...';
            setStatus('Scanning in progress...', 'info');
            
            try {
                const response = await fetch('/scan', { method: 'POST' });
                const result = await response.json();

                if (response.ok && result.success) {
                    let statusType = result.status.includes('Failed') ? 'error' : 'success';
                    setStatus(`✅ Processed ${result.image_name}. ${result.status}`, statusType);
                    fetchData();
                } else {
                    setStatus(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                setStatus('🚫 Failed to communicate with server', 'error');
            } finally {
                scanButton.disabled = false;
                scanButton.textContent = '📸 Scan Next Image';
            }
        });

        refreshButton.addEventListener('click', fetchData);
        
        // Auto-refresh every 30 seconds
        setInterval(fetchData, 30000);
        fetchData();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scan', methods=['POST'])
def scan_image():
    global current_image_index
    
    if not IMAGE_FILES:
        return jsonify({"error": "No images found in 'images' folder."}), 404
    
    image_to_process = IMAGE_FILES[current_image_index]
    result = process_single_image(image_to_process)
    current_image_index = (current_image_index + 1) % len(IMAGE_FILES)
    
    status_code = 200 if result.get("success") else 500
    return jsonify(result), status_code

@app.route('/data')
def get_data():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scanned_labels ORDER BY id DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

if __name__ == '__main__':
    try:
        # Initialize directories
        if not os.path.exists(IMAGE_FOLDER):
            os.makedirs(IMAGE_FOLDER)
            print(f"Created '{IMAGE_FOLDER}' directory")
        
        # Find images
        IMAGE_FILES = [
            os.path.join(IMAGE_FOLDER, f) 
            for f in os.listdir(IMAGE_FOLDER) 
            if f.lower().endswith(('png', 'jpg', 'jpeg', 'tiff', 'bmp'))
        ]
        
        if not IMAGE_FILES:
            print(f"WARNING: No images found in '{IMAGE_FOLDER}'.")
            print("Please add some images to the 'images' directory.")
        else:
            print(f"Found {len(IMAGE_FILES)} images to process.")
        
        # Initialize database
        init_db()
        print("Database initialized successfully.")
        
        # Test OpenCV
        test_img = np.zeros((100, 100), dtype=np.uint8)
        cv2.fastNlMeansDenoising(test_img)
        print("OpenCV working correctly.")
        
        # Start Flask app
        print("Starting OCR system...")
        print("Access the web interface at: http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5005)
        
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install required packages:")
        print("pip install opencv-python pillow pytesseract python-levenshtein flask")
    except Exception as e:
        print(f"Startup error: {e}")
        print("Please check your setup and try again.")