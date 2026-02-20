# MERGED FILE: src/hardware/motor_controller.py
# src/hardware/motor_controller.py
import serial
import time
import logging
import threading
from typing import ClassVar, Optional

class MotorController:
    _instance: ClassVar[Optional['MotorController']] = None
    _class_lock: ClassVar[threading.Lock] = threading.Lock()
    _CMD_MAP: ClassVar[dict] = {
        'forward':  'W',
        'backward': 'S',
        'left':     'A',
        'right':    'D',
        'stop':     'X',
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, 'initialized', False):
            return
        self.serial_conn: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self._port: Optional[str] = None
        self._baudrate: Optional[int] = None
        self._io_lock = threading.Lock()
        self.logger = logging.getLogger("MotorController")
        self.initialized = True

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        if not isinstance(port, str) or not port:
            raise ValueError("port must be a non-empty string")
        if not isinstance(baudrate, int) or baudrate <= 0:
            raise ValueError("baudrate must be a positive integer")
        with self._io_lock:
            if self.is_connected and self.serial_conn and self.serial_conn.is_open:
                return True
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
            try:
                self.serial_conn = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=2,
                    write_timeout=1,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                )
                time.sleep(2)
                self.serial_conn.flushInput()
                self.serial_conn.flushOutput()
                self._port = port
                self._baudrate = baudrate
                if not self._test_connection():
                    self.serial_conn.close()
                    self.serial_conn = None
                    return False
                self.is_connected = True
                self.logger.info(f"Connected to motor controller on {port} @ {baudrate}")
                return True
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
                self.is_connected = False
                self.serial_conn = None
                return False

    def _test_connection(self) -> bool:
        try:
            self.serial_conn.write(b'K')
            self.serial_conn.flush()
            time.sleep(0.1)
            self.serial_conn.flushInput()
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def send_command(self, command: str, speed: int = 0) -> bool:
        cmd_lower = command.lower()
        if cmd_lower not in self._CMD_MAP:
            self.logger.warning(f"Unknown command: '{command}'")
            return False
        char_cmd = self._CMD_MAP[cmd_lower]
        with self._io_lock:
            if not self.is_connected or not self.serial_conn or not self.serial_conn.is_open:
                self.logger.error("Cannot send command: motor controller not connected")
                return False
            try:
                self.serial_conn.write(char_cmd.encode('ascii'))
                self.serial_conn.flush()
                self.logger.debug(f"Sent command: '{char_cmd}'")
                return True
            except serial.SerialException as e:
                self.logger.error(f"Serial error sending command: {e}")
                self.disconnect()
                return False
            except Exception as e:
                self.logger.error(f"Unexpected error sending command: {e}")
                self.disconnect()
                return False

    def disconnect(self) -> None:
        with self._io_lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.write(b'X')
                    self.serial_conn.flush()
                except Exception:
                    pass
                try:
                    self.serial_conn.close()
                except Exception as e:
                    self.logger.warning(f"Error closing serial port: {e}")
                self.serial_conn = None
                self.is_connected = False
                self.logger.info("Motor controller disconnected")

    def get_status(self) -> dict:
        return {
            'connected': self.is_connected,
            'port': self._port,
            'baudrate': self._baudrate,
        }