// wheels_fixed.ino
#include <Servo.h>

// Create servo objects for ESCs
Servo leftESC;
Servo rightESC;

// ESC pins
const int leftESCPin = 8;
const int rightESCPin = 9;

// ESC control values
const int ESC_MIN = 1000;      // Minimum throttle (stop)
const int ESC_NEUTRAL = 1500;  // Neutral/stop position
const int ESC_MAX = 2000;      // Maximum throttle

// Movement speeds - INCREASED for better reliability
int MOVE_SPEED = 300;          // Increased from 200 to 300
int TURN_SPEED = 250;          // Increased from 150 to 250

// ESC dead zone compensation
const int DEAD_ZONE_OFFSET = 50; // Minimum offset from neutral for movement

// Current motor speeds
int leftSpeed = 0;
int rightSpeed = 0;

// --- Hold-to-move timeout ---
unsigned long lastKeepAliveTime = 0;
const long keepAliveTimeout = 200; // Timeout in milliseconds

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  Serial.println("Initializing ESCs...");
  
  // Attach ESCs to pins
  leftESC.attach(leftESCPin);
  rightESC.attach(rightESCPin);
  
  // ESC calibration sequence - IMPROVED
  Serial.println("Calibrating ESCs...");
  
  // Send neutral signal
  leftESC.writeMicroseconds(ESC_NEUTRAL);
  rightESC.writeMicroseconds(ESC_NEUTRAL);
  delay(1000);
  
  // Send max signal briefly (some ESCs need this)
  leftESC.writeMicroseconds(ESC_MAX);
  rightESC.writeMicroseconds(ESC_MAX);
  delay(500);
  
  // Send min signal briefly
  leftESC.writeMicroseconds(ESC_MIN);
  rightESC.writeMicroseconds(ESC_MIN);
  delay(500);
  
  // Return to neutral
  leftESC.writeMicroseconds(ESC_NEUTRAL);
  rightESC.writeMicroseconds(ESC_NEUTRAL);
  delay(1000);
  
  Serial.println("ESC Calibration Complete!");
  
  // Print startup message
  Serial.println("WASD ESC Control Ready!");
  Serial.println("Commands:");
  Serial.println("W - Forward");
  Serial.println("S - Backward");
  Serial.println("A - Turn Left");
  Serial.println("D - Turn Right");
  Serial.println("X - Stop");
  Serial.println("K - Keep Alive (for hold-to-move)");
  Serial.println("+ - Increase Speed");
  Serial.println("- - Decrease Speed");
  Serial.println("T - Test Motors");
  Serial.println();
  
  // Initialize keep-alive timer
  lastKeepAliveTime = millis();
}

void loop() {
  // --- Check for timeout ---
  if ((millis() - lastKeepAliveTime) > keepAliveTimeout) {
    stopMotors(); // Stop if no keep-alive received
  }

  // Check if any command is sent via Serial
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    // Clear any remaining characters (like newlines)
    while (Serial.available() > 0) {
      Serial.read();
    }
    
    command = toupper(command);  // Make case-insensitive
    
    switch (command) {
      case 'W':
        moveForward();
        Serial.println("Moving Forward");
        Serial.print("Left: "); Serial.print(leftSpeed);
        Serial.print(" | Right: "); Serial.println(rightSpeed);
        lastKeepAliveTime = millis();
        break;
      case 'S':
        moveBackward();
        Serial.println("Moving Backward");
        Serial.print("Left: "); Serial.print(leftSpeed);
        Serial.print(" | Right: "); Serial.println(rightSpeed);
        lastKeepAliveTime = millis();
        break;
      case 'A':
        turnLeft();
        Serial.println("Turning Left");
        Serial.print("Left: "); Serial.print(leftSpeed);
        Serial.print(" | Right: "); Serial.println(rightSpeed);
        lastKeepAliveTime = millis();
        break;
      case 'D':
        turnRight();
        Serial.println("Turning Right");
        Serial.print("Left: "); Serial.print(leftSpeed);
        Serial.print(" | Right: "); Serial.println(rightSpeed);
        lastKeepAliveTime = millis();
        break;
      case 'X':
        stopMotors();
        Serial.println("Motors Stopped (Explicit)");
        Serial.print("Left: "); Serial.print(leftSpeed);
        Serial.print(" | Right: "); Serial.println(rightSpeed);
        break;
      case 'K':
        lastKeepAliveTime = millis();
        Serial.println("Keep-Alive Received");
        break;
      case '+':
        increaseSpeed();
        break;
      case '-':
        decreaseSpeed();
        break;
      case 'T':
        testMotors();
        break;
      default:
        Serial.print("Invalid command: ");
        Serial.println(command);
        Serial.println("Use: W, A, S, D, X, K, +, -, T");
        break;
    }
  }
  delay(10);
}

// --- Movement Functions with Dead Zone Compensation ---
void moveForward() {
  leftSpeed = ESC_NEUTRAL + max(MOVE_SPEED, DEAD_ZONE_OFFSET);
  rightSpeed = ESC_NEUTRAL + max(MOVE_SPEED, DEAD_ZONE_OFFSET);
  updateMotors();
}

void moveBackward() {
  leftSpeed = ESC_NEUTRAL - max(MOVE_SPEED, DEAD_ZONE_OFFSET);
  rightSpeed = ESC_NEUTRAL - max(MOVE_SPEED, DEAD_ZONE_OFFSET);
  updateMotors();
}

void turnLeft() {
  leftSpeed = ESC_NEUTRAL - max(TURN_SPEED, DEAD_ZONE_OFFSET);
  rightSpeed = ESC_NEUTRAL + max(TURN_SPEED, DEAD_ZONE_OFFSET);
  updateMotors();
}

void turnRight() {
  leftSpeed = ESC_NEUTRAL + max(TURN_SPEED, DEAD_ZONE_OFFSET);
  rightSpeed = ESC_NEUTRAL - max(TURN_SPEED, DEAD_ZONE_OFFSET);
  updateMotors();
}

void stopMotors() {
  leftSpeed = ESC_NEUTRAL;
  rightSpeed = ESC_NEUTRAL;
  updateMotors();
}

// --- Speed Adjustment Functions ---
void increaseSpeed() {
  if (MOVE_SPEED < 450) {
    MOVE_SPEED += 25; // Larger increments
    TURN_SPEED += 20;
  }
  Serial.print("Move speed: "); Serial.print(MOVE_SPEED);
  Serial.print(" | Turn speed: "); Serial.println(TURN_SPEED);
}

void decreaseSpeed() {
  if (MOVE_SPEED > 100) { // Higher minimum
    MOVE_SPEED -= 25; // Larger decrements
    TURN_SPEED -= 20;
  }
  Serial.print("Move speed: "); Serial.print(MOVE_SPEED);
  Serial.print(" | Turn speed: "); Serial.println(TURN_SPEED);
}

// --- Motor Test Function ---
void testMotors() {
  Serial.println("Testing motors...");
  
  Serial.println("Left motor forward...");
  leftESC.writeMicroseconds(ESC_NEUTRAL + 200);
  rightESC.writeMicroseconds(ESC_NEUTRAL);
  delay(1000);
  
  Serial.println("Right motor forward...");
  leftESC.writeMicroseconds(ESC_NEUTRAL);
  rightESC.writeMicroseconds(ESC_NEUTRAL + 200);
  delay(1000);
  
  Serial.println("Both motors backward...");
  leftESC.writeMicroseconds(ESC_NEUTRAL - 200);
  rightESC.writeMicroseconds(ESC_NEUTRAL - 200);
  delay(1000);
  
  Serial.println("Stop all...");
  stopMotors();
}

// --- Motor Output Function ---
void updateMotors() {
  // Ensure values stay within safe ESC range
  leftSpeed = constrain(leftSpeed, ESC_MIN, ESC_MAX);
  rightSpeed = constrain(rightSpeed, ESC_MIN, ESC_MAX);
  
  // Send PWM signals
  leftESC.writeMicroseconds(leftSpeed);
  rightESC.writeMicroseconds(rightSpeed);
}