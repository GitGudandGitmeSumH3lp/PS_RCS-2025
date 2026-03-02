/*
 * PS_RCS_PROJECT – Motor Controller with Variable Speed
 * 
 * Commands:
 *   W <speed> – forward
 *   S <speed> – backward
 *   A <speed> – left (rotate)
 *   D <speed> – right (rotate)
 *   X        – stop (no speed byte)
 * 
 * Speed is a byte 0-255, where 0 = stop, 255 = full speed.
 * Pulse widths: 1500µs = stop, 2000µs = full forward, 1000µs = full reverse.
 */

#include <Servo.h>

Servo leftMotor;   // left motor on pin 8
Servo rightMotor;  // right motor on pin 9

// Pulse widths in microseconds (adjust for your ESCs)
#define STOP_PULSE  1500
#define FWD_PULSE   2000
#define REV_PULSE   1000

// Safety timeout: stop motors if no command received for this many milliseconds
#define SAFETY_TIMEOUT_MS 500

unsigned long lastCommandTime = 0;

// Convert speed (0-255) to pulse width between stop and full in the given direction
int speedToPulse(int speed, bool forward) {
  if (speed == 0) return STOP_PULSE;
  int range = (forward ? FWD_PULSE : REV_PULSE) - STOP_PULSE;
  speed = constrain(speed, 0, 255);
  return STOP_PULSE + (range * speed) / 255;
}

void setup() {
  leftMotor.attach(8);
  rightMotor.attach(9);
  Serial.begin(9600);
  // Initial stop
  leftMotor.writeMicroseconds(STOP_PULSE);
  rightMotor.writeMicroseconds(STOP_PULSE);
  lastCommandTime = millis();
}

void loop() {
  // Check if at least one byte is available
  if (Serial.available() >= 1) {
    char cmd = Serial.read();
    uint8_t speed = 255;      // default full speed if no speed byte
    bool hasSpeed = false;

    // If it's a movement command, try to read a speed byte
    if (cmd == 'W' || cmd == 'A' || cmd == 'S' || cmd == 'D') {
      if (Serial.available() >= 1) {
        speed = Serial.read();
        hasSpeed = true;
      }
    }

    // Execute command with speed
    switch (cmd) {
      case 'W': // forward
        leftMotor.writeMicroseconds(speedToPulse(speed, true));
        rightMotor.writeMicroseconds(speedToPulse(speed, true));
        lastCommandTime = millis();
        break;
      case 'S': // backward
        leftMotor.writeMicroseconds(speedToPulse(speed, false));
        rightMotor.writeMicroseconds(speedToPulse(speed, false));
        lastCommandTime = millis();
        break;
      case 'A': // left (rotate)
        leftMotor.writeMicroseconds(speedToPulse(speed, false));
        rightMotor.writeMicroseconds(speedToPulse(speed, true));
        lastCommandTime = millis();
        break;
      case 'D': // right (rotate)
        leftMotor.writeMicroseconds(speedToPulse(speed, true));
        rightMotor.writeMicroseconds(speedToPulse(speed, false));
        lastCommandTime = millis();
        break;
      case 'X': // stop
        leftMotor.writeMicroseconds(STOP_PULSE);
        rightMotor.writeMicroseconds(STOP_PULSE);
        lastCommandTime = millis();
        break;
      default:
        // ignore unknown characters
        break;
    }
  }

  // Safety timeout: stop if no valid command for too long
  if (millis() - lastCommandTime > SAFETY_TIMEOUT_MS) {
    leftMotor.writeMicroseconds(STOP_PULSE);
    rightMotor.writeMicroseconds(STOP_PULSE);
  }
}