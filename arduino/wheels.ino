/*
 * PS_RCS_PROJECT - Motor Controller Firmware (Direct PWM on pins 8 & 9)
 * File: arduino/wheels.ino
 * Description: Drives two ESCs on pins 8 (left) and 9 (right) using the Servo library.
 *              Accepts W/A/S/D/X commands via Serial at 9600 baud.
 *
 * Wiring:
 *   - Left ESC signal wire → Arduino pin 8
 *   - Right ESC signal wire → Arduino pin 9
 *   - Ensure ESCs have common ground with Arduino.
 *   - Power ESCs from a suitable battery (do NOT power through Arduino).
 */

#include <Servo.h>

Servo leftMotor;   // left ESC on pin 8
Servo rightMotor;  // right ESC on pin 9

// Pulse widths in microseconds (standard for most ESCs)
#define STOP_PULSE  1500  // neutral / stop
#define FWD_PULSE   2000  // full forward
#define REV_PULSE   1000  // full reverse

void setup() {
  Serial.begin(9600);
  leftMotor.attach(8);
  rightMotor.attach(9);
  stopMotors();                // ensure motors are stopped at startup
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = toupper(Serial.read());
    switch (cmd) {
      case 'W': moveForward();  break;
      case 'S': moveBackward(); break;
      case 'A': turnLeft();     break;
      case 'D': turnRight();    break;
      case 'X': stopMotors();   break;
      // Unknown characters ignored
    }
  }
}

void moveForward() {
  leftMotor.writeMicroseconds(FWD_PULSE);
  rightMotor.writeMicroseconds(FWD_PULSE);
}

void moveBackward() {
  leftMotor.writeMicroseconds(REV_PULSE);
  rightMotor.writeMicroseconds(REV_PULSE);
}

void turnLeft() {
  leftMotor.writeMicroseconds(REV_PULSE);
  rightMotor.writeMicroseconds(FWD_PULSE);
}

void turnRight() {
  leftMotor.writeMicroseconds(FWD_PULSE);
  rightMotor.writeMicroseconds(REV_PULSE);
}

void stopMotors() {
  leftMotor.writeMicroseconds(STOP_PULSE);
  rightMotor.writeMicroseconds(STOP_PULSE);
}