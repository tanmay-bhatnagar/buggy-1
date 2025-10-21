/*********************************************************************
 * four_move_with_pauses.ino
 *
 * Drives a 4WD buggy (L293D v1 shield) in the following sequence:
 *   1. Forward for 3 s
 *   2. Pause 2 s
 *   3. Backward for 3 s
 *   4. Pause 2 s
 *   5. Forward-left for 3 s
 *   6. Pause 2 s
 *   7. Forward-right for 3 s
 *   8. Stop
 *
 * Wheel ↔ motor-slot mapping:
 *   M1 → Front-Left   (reversed)
 *   M2 → Rear-Left    (normal)
 *   M3 → Rear-Right   (reversed)
 *   M4 → Front-Right  (normal)
 *
 * “Forward-left”   = left wheels stopped, right wheels forward
 * “Forward-right”  = left wheels forward, right wheels stopped
 *
 * Pause means all wheels RELEASE (coast).
 *
 * Dependencies:
 *   • Adafruit Motor Shield Library (v1) → AFMotor.h
 *
 * Author: ChatGPT (o4-mini)
 * Date:   Jun 2025
 *********************************************************************/

#include <AFMotor.h>  // For L293D v1 motor shields

// Motor slot constants (match shield labels)
constexpr uint8_t M1 = 1;   // Front-Left   (reversed)
constexpr uint8_t M2 = 2;   // Rear-Left    (normal)
constexpr uint8_t M3 = 3;   // Rear-Right   (reversed)
constexpr uint8_t M4 = 4;   // Front-Right  (normal)

// Create AF_DCMotor objects
AF_DCMotor FL(M1);
AF_DCMotor RL(M2);
AF_DCMotor RR(M3);
AF_DCMotor FR(M4);

// Reversal table: true = motor is wired flipped
//   index 0 → M1, index 1 → M2, index 2 → M3, index 3 → M4
const bool REV[] = { true,  // M1 (Front-Left)   reversed
                     false, // M2 (Rear-Left)    normal
                     true,  // M3 (Rear-Right)   reversed
                     false  // M4 (Front-Right)  normal
                   };

// Speeds (0–255)
constexpr uint8_t SPEED = 200;

// Durations (milliseconds)
constexpr uint16_t T_MOVE  = 3000;  // 3 seconds
constexpr uint16_t T_PAUSE = 2000;  // 2 seconds

// ──────────────────────────────────────────────────────────────────────
// Helper: set all four motors to the same PWM speed
void setAllSpeed(uint8_t pwm)
{
  FL.setSpeed(pwm);
  RL.setSpeed(pwm);
  RR.setSpeed(pwm);
  FR.setSpeed(pwm);
}

// Helper: drive each side with a logical FORWARD/BACKWARD/RELEASE
//   leftDir  = FORWARD / BACKWARD / RELEASE for M1 & M2
//   rightDir = FORWARD / BACKWARD / RELEASE for M3 & M4
void tankDrive(uint8_t leftDir, uint8_t rightDir)
{
  // Front-Left
  FL.run( REV[0] ? (leftDir == FORWARD ? BACKWARD
                                     : leftDir == BACKWARD ? FORWARD
                                                           : RELEASE)
                 : leftDir );
  // Rear-Left
  RL.run( REV[1] ? (leftDir == FORWARD ? BACKWARD
                                     : leftDir == BACKWARD ? FORWARD
                                                           : RELEASE)
                 : leftDir );
  // Rear-Right
  RR.run( REV[2] ? (rightDir == FORWARD ? BACKWARD
                                      : rightDir == BACKWARD ? FORWARD
                                                            : RELEASE)
                 : rightDir );
  // Front-Right
  FR.run( REV[3] ? (rightDir == FORWARD ? BACKWARD
                                      : rightDir == BACKWARD ? FORWARD
                                                            : RELEASE)
                 : rightDir );
}

// Helper: stop all motors (coast)
void releaseAll()
{
  FL.run(RELEASE);
  RL.run(RELEASE);
  RR.run(RELEASE);
  FR.run(RELEASE);
}

// ──────────────────────────────────────────────────────────────────────
void setup()
{
  // Initialize all motors at the defined speed
  setAllSpeed(SPEED);
}

void loop()
{
  // 1) Forward for 3 s
  tankDrive(FORWARD, FORWARD);
  delay(T_MOVE);

  // 2) Pause 2 s
  releaseAll();
  delay(T_PAUSE);

  // 3) Backward for 3 s
  tankDrive(BACKWARD, BACKWARD);
  delay(T_MOVE);

  // 4) Pause 2 s
  releaseAll();
  delay(T_PAUSE);

  // 5) Forward-left for 3 s: left side stopped, right side forward
  //    (Left wheels RELEASE, right wheels FORWARD)
  //    “Left side” → M1 & M2; “Right side” → M3 & M4
  tankDrive(RELEASE, FORWARD);
  delay(T_MOVE);

  // 6) Pause 2 s
  releaseAll();
  delay(T_PAUSE);

  // 7) Forward-right for 3 s: left side forward, right side stopped
  //    (Left wheels FORWARD, right wheels RELEASE)
  tankDrive(FORWARD, RELEASE);
  delay(T_MOVE);

  // 8) Stop and end
  releaseAll();

  // Halt here; remove this if you want to repeat the sequence
  while (true) { }
}
