# tests/test_ocr_correction.py

import unittest
import tempfile
import json
import os
from src.services.ocr_correction import FlashExpressCorrector

class TestFlashExpressCorrector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dict_data = {
            "couriers": {
                "flash-express": {
                    "dictionaries": {
                        "barangays": ["Muzon", "Graceville", "Tungko", "Sapang Palay"],
                        "districts": {
                            "Muzon": [{"name": "North", "code": "MZN1"}, {"name": "South", "code": "MZN2"}],
                            "Tungko": [{"name": "Main", "code": "TKO1"}]
                        }
                    },
                    "fieldEnumerations": {
                        "riderCodes": ["GY01", "GY02", "GY22", "HUB"],
                        "sortCode": [
                            "FEX-BUL-SJDM-MZN1-GY01",
                            "FEX-BUL-SJDM-TKO1-GY22"
                        ]
                    },
                    "fieldPatterns": {
                        "trackingNumber": {"pattern": "^FE\\d{10}$"},
                        "phNumber": {"pattern": "^FE \\d{12}$"}
                    }
                }
            }
        }
        cls.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(cls.dict_data, cls.temp_file)
        cls.temp_file.close()
        cls.corrector = FlashExpressCorrector(cls.temp_file.name)

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.temp_file.name)

    def test_correct_barangay(self):
        result = self.corrector.correct_barangay("Muzon")
        self.assertEqual(result, "Muzon")
        result = self.corrector.correct_barangay("Muzonn")
        self.assertEqual(result, "Muzon")
        result = self.corrector.correct_barangay("Sapang Palay")
        self.assertEqual(result, "Sapang Palay")

    def test_correct_district(self):
        result = self.corrector.correct_district("Muzon", "North")
        self.assertEqual(result, "North")
        result = self.corrector.correct_district("Muzon", "Nort")
        self.assertEqual(result, "North")

    def test_validate_tracking_number(self):
        valid, corrected = self.corrector.validate_tracking_number("FE1234567890")
        self.assertTrue(valid)
        self.assertEqual(corrected, "FE1234567890")
        valid, corrected = self.corrector.validate_tracking_number("FE123456789O")
        self.assertTrue(valid)
        self.assertEqual(corrected, "FE1234567890")
        valid, corrected = self.corrector.validate_tracking_number("FE12345678")
        self.assertFalse(valid)
        self.assertEqual(corrected, "FE12345678")

    def test_validate_phone(self):
        valid, corrected = self.corrector.validate_phone("FE 123456789012")
        self.assertTrue(valid)
        valid, corrected = self.corrector.validate_phone("FE 12345678901O")
        self.assertTrue(valid)
        self.assertEqual(corrected, "FE 123456789010")

    def test_correct_rider_code(self):
        result = self.corrector.correct_rider_code("GY01")
        self.assertEqual(result, "GY01")
        result = self.corrector.correct_rider_code("GY0l")
        self.assertEqual(result, "GY01")

    def test_correct_sort_code(self):
        result = self.corrector.correct_sort_code("FEX-BUL-SJDM-MZN1-GY01")
        self.assertEqual(result, "FEX-BUL-SJDM-MZN1-GY01")
        result = self.corrector.correct_sort_code("FEX-BUL-SJDM-MZN1-GY0l")
        self.assertEqual(result, "FEX-BUL-SJDM-MZN1-GY01")

    def test_derive_quantity_from_weight(self):
        self.assertEqual(self.corrector.derive_quantity_from_weight(500), 1)
        self.assertEqual(self.corrector.derive_quantity_from_weight(1200), 2)
        self.assertEqual(self.corrector.derive_quantity_from_weight(3000), 6)

    def test_clean_address(self):
        dirty = "123 Main St, Brgy. Muzon, SJDM, Bulacan 3023 ) 1, iy"
        clean = self.corrector.clean_address(dirty)
        self.assertEqual(clean, "123 Main St, Brgy. Muzon, SJDM, Bulacan 3023")

if __name__ == '__main__':
    unittest.main()