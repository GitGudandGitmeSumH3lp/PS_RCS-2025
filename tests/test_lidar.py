# test_lidar.py
# Unit tests for LiDAR handler

import unittest
from unittest.mock import Mock, patch
import sys
import os
import math

# Add parent directory to path to import lidar_handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from lidar_handler import LiDARHandler

class TestLiDARHandler(unittest.TestCase):
    def setUp(self):
        self.lidar = LiDARHandler(port='/dev/ttyUSB1', baudrate=115200)

    @patch('lidar_handler.RPLidar')
    def test_connect_success(self, mock_rplidar):
        mock_lidar_instance = Mock()
        mock_rplidar.return_value = mock_lidar_instance
        
        result = self.lidar.connect()
        self.assertTrue(result)
        mock_rplidar.assert_called_with('/dev/ttyUSB1', 115200)

    @patch('lidar_handler.RPLidar')
    def test_connect_failure(self, mock_rplidar):
        mock_rplidar.side_effect = Exception("Connection failed")
        
        result = self.lidar.connect()
        self.assertFalse(result)

    def test_process_scan(self):
        # Mock scan data: (quality, angle, distance)
        mock_scan = [
            (15, 0, 1000),    # 0 degrees, 1000mm
            (15, 90, 500),    # 90 degrees, 500mm
            (15, 180, 0),     # Invalid distance
            (15, 270, 750),   # 270 degrees, 750mm
        ]
        
        points = self.lidar.process_scan(mock_scan)
        
        # Check we have the correct number of points
        self.assertEqual(len(points), 3)
        
        # Check specific points
        # Point at 0 degrees (1000mm) -> (1000, 0)
        self.assertAlmostEqual(points[0][0], 1000, places=1)
        self.assertAlmostEqual(points[0][1], 0, places=1)
        
        # Point at 90 degrees (500mm) -> (0, 500)
        self.assertAlmostEqual(points[1][0], 0, places=1)
        self.assertAlmostEqual(points[1][1], 500, places=1)
        
        # Point at 270 degrees (750mm) -> (0, -750)
        self.assertAlmostEqual(points[2][0], 0, places=1)
        self.assertAlmostEqual(points[2][1], -750, places=1)

    @patch('lidar_handler.RPLidar')
    def test_get_latest_scan(self, mock_rplidar):
        mock_lidar_instance = Mock()
        mock_rplidar.return_value = mock_lidar_instance
        
        # Mock scan data
        mock_scan_data = [
            (15, 45, 1000),
            (15, 135, 500)
        ]
        mock_lidar_instance.iter_scans.return_value = iter([mock_scan_data])
        
        self.lidar.lidar = mock_lidar_instance
        points = self.lidar.get_latest_scan()
        
        self.assertEqual(len(points), 2)
        # Point at 45 degrees (1000mm) -> (707.1, 707.1)
        self.assertAlmostEqual(points[0][0], 1000 * math.cos(math.radians(45)), places=1)
        self.assertAlmostEqual(points[0][1], 1000 * math.sin(math.radians(45)), places=1)

    @patch('lidar_handler.RPLidar')
    def test_get_latest_scan_no_connection(self, mock_rplidar):
        self.lidar.lidar = None
        points = self.lidar.get_latest_scan()
        self.assertEqual(points, [])

if __name__ == '__main__':
    unittest.main()