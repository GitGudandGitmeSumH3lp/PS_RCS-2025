/*
 * PS_RCS_PROJECT – Motor Controller with Variable Speed & SOFT START
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

// Pulse widths in microseconds
#define STOP_PULSE  1500
#define FWD_PULSE   2000
#define REV_PULSE   1000

// Safety timeout: stop motors if no command received for 500ms
#define SAFETY_TIMEOUT_MS 500

// --- SOFT START SETTINGS ---
// Modifying these changes how fast the robot accelerates
#define RAMP_INTERVAL_MS 10  // Update motor speed every 10ms
#define RAMP_STEP_US 25      // Microseconds to step per interval (25 = ~0.2 seconds to reach full speed)

unsigned long lastCommandTime = 0;
unsigned long lastRampTime = 0;

// Track current vs target speeds
int currentLeft = STOP_PULSE;
int currentRight = STOP_PULSE;
int targetLeft = STOP_PULSE;
int targetRight = STOP_PULSE;

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
  // 1. Process Serial Commands with Auto-Sync
  if (Serial.available() >= 2) {
    char peekCmd = Serial.peek(); // Look at the first byte without consuming it
    
    // Check if the byte is a valid command character
    if (peekCmd == 'W' || peekCmd == 'A' || peekCmd == 'S' || peekCmd == 'D' || peekCmd == 'X') {
      char cmd = Serial.read();
      uint8_t speed = Serial.read();
      
      lastCommandTime = millis();
      
      // Set the TARGET speed, don't write to motors directly
      switch (cmd) {
        case 'W': 
          targetLeft = speedToPulse(speed, true);
          targetRight = speedToPulse(speed, true);
          break;
        case 'S': 
          targetLeft = speedToPulse(speed, false);
          targetRight = speedToPulse(speed, false);
          break;
        case 'A': 
          targetLeft = speedToPulse(speed, false);
          targetRight = speedToPulse(speed, true);
          break;
        case 'D': 
          targetLeft = speedToPulse(speed, true);
          targetRight = speedToPulse(speed, false);
          break;
        case 'X': 
          targetLeft = STOP_PULSE;
          targetRight = STOP_PULSE;
          break;
      }
    } else {
      // DESYNC DETECTED! Throw away the garbage byte to realign the stream
      Serial.read(); 
    }
  }

  // 2. Safety Timeout Check
  if (millis() - lastCommandTime > SAFETY_TIMEOUT_MS) {
    targetLeft = STOP_PULSE;
    targetRight = STOP_PULSE;
  }

  // 3. Soft Start Ramping Execution
  unsigned long now = millis();
  if (now - lastRampTime >= RAMP_INTERVAL_MS) {
    lastRampTime = now;
    
    // Step Left Motor
    if (currentLeft < targetLeft) {
      currentLeft += RAMP_STEP_US;
      if (currentLeft > targetLeft) currentLeft = targetLeft;
    } else if (currentLeft > targetLeft) {
      currentLeft -= RAMP_STEP_US;
      if (currentLeft < targetLeft) currentLeft = targetLeft;
    }
    
    // Step Right Motor
    if (currentRight < targetRight) {
      currentRight += RAMP_STEP_US;
      if (currentRight > targetRight) currentRight = targetRight;
    } else if (currentRight > targetRight) {
      currentRight -= RAMP_STEP_US;
      if (currentRight < targetRight) currentRight = targetRight;
    }

    // Actually send the smoothed signal to the ESCs
    leftMotor.writeMicroseconds(currentLeft);
    rightMotor.writeMicroseconds(currentRight);
  }
}