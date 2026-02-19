/*
 * PS_RCS_PROJECT - Motor Controller Firmware
 * File: arduino/wheels.ino
 * Description: PCA9685 differential drive controller.
 *              Accepts W/A/S/D/X commands via Serial at 9600 baud.
 *
 * Wiring: Connect PCA9685 via I2C (SDA=A4, SCL=A5 on Uno).
 *         Left motor on channel LEFT_MOTOR_CH.
 *         Right motor on channel RIGHT_MOTOR_CH.
 *         If one motor runs backwards, swap FWD_PULSE <-> REV_PULSE for that channel.
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(); // Default I2C addr 0x40

// ── Channel Assignment ────────────────────────────────────────────────────────
#define LEFT_MOTOR_CH   0
#define RIGHT_MOTOR_CH  1

// ── Pulse Widths (continuous rotation servos @ 50Hz) ─────────────────────────
#define STOP_PULSE  307   // ~1.5ms neutral
#define FWD_PULSE   410   // ~2.0ms forward
#define REV_PULSE   205   // ~1.0ms reverse

// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(9600);
  pwm.begin();
  pwm.setPWMFreq(50);
  stopMotors();
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
      // Unknown chars ignored silently
    }
  }
}

void setMotor(int channel, int pulse) {
  pwm.setPWM(channel, 0, pulse);
}

void moveForward() {
  setMotor(LEFT_MOTOR_CH,  FWD_PULSE);
  setMotor(RIGHT_MOTOR_CH, FWD_PULSE);
}

void moveBackward() {
  setMotor(LEFT_MOTOR_CH,  REV_PULSE);
  setMotor(RIGHT_MOTOR_CH, REV_PULSE);
}

void turnLeft() {
  setMotor(LEFT_MOTOR_CH,  REV_PULSE);
  setMotor(RIGHT_MOTOR_CH, FWD_PULSE);
}

void turnRight() {
  setMotor(LEFT_MOTOR_CH,  FWD_PULSE);
  setMotor(RIGHT_MOTOR_CH, REV_PULSE);
}

void stopMotors() {
  setMotor(LEFT_MOTOR_CH,  STOP_PULSE);
  setMotor(RIGHT_MOTOR_CH, STOP_PULSE);
}