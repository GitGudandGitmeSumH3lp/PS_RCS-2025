"""Concurrent OCR load test for PS_RCS_PROJECT.

Spawns N threads, each sending a POST /api/ocr/analyze with a sample image.
Verifies all scans are stored and retrievable via /api/ocr/scans.
"""

import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

# Configuration
SERVER_URL = "http://192.168.100.23:5000"  # Use your server IP
NUM_REQUESTS = 10                          # Number of concurrent uploads
SAMPLE_IMAGE_PATH = r"F:\PORTFOLIO\ps_rcs_project\OCR_sim\images\receipt6.jpg"

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def send_ocr_request(thread_id):
    """Submit one OCR analysis request and poll for result."""
    print(f"[Thread {thread_id}] Starting...")
    
    # 1. Encode image
    image_b64 = encode_image(SAMPLE_IMAGE_PATH)
    
    # 2. POST /api/ocr/analyze
    resp = requests.post(
        f"{SERVER_URL}/api/ocr/analyze",
        json={"image_data": f"data:image/jpeg;base64,{image_b64}"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    scan_id = data["scan_id"]
    print(f"[Thread {thread_id}] Scan submitted: {scan_id}")
    
    # 3. Poll for results (max 30 seconds)
    start = time.time()
    while time.time() - start < 30:
        result_resp = requests.get(f"{SERVER_URL}/api/vision/results/{scan_id}", timeout=5)
        if result_resp.status_code == 200:
            result = result_resp.json()
            if result.get("status") == "completed":
                print(f"[Thread {thread_id}] Scan {scan_id} completed.")
                return scan_id, True
        elif result_resp.status_code == 404:
            time.sleep(0.5)
            continue
        else:
            print(f"[Thread {thread_id}] Unexpected status: {result_resp.status_code}")
            break
    print(f"[Thread {thread_id}] Scan {scan_id} timed out.")
    return scan_id, False

def main():
    print(f"Starting concurrent OCR test with {NUM_REQUESTS} threads...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=NUM_REQUESTS) as executor:
        futures = [
            executor.submit(send_ocr_request, i)
            for i in range(NUM_REQUESTS)
        ]
        
        results = []
        for future in as_completed(futures):
            scan_id, success = future.result()
            results.append((scan_id, success))
    
    elapsed = time.time() - start_time
    
    # 4. Verify all scans appear in history
    history_resp = requests.get(f"{SERVER_URL}/api/ocr/scans?limit={NUM_REQUESTS*2}")
    history_resp.raise_for_status()
    scans = history_resp.json().get("scans", [])
    stored_ids = {s["scan_id"] for s in scans}
    
    successful_ids = {scan_id for scan_id, success in results if success}
    missing_ids = successful_ids - stored_ids
    
    print("\n=== LOAD TEST RESULTS ===")
    print(f"Total time: {elapsed:.2f} seconds")
    print(f"Requests: {NUM_REQUESTS}")
    print(f"Successful completions: {len(successful_ids)}/{NUM_REQUESTS}")
    if missing_ids:
        print(f"❌ Scans missing from history: {missing_ids}")
    else:
        print("✅ All scans persisted to database.")
    
    # 5. Check server logs for lock errors (manual step)
    print("\n⚠️ Please check the Flask console for any:")
    print("   - 'database is locked' errors")
    print("   - 500/503 responses")
    print("   - 'DB save failed' messages")

if __name__ == "__main__":
    main()
