# ocr.py (V16 - Guaranteed Response & Final Polish)

import os
import sqlite3
import re
from datetime import datetime
import pytesseract
import Levenshtein
import time
import threading
import json
from queue import Queue
from flask import Flask, render_template, Response

from image_preprocessor import pipeline_for_ocr
from knowledge_base import VALID_RTS_CODES_WITH_PARTS, TYPO_CORRECTIONS, SCORE_THRESHOLD

# (Configuration and Database functions remain unchanged)
DATABASE_FILE = 'scanned_data.db'
IMAGE_FOLDER = 'images'
app = Flask(__name__)
TESSERTUPAC_CONFIG = "--oem 1 --psm 3"
clients = []
clients_lock = threading.Lock()

def broadcast_event(event, data):
    with clients_lock:
        for q in clients:
            q.put({"event": event, "data": data})

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scanned_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            image_name TEXT NOT NULL,
            status TEXT NOT NULL,
            rts_code TEXT,
            top_guess_code TEXT,
            top_guess_score INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# (clean_ocr_text and reconcile_and_correct functions remain unchanged)
def clean_ocr_text(text):
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if len(line) < 3: continue
        if sum(c.isalnum() for c in line) / len(line) < 0.5: continue
        clean_lines.append(line)
    return ' '.join(clean_lines)

def reconcile_and_correct(text):
    scores = {code: 0 for code in VALID_RTS_CODES_WITH_PARTS.keys()}
    words_in_text = re.split(r'[\s:-]+', text.upper())
    for code, parts in VALID_RTS_CODES_WITH_PARTS.items():
        for part in parts:
            for word in words_in_text:
                if Levenshtein.distance(part, word) <= 2:
                    scores[code] += 1
                    break
    best_match_code = max(scores, key=scores.get) if scores else None
    best_score = scores[best_match_code] if best_match_code else 0
    print(f"DEBUG: Top guess is '{best_match_code}' with a score of {best_score}")
    result = {"rts_code": None, "status": "Failed: Score too low", "top_guess_code": best_match_code, "top_guess_score": best_score}
    if best_score >= SCORE_THRESHOLD:
        result["rts_code"] = best_match_code
        result["status"] = f"Success: Guessed with Score {best_score}"
    return result

def process_single_image(image_path):
    image_name = os.path.basename(image_path)
    try:
        processed_img = processed_img = pipeline_for_ocr(image_path)
        raw_text = pytesseract.image_to_string(processed_img, config=TESSERTUPAC_CONFIG)
        sanitized_text = raw_text.encode('ascii', errors='ignore').decode('ascii')
        print("-" * 50)
        print(f"RAW (SANITIZED) OCR OUTPUT FOR: {image_name}")
        print(sanitized_text)
        print("-" * 50)
        clean_text = clean_ocr_text(sanitized_text)
        final_data = reconcile_and_correct(clean_text)
        conn = get_db_connection()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO scanned_labels (timestamp, image_name, status, rts_code, top_guess_code, top_guess_score) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (timestamp, image_name, final_data["status"], final_data["rts_code"], final_data["top_guess_code"], final_data["top_guess_score"])
        )
        conn.commit()
        final_data['id'] = cursor.lastrowid
        final_data['timestamp'] = timestamp
        final_data['image_name'] = image_name
        conn.close()
        return final_data
    except Exception as e:
        import traceback
        print(f"FATAL ERROR while processing {image_name}:")
        traceback.print_exc()
        return None

# --- HEAVILY UPGRADED Simulation Thread ---
def simulate_scanning():
    print("INFO: Starting background scanning simulation...")
    image_files = [os.path.join(IMAGE_FOLDER, f) for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('png', 'jpg', 'jpeg'))]
    if not image_files:
        print(f"WARNING: No images in '{IMAGE_FOLDER}'.")
        return

    current_index = 0
    while True:
        image_path = image_files[current_index]
        image_name = os.path.basename(image_path)
        scan_id = f"scan-{int(time.time() * 1000)}"

        broadcast_event("scan_start", {"image_name": image_name, "scan_id": scan_id})
        
        result = process_single_image(image_path)
        
        # --- THE FIX: ALWAYS BROADCAST A RESULT ---
        if result:
            result["scan_id"] = scan_id
            broadcast_event("scan_result", result)
        else:
            # If processing failed, create and send an error result
            error_result = {
                "scan_id": scan_id,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "image_name": image_name,
                "status": "FATAL: Processing Error",
                "rts_code": "---",
                "top_guess_code": "---",
                "top_guess_score": 0
            }
            broadcast_event("scan_result", error_result)
        
        current_index = (current_index + 1) % len(image_files)
        time.sleep(5)

# (Flask routes and main block remain unchanged)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream')
def stream():
    def event_stream():
        q = Queue()
        with clients_lock:
            clients.append(q)
        print(f"INFO: Client connected. Total clients: {len(clients)}")
        try:
            while True:
                event_data = q.get()
                event = event_data['event']
                data = json.dumps(event_data['data'])
                yield f"event: {event}\ndata: {data}\n\n"
        finally:
            with clients_lock:
                clients.remove(q)
            print(f"INFO: Client disconnected. Total clients: {len(clients)}")
    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    if not os.path.exists(IMAGE_FOLDER):
        os.makedirs(IMAGE_FOLDER)
    init_db()
    scanner_thread = threading.Thread(target=simulate_scanning, daemon=True)
    scanner_thread.start()
    print("INFO: Starting Flask web server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)