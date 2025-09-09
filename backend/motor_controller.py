# motor_controller_fixed.py
# Improved Python module to control robot motors via serial communication

import serial
import time
import logging
import threading

class MotorController:
    _instance = None

    def __new__(cls, port='/dev/ttyUSB0', baudrate=9600):
        if cls._instance is None:
            cls._instance = super(MotorController, cls).__new__(cls)
        return cls._instance

    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        # Prevent re-initialization of the same instance's core attributes
        if hasattr(self, 'initialized'):
            return
        self.initialized = True

        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        self._lock = threading.Lock()  # Thread safety

    def connect(self):
        """Establish serial connection to Arduino"""
        with self._lock:
            if self.is_connected and self.serial_conn and self.serial_conn.is_open:
                self.logger.info("Already connected.")
                return True

            try:
                # Ensure previous connection is closed
                if self.serial_conn:
                    self.serial_conn.close()

                # Open new connection with improved settings
                self.serial_conn = serial.Serial(
                    port=self.port, 
                    baudrate=self.baudrate, 
                    timeout=2,
                    write_timeout=1,  # Add write timeout
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                )
                
                # Wait for Arduino to reset and initialize
                time.sleep(4.0)  # Increased wait time
                
                # Clear any startup messages
                self.serial_conn.flushInput()
                self.serial_conn.flushOutput()
                
                # Test connection with a safe command
                test_success = self._test_connection()
                
                if test_success:
                    self.is_connected = True
                    self.logger.info(f" Connected to motor controller on {self.port}")
                    return True
                else:
                    self.logger.error(" Connection test failed")
                    self.serial_conn.close()
                    self.serial_conn = None
                    return False
                    
            except Exception as e:
                self.logger.error(f" Failed to connect to motor controller on {self.port}: {e}")
                self.is_connected = False
                self.serial_conn = None
                return False

    def _test_connection(self):
        """Test if the connection is working by sending a keep-alive"""
        try:
            # Send keep-alive command
            self.serial_conn.write(b'K')
            self.serial_conn.flush()
            time.sleep(0.1)
            
            # Try to read any response (Arduino might send debug info)
            response = ""
            start_time = time.time()
            while time.time() - start_time < 1.0:  # Wait up to 1 second
                if self.serial_conn.in_waiting > 0:
                    try:
                        response += self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                    except:
                        pass
                time.sleep(0.1)
            
            self.logger.debug(f"Arduino response: {response.strip()}")
            return True  # Connection established
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def disconnect(self):
        """Close serial connection"""
        with self._lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.stop()  # Send final stop command
                    time.sleep(0.3)  # Wait a bit longer
                    self.serial_conn.close()
                    self.logger.info("🔌 Disconnected from motor controller")
                except Exception as e:
                    self.logger.error(f"⚠️ Error during disconnection: {e}")
            self.is_connected = False
            self.serial_conn = None

    def send_command(self, command):
        """Send a single character command to Arduino"""
        with self._lock:
            if not self.is_connected or not self.serial_conn or not self.serial_conn.is_open:
                self.logger.error("🚫 Not connected to motor controller")
                return False

            try:
                # Send ONLY the command character (no newline)
                cmd_byte = command.upper().encode('ascii')[0:1]
                
                # Clear input buffer before sending (optional)
                if self.serial_conn.in_waiting > 0:
                    self.serial_conn.flushInput()
                
                self.serial_conn.write(cmd_byte)
                self.serial_conn.flush()  # Ensure it's sent immediately
                
                self.logger.debug(f"⬆️ Sent command: '{command.upper()}'")
                
                # Optional: Read Arduino response for debugging
                if self.logger.level <= logging.DEBUG:
                    time.sleep(0.05)  # Brief wait for response
                    if self.serial_conn.in_waiting > 0:
                        response = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                        self.logger.debug(f"⬇️ Arduino: {response.strip()}")
                
                return True
                
            except Exception as e:
                self.logger.error(f"💥 Failed to send command '{command}': {e}")
                self.is_connected = False  # Mark as disconnected on error
                return False

    # --- Movement Commands ---
    def move_forward(self):
        """Move robot forward"""
        return self.send_command("W")

    def move_backward(self):
        """Move robot backward"""
        return self.send_command("S")

    def turn_left(self):
        """Turn robot left"""
        return self.send_command("A")

    def turn_right(self):
        """Turn robot right"""
        return self.send_command("D")

    def stop(self):
        """Stop all motors"""
        return self.send_command("X")

    def keep_alive(self):
        """Send keep-alive signal (for hold-to-move systems)"""
        return self.send_command("K")

    def increase_speed(self):
        """Increase motor speed"""
        return self.send_command("+")

    def decrease_speed(self):
        """Decrease motor speed"""
        return self.send_command("-")

    def test_motors(self):
        """Test individual motors"""
        return self.send_command("T")

    # --- Convenience Methods ---
    def move_for_duration(self, command, duration_seconds):
        """Move in a direction for a specific duration"""
        if command.upper() == 'W':
            success = self.move_forward()
        elif command.upper() == 'S':
            success = self.move_backward()
        elif command.upper() == 'A':
            success = self.turn_left()
        elif command.upper() == 'D':
            success = self.turn_right()
        else:
            self.logger.error(f"Invalid movement command: {command}")
            return False
            
        if success:
            time.sleep(duration_seconds)
            return self.stop()
        return False

    def get_status(self):
        """Get connection status"""
        return {
            'connected': self.is_connected,
            'port': self.port,
            'baudrate': self.baudrate,
            'serial_open': self.serial_conn.is_open if self.serial_conn else False
        }

# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test the motor controller
    motor = MotorController(port='/dev/ttyUSB0')  # Adjust port as needed
    
    try:
        if motor.connect():
            print(" Motor controller connected!")
            print("Status:", motor.get_status())
            
            # Test sequence
            print("\n Running test sequence...")
            
            print("Testing forward motion...")
            motor.move_forward()
            time.sleep(2)
            motor.stop()
            time.sleep(1)
            
            print("Testing backward motion...")
            motor.move_backward()
            time.sleep(2)
            motor.stop()
            time.sleep(1)
            
            print("Testing left turn...")
            motor.turn_left()
            time.sleep(1)
            motor.stop()
            time.sleep(1)
            
            print("Testing right turn...")
            motor.turn_right()
            time.sleep(1)
            motor.stop()
            
            print("Testing individual motors...")
            motor.test_motors()
            
            print(" Test complete!")
            
        else:
            print(" Failed to connect to motor controller")
            
    except KeyboardInterrupt:
        print("\n Test interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        motor.disconnect()
        print(" Motor controller disconnected")