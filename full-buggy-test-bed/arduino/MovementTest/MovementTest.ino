/*
  MovementTest.ino — Buggy v1 (UNO R4 WiFi + L293D v1 clone + 74HC595)

  What this does (for 1.1):
  - Drives 4 DC motors (M1..M4) using a v1-style L293D shield that uses a 74HC595 shift register for IN lines.
  - Lets you test: FORWARD, BACK, LEFT, RIGHT, SPIN-IN-PLACE (both directions), STOP, and KILL.
  - Prints chatty logs at 115200 so you can sanity-check direction/polarity.
  - Handles the common clone quirk: right motors’ EN may be ganged on D3; if they don’t respond, you can toggle an
    alternate mapping at runtime (see ENALT command notes below).

  === Wiring / Map (LOCKED for 1.1) ===

  Shift-register (controls IN1..IN8 to L293D inputs):
    SR_DATA  = D8
    SR_LATCH = D12
    SR_CLK   = D4
    SR_OE    = D7   (active-LOW; we hold LOW to enable outputs)

  Motor EN (PWM) pins — clone note:
    M1_EN = D11         // Front-Left   (locked)
    M2_EN = D3          // Rear-Left    (default)
    M3_EN = D3 or D11   // Rear-Right   (default D3; toggle at runtime with ENALT)
    M4_EN = D3 or D11   // Front-Right  (default D3; toggle at runtime with ENALT)

  Motor ↔ wheel orientation (logical → physical):
    M1 = Front-Left
    M2 = Rear-Left
    M3 = Rear-Right
    M4 = Front-Right

  Servo & Ultrasonic (unused in 1.1, here for context):
    SERVO = D10
    US_TRIG = A0, US_ECHO = A1

  Power sanity (non-negotiable):
    - 4×AA motor pack → shield MOTOR VIN(+) and MOTOR GND(−). VIN jumper REMOVED. ✅
    - Arduino logic from Jetson via USB-C. Jetson↔Arduino share ground via USB. ✅
    - Shield ties MOTOR GND to Arduino GND on most clones (common reference). ✅
    - If you ever see servo jitter under load, move servo to a separate 5–6V BEC and keep grounds common.

  Serial & safety:
    - BAUD = 115200
    - KILL is CASE-INSENSITIVE; it immediately brakes all motors and zeros the shift register.
    - ProjectShutdown (1.4) will perform the same zeroing at end-of-day so the buggy wakes up calm.

  === Runtime serial commands (case-insensitive) ===
    FWD         — forward
    BACK        — backward
    LEFT        — left turn (left wheels brake, right wheels forward)
    RIGHT       — right turn (right wheels brake, left wheels forward)
    SPINL       — spin in place left (left reverse, right forward)
    SPINR       — spin in place right (left forward, right reverse)
    STOP        — brake all motors (fast stop)
    KILL        — emergency stop + zero all lines (also used at boot)

    SPEED <0..255>     — set PWM (default 255). Example: SPEED 180
    TIME  <ms>         — set move duration for one-shot commands (default 1200ms). Example: TIME 800
    TEST               — runs a short script: FWD → BACK → LEFT → RIGHT → SPINL → SPINR → STOP
    ENALT ON|OFF       — toggle alternate EN mapping for right motors:
                         OFF (default): right EN uses D3
                         ON:            right EN uses D11
                         Use if right side doesn’t respond on your unit.

  Notes on direction polarity:
    REV[] below encodes per-motor inversion so “forward” actually moves the buggy forward in your wiring.
    Current default = {true, false, true, false} for {M1,M2,M3,M4}, based on prior tests.
    If any wheel is backwards, flip its REV flag to the opposite value.
*/

#include <Arduino.h>

// ---------------------------- Shift Register (74HC595) ----------------------------

constexpr uint8_t SR_DATA  = 8;   // SER
constexpr uint8_t SR_LATCH = 12;  // RCLK
constexpr uint8_t SR_CLK   = 4;   // SRCLK
constexpr uint8_t SR_OE    = 7;   // Output Enable (active LOW)

volatile uint8_t latch_state = 0x00;  // IN1..IN8 bitfield (bit0=IN1 ... bit7=IN8)

// Bit positions for IN1..IN8. Most v1 shields wire 1:1 to L293D inputs.
enum : uint8_t {
  IN1_BIT = 0, IN2_BIT = 1,  // Motor channel A
  IN3_BIT = 2, IN4_BIT = 3,  // Motor channel B
  IN5_BIT = 4, IN6_BIT = 5,  // Motor channel C
  IN7_BIT = 6, IN8_BIT = 7   // Motor channel D
};

// Motor-to-channel map (logical M1..M4 → L293D input pairs). Adjust only if your shield deviates.
struct Channel { uint8_t inA_bit; uint8_t inB_bit; };
constexpr Channel CH_M1 = { IN1_BIT, IN2_BIT };  // M1 uses IN1/IN2
constexpr Channel CH_M2 = { IN3_BIT, IN4_BIT };  // M2 uses IN3/IN4
constexpr Channel CH_M3 = { IN5_BIT, IN6_BIT };  // M3 uses IN5/IN6
constexpr Channel CH_M4 = { IN7_BIT, IN8_BIT };  // M4 uses IN7/IN8

// ---------------------------- EN (PWM) Pins & Alt Mapping ----------------------------

// Left side (fixed)
constexpr uint8_t M1_EN = 11;  // Front-Left
constexpr uint8_t M2_EN = 3;   // Rear-Left

// Right side (clone quirk): default D3, can flip to D11 at runtime via ENALT command.
bool useAltEnForRight = false; // false => D3 (default). true => D11.
constexpr uint8_t RIGHT_EN_DEFAULT = 3;
constexpr uint8_t RIGHT_EN_ALT     = 11;

// Helper to resolve current EN pins for right side
inline uint8_t M3_EN() { return useAltEnForRight ? RIGHT_EN_ALT : RIGHT_EN_DEFAULT; }
inline uint8_t M4_EN() { return useAltEnForRight ? RIGHT_EN_ALT : RIGHT_EN_DEFAULT; }

// ---------------------------- Behavior tuning ----------------------------

uint8_t PWM_VALUE = 255;       // Full send by default
uint32_t MOVE_TIME_MS = 1200;  // Duration for one-shot moves (TIME command)

// Per-motor polarity so that "forward" means actual forward motion on your wiring.
bool REV[4] = {
  true,   // M1 (Front-Left)   — true = invert
  false,  // M2 (Rear-Left)
  true,   // M3 (Rear-Right)
  false   // M4 (Front-Right)
};

// ---------------------------- Low-level SR utilities ----------------------------

void srApply() {
  // Latch out the current latch_state to the 74HC595
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLK, MSBFIRST, latch_state);
  digitalWrite(SR_LATCH, HIGH);
}

void srSetBit(uint8_t bitIndex, bool high) {
  if (high) latch_state |=  (1 << bitIndex);
  else      latch_state &= ~(1 << bitIndex);
  srApply();
}

void srZeroAll() {
  latch_state = 0x00;
  srApply();
}

// ---------------------------- Motor helpers ----------------------------

enum Dir : uint8_t { BRAKE = 0, FWD = 1, REVv = 2 };

void motorSet(const Channel& ch, Dir d) {
  // For each channel: INA/INB control H-bridge direction or brake
  switch (d) {
    case BRAKE: srSetBit(ch.inA_bit, LOW); srSetBit(ch.inB_bit, LOW); break;
    case FWD:   srSetBit(ch.inA_bit, HIGH); srSetBit(ch.inB_bit, LOW); break;
    case REVv:  srSetBit(ch.inA_bit, LOW);  srSetBit(ch.inB_bit, HIGH); break;
  }
}

void allBrake() {
  motorSet(CH_M1, BRAKE);
  motorSet(CH_M2, BRAKE);
  motorSet(CH_M3, BRAKE);
  motorSet(CH_M4, BRAKE);
  analogWrite(M1_EN, 0);
  analogWrite(M2_EN, 0);
  analogWrite(M3_EN(), 0);
  analogWrite(M4_EN(), 0);
}

void applyPWMAll(uint8_t pwm) {
  analogWrite(M1_EN, pwm);
  analogWrite(M2_EN, pwm);
  analogWrite(M3_EN(), pwm);
  analogWrite(M4_EN(), pwm);
}

// High-level moves (respecting REV flags):
void moveForward() {
  motorSet(CH_M1, REV[0] ? REVv : FWD);
  motorSet(CH_M2, REV[1] ? REVv : FWD);
  motorSet(CH_M3, REV[2] ? REVv : FWD);
  motorSet(CH_M4, REV[3] ? REVv : FWD);
  applyPWMAll(PWM_VALUE);
}

void moveBackward() {
  motorSet(CH_M1, REV[0] ? FWD : REVv);
  motorSet(CH_M2, REV[1] ? FWD : REVv);
  motorSet(CH_M3, REV[2] ? FWD : REVv);
  motorSet(CH_M4, REV[3] ? FWD : REVv);
  applyPWMAll(PWM_VALUE);
}

void turnLeft() {
  // Left wheels brake, right wheels forward
  motorSet(CH_M1, BRAKE);
  motorSet(CH_M2, BRAKE);
  motorSet(CH_M3, REV[2] ? REVv : FWD);
  motorSet(CH_M4, REV[3] ? REVv : FWD);
  applyPWMAll(PWM_VALUE);
}

void turnRight() {
  // Right wheels brake, left wheels forward
  motorSet(CH_M1, REV[0] ? REVv : FWD);
  motorSet(CH_M2, REV[1] ? REVv : FWD);
  motorSet(CH_M3, BRAKE);
  motorSet(CH_M4, BRAKE);
  applyPWMAll(PWM_VALUE);
}

void spinLeft() {
  // Left reverse, right forward
  motorSet(CH_M1, REV[0] ? FWD : REVv);
  motorSet(CH_M2, REV[1] ? FWD : REVv);
  motorSet(CH_M3, REV[2] ? REVv : FWD);
  motorSet(CH_M4, REV[3] ? REVv : FWD);
  applyPWMAll(PWM_VALUE);
}

void spinRight() {
  // Left forward, right reverse
  motorSet(CH_M1, REV[0] ? REVv : FWD);
  motorSet(CH_M2, REV[1] ? REVv : FWD);
  motorSet(CH_M3, REV[2] ? FWD : REVv);
  motorSet(CH_M4, REV[3] ? FWD : REVv);
  applyPWMAll(PWM_VALUE);
}

// ---------------------------- Command handling ----------------------------

String rx;

void printHelp() {
  Serial.println(F("\nCommands: FWD | BACK | LEFT | RIGHT | SPINL | SPINR | STOP | KILL"));
  Serial.println(F("          SPEED <0..255>   | TIME <ms>"));
  Serial.println(F("          ENALT ON|OFF     | TEST"));
  Serial.println(F("Notes: ENALT toggles right-side EN between D3 (OFF) and D11 (ON)."));
}

void doTestScript() {
  const uint16_t pause = 300;
  Serial.println(F("[TEST] FORWARD"));
  moveForward(); delay(MOVE_TIME_MS); allBrake(); delay(pause);

  Serial.println(F("[TEST] BACK"));
  moveBackward(); delay(MOVE_TIME_MS); allBrake(); delay(pause);

  Serial.println(F("[TEST] LEFT"));
  turnLeft(); delay(MOVE_TIME_MS); allBrake(); delay(pause);

  Serial.println(F("[TEST] RIGHT"));
  turnRight(); delay(MOVE_TIME_MS); allBrake(); delay(pause);

  Serial.println(F("[TEST] SPINL"));
  spinLeft(); delay(MOVE_TIME_MS); allBrake(); delay(pause);

  Serial.println(F("[TEST] SPINR"));
  spinRight(); delay(MOVE_TIME_MS); allBrake(); delay(pause);

  Serial.println(F("[TEST] STOP"));
  allBrake();
}

void handleCommand(const String& cmdLine) {
  // uppercase & trim
  String s = cmdLine;
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "FWD")          { Serial.println(F("→ FORWARD")); moveForward(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s == "BACK")    { Serial.println(F("→ BACK"));    moveBackward(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s == "LEFT")    { Serial.println(F("→ LEFT"));    turnLeft(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s == "RIGHT")   { Serial.println(F("→ RIGHT"));   turnRight(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s == "SPINL")   { Serial.println(F("→ SPIN LEFT"));  spinLeft(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s == "SPINR")   { Serial.println(F("→ SPIN RIGHT")); spinRight(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s == "STOP")    { Serial.println(F("■ STOP")); allBrake(); }
  else if (s == "KILL")    {
    Serial.println(F("!! KILL: HARD BRAKE + ZERO SR"));
    allBrake();
    srZeroAll(); // ensure all IN low
  }
  else if (s.startsWith("SPEED")) {
    int sp = s.substring(5).toInt();
    sp = constrain(sp, 0, 255);
    PWM_VALUE = (uint8_t)sp;
    Serial.print(F("PWM_VALUE = ")); Serial.println(PWM_VALUE);
  }
  else if (s.startsWith("TIME")) {
    int ms = s.substring(4).toInt();
    ms = max(0, ms);
    MOVE_TIME_MS = (uint32_t)ms;
    Serial.print(F("MOVE_TIME_MS = ")); Serial.println((int)MOVE_TIME_MS);
  }
  else if (s == "TEST") {
    doTestScript();
  }
  else if (s.startsWith("ENALT")) {
    // ENALT ON|OFF
    if (s.indexOf("ON") > 0) {
      useAltEnForRight = true;
      Serial.println(F("ENALT=ON (right EN uses D11)"));
    } else if (s.indexOf("OFF") > 0) {
      useAltEnForRight = false;
      Serial.println(F("ENALT=OFF (right EN uses D3)"));
    } else {
      Serial.print(F("ENALT is currently "));
      Serial.println(useAltEnForRight ? F("ON (D11)") : F("OFF (D3)"));
    }
    // Re-apply current PWM to the newly selected pins (others go low)
    analogWrite(RIGHT_EN_DEFAULT, useAltEnForRight ? 0 : PWM_VALUE);
    analogWrite(RIGHT_EN_ALT,     useAltEnForRight ? PWM_VALUE : 0);
  }
  else if (s == "HELP" || s == "?") {
    printHelp();
  }
  else {
    Serial.print(F("Unknown: ")); Serial.println(s);
    printHelp();
  }
}

// ---------------------------- Setup / Loop ----------------------------

void setup() {
  Serial.begin(115200);
  delay(50);

  // Shift register pins
  pinMode(SR_DATA, OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_CLK, OUTPUT);
  pinMode(SR_OE, OUTPUT);

  digitalWrite(SR_OE, LOW);   // enable outputs (active-LOW)
  latch_state = 0x00;         // zero all IN lines at boot (clone shields can wake noisy)
  srApply();

  // EN pins
  pinMode(M1_EN, OUTPUT);
  pinMode(M2_EN, OUTPUT);
  pinMode(RIGHT_EN_DEFAULT, OUTPUT);
  pinMode(RIGHT_EN_ALT, OUTPUT);

  // Ensure everything is off at boot
  allBrake();

  Serial.println(F("\n[MovementTest 1.1] UNO R4 + L293D v1 clone + 74HC595"));
  Serial.println(F("Pins: SR(DATA=8,LATCH=12,CLK=4,OE=7), EN(L: D11,D3 | R: D3 or D11)"));
  Serial.println(F("Wheels: M1=FL, M2=RL, M3=RR, M4=FR"));
  Serial.println(F("Type HELP for commands. KILL is case-insensitive."));
  Serial.println(F("Tip: If right motors don’t move, send: ENALT ON"));
}

void loop() {
  // Read line-by-line commands from Serial
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      handleCommand(rx);
      rx = "";
    } else {
      rx += c;
      // safety: if someone pastes KILL without newline, act immediately once it matches
      String up = rx; up.toUpperCase();
      if (up.endsWith("KILL")) {
        handleCommand("KILL");
        rx = "";
      }
    }
  }
}