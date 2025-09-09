# test_motor.py
# Unit tests for motor controller

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import motor_controller
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from motor_controller import MotorController

class TestMotorController(unittest.TestCase):
    def setUp(self):
        self.motor = MotorController(port='/dev/ttyUSB0', baudrate=9600)

    @patch('motor_controller.serial.Serial')
    def test_connect_success(self, mock_serial):
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        mock_serial_instance.is_open = True
        
        result = self.motor.connect()
        self.assertTrue(result)
        mock_serial.assert_called_with('/dev/ttyUSB0', 9600, timeout=1)

    @patch('motor_controller.serial.Serial')
    def test_connect_failure(self, mock_serial):
        mock_serial.side_effect = Exception("Connection failed")
        
        result = self.motor.connect()
        self.assertFalse(result)

    @patch('motor_controller.serial.Serial')
    def test_send_command_success(self, mock_serial):
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        mock_serial_instance.is_open = True
        mock_serial_instance.readline.return_value = b"Acknowledged\n"
        
        self.motor.serial_conn = mock_serial_instance
        result = self.motor.send_command("FORWARD")
        self.assertTrue(result)
        mock_serial_instance.write.assert_called_with(b"FORWARD\n")

    def test_send_command_no_connection(self):
        self.motor.serial_conn = None
        result = self.motor.send_command("FORWARD")
        self.assertFalse(result)

    @patch('motor_controller.serial.Serial')
    def test_movement_commands(self, mock_serial):
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        mock_serial_instance.is_open = True
        mock_serial_instance.readline.return_value = b"Acknowledged\n"
        
        self.motor.serial_conn = mock_serial_instance
        
        # Test all movement commands
        commands = [
            ("FORWARD", self.motor.move_forward),
            ("BACKWARD", self.motor.move_backward),
            ("LEFT", self.motor.turn_left),
            ("RIGHT", self.motor.turn_right),
            ("STOP", self.motor.stop)
        ]
        
        for command_str, command_func in commands:
            with self.subTest(command=command_str):
                result = command_func()
                self.assertTrue(result)
                mock_serial_instance.write.assert_called_with(f"{command_str}\n".encode())

    @patch('motor_controller.serial.Serial')
    def test_disconnect(self, mock_serial):
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        mock_serial_instance.is_open = True
        
        self.motor.serial_conn = mock_serial_instance
        self.motor.disconnect()
        
        mock_serial_instance.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()