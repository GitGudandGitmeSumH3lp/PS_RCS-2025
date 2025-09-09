# test_huskylens.py
# Unit tests for HuskyLens handler

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import huskylens_handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from huskylens_handler import HuskyLensHandler

class TestHuskyLensHandler(unittest.TestCase):
    def setUp(self):
        self.husky = HuskyLensHandler(port='/dev/ttyUSB2', baudrate=9600)

    @patch('huskylens_handler.HuskyLensLibrary')
    def test_connect_success(self, mock_huskylib):
        mock_husky_instance = Mock()
        mock_huskylib.return_value = mock_husky_instance
        mock_husky_instance.known_algorithms = {"ALGORITHM_FACE_RECOGNITION": "Face Recognition"}
        mock_husky_instance.currentAlgorithm = "ALGORITHM_FACE_RECOGNITION"
        
        result = self.husky.connect()
        self.assertTrue(result)
        mock_huskylib.assert_called_with("SERIAL", '/dev/ttyUSB2', baudrate=9600)

    @patch('huskylens_handler.HuskyLensLibrary')
    def test_connect_failure(self, mock_huskylib):
        mock_huskylib.side_effect = Exception("Connection failed")
        
        result = self.husky.connect()
        self.assertFalse(result)

    def test_get_object_label_face_recognition(self):
        # Mock block object
        mock_block = Mock()
        mock_block.ID = 1
        
        # Set current mode to face recognition
        self.husky.current_mode = "ALGORITHM_FACE_RECOGNITION"
        
        label = self.husky.get_object_label(mock_block)
        self.assertEqual(label, "Face #1")

    def test_get_object_label_object_classification(self):
        mock_block = Mock()
        mock_block.ID = 2
        mock_block.name = "Apple"
        
        self.husky.current_mode = "ALGORITHM_OBJECT_CLASSIFICATION"
        
        label = self.husky.get_object_label(mock_block)
        self.assertEqual(label, "Apple")

    def test_get_object_label_color_recognition(self):
        mock_block = Mock()
        mock_block.ID = 1  # Red
        
        self.husky.current_mode = "ALGORITHM_COLOR_RECOGNITION"
        
        label = self.husky.get_object_label(mock_block)
        self.assertEqual(label, "Red")

    @patch('huskylens_handler.HuskyLensLibrary')
    def test_get_detections(self, mock_huskylib):
        mock_husky_instance = Mock()
        mock_huskylib.return_value = mock_husky_instance
        
        # Mock block objects
        mock_block1 = Mock()
        mock_block1.ID = 1
        mock_block1.x = 100
        mock_block1.y = 150
        mock_block1.width = 50
        mock_block1.height = 30
        
        mock_block2 = Mock()
        mock_block2.ID = 2
        mock_block2.x = 200
        mock_block2.y = 250
        mock_block2.width = 60
        mock_block2.height = 40
        
        mock_husky_instance.blocks.return_value = [mock_block1, mock_block2]
        
        self.husky.huskylens = mock_husky_instance
        self.husky.current_mode = "ALGORITHM_FACE_RECOGNITION"
        
        detections = self.husky.get_detections()
        
        self.assertEqual(len(detections), 2)
        self.assertEqual(detections[0]["label"], "Face #1")
        self.assertEqual(detections[0]["x"], 100)
        self.assertEqual(detections[0]["y"], 150)
        self.assertEqual(detections[0]["width"], 50)
        self.assertEqual(detections[0]["height"], 30)

if __name__ == '__main__':
    unittest.main()