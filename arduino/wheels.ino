/*
 * PS_RCS_PROJECT – Motor Controller with Variable Speed
 * 
 * Commands (ALWAYS 2 BYTES):
 *   W <speed> – forward
 *   S <speed> – backward
 *   A <speed> – left (rotate)
 *   D <speed> – right (rotate)
 *   X <speed> – stop (speed byte ignored but must be sent)
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
  
  // Initial stop to arm ESCs
  leftMotor.writeMicroseconds(STOP_PULSE);
  rightMotor.writeMicroseconds(STOP_PULSE);
  lastCommandTime = millis();
}

void loop() {
  // Wait until exactly 2 bytes are available in the buffer
  if (Serial.available() >= 2) {
    char cmd = Serial.read();       // Read byte 1: Command
    uint8_t speed = Serial.read();  // Read byte 2: Speed

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
        // Ignore unknown characters (keeps buffer aligned)
        break;
    }
  }

  // Safety timeout: stop if no valid command for too long
  if (millis() - lastCommandTime > SAFETY_TIMEOUT_MS) {
    leftMotor.writeMicroseconds(STOP_PULSE);
    rightMotor.writeMicroseconds(STOP_PULSE);
  }
}