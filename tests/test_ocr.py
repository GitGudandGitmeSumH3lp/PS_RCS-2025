# test_ocr.py
# Unit tests for OCR handler

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import ocr_handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from ocr_handler import OCRHandler

class TestOCRHandler(unittest.TestCase):
    def setUp(self):
        self.ocr = OCRHandler()

    @patch('ocr_handler.cv2.imread')
    def test_preprocess_image_success(self, mock_imread):
        mock_image = Mock()
        mock_imread.return_value = mock_image
        
        # Mock cv2 functions
        with patch('ocr_handler.cv2.cvtColor'), \
             patch('ocr_handler.cv2.createCLAHE'), \
             patch('ocr_handler.cv2.medianBlur'), \
             patch('ocr_handler.cv2.threshold'):
            
            result = self.ocr.preprocess_image("test_image.png")
            self.assertIsNotNone(result)

    @patch('ocr_handler.cv2.imread')
    def test_preprocess_image_failure(self, mock_imread):
        mock_imread.return_value = None
        
        result = self.ocr.preprocess_image("nonexistent_image.png")
        self.assertIsNone(result)

    def test_get_next_text(self):
        # Mock detections
        detections = [
            {'text': 'Order ID'},
            {'text': 'ABC123'},  # This should be returned
            {'text': 'Tracking'},
            {'text': 'Number'}
        ]
        
        result = self.ocr._get_next_text(detections, 0)
        self.assertEqual(result, 'ABC123')

    def test_rts_code_extraction(self):
        # Test RTS code pattern matching
        test_cases = [
            ("RTS-BUL-SJDM-MZN1-A1", "RTS-BUL-SJDM-MZN1-A1"),
            ("RTS-BUL-SJDM-TKM-B1", "RTS-BUL-SJDM-TKM-B1"),
            ("Some text RTS-BUL-SJDM-SPY1-C1 more text", "RTS-BUL-SJDM-SPY1-C1"),
            ("No RTS code here", None)
        ]
        
        for text, expected in test_cases:
            with self.subTest(text=text):
                # This would be tested in the full extraction process
                import re
                match = re.search(self.ocr.RTS_PATTERN, text)
                if match:
                    self.assertEqual(match.group(), expected)
                else:
                    self.assertIsNone(expected)

if __name__ == '__main__':
    unittest.main()