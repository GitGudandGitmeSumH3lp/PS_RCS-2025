# ocr_handler.py
# OCR handler with RTS Sort Logic

import cv2
import pytesseract
import numpy as np
import re
import time
import logging
from datetime import datetime

# ----------------------------
# CONFIGURATION
# ----------------------------
RTS_PATTERN = r"RTS-[A-Z0-9-]+"  # Pattern for RTS codes
MIN_CONFIDENCE = 60  # OCR confidence threshold (%)

# RTS Sort Code Map
RTS_MAP = {
    "Muzon": {
        "North": "RTS-BUL-SJDM-MZN1-A1",
        "South": "RTS-BUL-SJDM-MZN2-A2",
        "Central": "RTS-BUL-SJDM-MZN3-A3"
    },
    "Tungko": {
        "Main": "RTS-BUL-SJDM-TKM-B1",
        "Subdivision": "RTS-BUL-SJDM-TKM-B2"
    },
    "Sapang Palay": {
        "West": "RTS-BUL-SJDM-SPY1-C1",
        "East": "RTS-BUL-SJDM-SPY2-C2"
    },
    "Santa Maria": "RTS-BUL-STM-SMR-D1",
    "Norzagaray": "RTS-BUL-NRY-NRY-D2"
}

# Predefined keywords to guide region-of-interest
KEYWORDS = [
    "Order ID", "Tracking Number", "Buyer Name", "Address",
    "Weight", "Quantity", "RTS Code", "Barangay", "District"
]

class OCRHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Set Tesseract path if needed
        # pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

    # ----------------------------
    # IMAGE PREPROCESSING
    # ----------------------------
    def preprocess_image(self, image_path):
        """Load and preprocess image for better OCR."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise FileNotFoundError(f"Image not found: {image_path}")

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Enhance contrast (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)

            # Noise reduction
            denoised = cv2.medianBlur(enhanced, 3)

            # Threshold: binary + inverse (text white on black)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            return thresh
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {e}")
            return None

    # ----------------------------
    # TEXT DETECTION
    # ----------------------------
    def extract_text_with_sort_logic(self, image_path):
        """
        Use SORT-inspired logic to extract text efficiently.
        """
        preprocessed = self.preprocess_image(image_path)
        if preprocessed is None:
            return None

        # Use Tesseract with bounding box data
        data = pytesseract.image_to_data(
            preprocessed,
            config='--psm 6',  # Assume uniform block of text
            output_type=pytesseract.Output.DICT
        )

        n_boxes = len(data['text'])
        detections = []

        # Step 1: Collect all high-confidence detections
        for i in range(n_boxes):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]

            if conf > MIN_CONFIDENCE and len(text) > 0:
                detections.append({
                    'text': text,
                    'conf': conf,
                    'bbox': (x, y, w, h)
                })

        # Sort left-to-right, top-to-bottom (like reading order)
        detections.sort(key=lambda d: (d['bbox'][1], d['bbox'][0]))

        # Step 2: Build structured data
        result = {
            'order_id': '',
            'tracking_number': '',
            'buyer_name': '',
            'address': '',
            'weight': '',
            'quantity': '',
            'rts_code': '',
            'barangay': '',
            'district': '',
            'timestamp': datetime.now().isoformat()
        }

        # First: Look for RTS Code directly
        for det in detections:
            match = re.search(RTS_PATTERN, det['text'])
            if match:
                result['rts_code'] = match.group()
                self.logger.info(f"🎯 RTS Code found: {result['rts_code']}")
                break

        # If not found, infer from barangay/district
        if not result['rts_code']:
            # Look for barangay
            for det in detections:
                txt = det['text']
                if txt in RTS_MAP:
                    result['barangay'] = txt
                    break

            # Look for district
            for det in detections:
                txt = det['text']
                if result['barangay'] and result['barangay'] in RTS_MAP:
                    district_map = RTS_MAP[result['barangay']]
                    if isinstance(district_map, dict):
                        for d in district_map:
                            if d.lower() in txt.lower():
                                result['district'] = d
                                break

            # Now generate RTS code
            if result['barangay']:
                code = RTS_MAP[result['barangay']]
                if isinstance(code, dict) and result['district']:
                    code = code[result['district']]
                result['rts_code'] = code

        # Extract other fields by keyword proximity
        for i, det in enumerate(detections):
            txt = det['text']

            if "Order" in txt and "ID" in [detections[min(i+j, len(detections)-1)]['text'] for j in range(1, 4)]:
                result['order_id'] = self._get_next_text(detections, i)
            elif "Tracking" in txt and "Number" in [detections[min(i+j, len(detections)-1)]['text'] for j in range(1, 4)]:
                result['tracking_number'] = self._get_next_text(detections, i)
            elif "Buyer" in txt and "Name" in [detections[min(i+j, len(detections)-1)]['text'] for j in range(1, 4)]:
                result['buyer_name'] = self._get_next_text(detections, i)
            elif "Address" in txt:
                result['address'] = self._get_next_text(detections, i)
            elif "Weight" in txt:
                result['weight'] = ''.join(filter(str.isdigit, self._get_next_text(detections, i)))
            elif "Quantity" in txt:
                result['quantity'] = ''.join(filter(str.isdigit, self._get_next_text(detections, i)))

        return result

    def _get_next_text(self, detections, idx):
        """Get the next non-keyword text after a label."""
        for i in range(idx + 1, min(idx + 5, len(detections))):
            t = detections[i]['text'].strip()
            if t and not any(k.lower() in t.lower() for k in KEYWORDS):
                return t
        return ""

    # ----------------------------
    # PUBLIC API
    # ----------------------------
    def process_image(self, image_path):
        """Main method: extract data from image."""
        self.logger.info(f"Processing image: {image_path}")
        result = self.extract_text_with_sort_logic(image_path)
        if result:
            self.logger.info(f"Extracted: {result}")
        else:
            self.logger.error("Failed to extract data.")
        return result

# Example usage
if __name__ == "__main__":
    ocr = OCRHandler()
    result = ocr.process_image("test_label.png")  # Replace with actual image path
    if result:
        print("OCR Result:")
        for key, value in result.items():
            print(f"  {key}: {value}")