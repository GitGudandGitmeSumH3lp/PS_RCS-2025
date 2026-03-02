/*
 * PS_RCS_PROJECT - Motor Controller Firmware with Safety Timeout
 * File: arduino/wheels.ino
 * Description: Drives two ESCs on pins 8 & 9 using Servo library.
 *              Accepts W/A/S/D/X commands via Serial at 9600 baud.
 *              Motors stop automatically if no command received for SAFETY_TIMEOUT_MS.
 */

#include <Servo.h>

Servo leftMotor;   // left ESC on pin 8
Servo rightMotor;  // right ESC on pin 9

// Pulse widths in microseconds (adjust for your ESCs)
#define STOP_PULSE  1500
#define FWD_PULSE   2000
#define REV_PULSE   1000

// Safety timeout: stop motors if no command received for this many milliseconds
#define SAFETY_TIMEOUT_MS 500

unsigned long lastCommandTime = 0;

void setup() {
  Serial.begin(9600);
  leftMotor.attach(8);
  rightMotor.attach(9);
  stopMotors();
  lastCommandTime = millis();
  Serial.println("READY");
}

void loop() {
  // Check for timeout
  if (millis() - lastCommandTime > SAFETY_TIMEOUT_MS) {
    stopMotors();
  }

  if (Serial.available() > 0) {
    char cmd = toupper(Serial.read());
    lastCommandTime = millis();  // reset timeout

    switch (cmd) {
      case 'W': moveForward();  break;
      case 'S': moveBackward(); break;
      case 'A': turnLeft();     break;
      case 'D': turnRight();    break;
      case 'X': stopMotors();   break;
      // unknown chars ignored
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