/********************************************************************
 * UNO R4 + L293D v1-style shield (74HC595) + Servo + Ultrasonic
 * EN pins on this clone are effectively always HIGH; we control
 * motion solely via A/B bits latched into the 74HC595.
 *
 * Runs (with pauses between):
 *   Forward 1s, Back 1s, Left 1s, Right 1s, Spin CW 5s, Spin CCW 5s
 *
 * Servo + ultrasonic:
 *   Servo sweeps continuously left<->right during the entire test.
 *   Distance is sampled continuously and logged with the current angle.
 *
 * Serial (115200): STOP | GO | KILL | HELP | CLS
 ********************************************************************/

#include <Arduino.h>
#include <Servo.h>

// ── TUNABLE DURATIONS (ms) ──────────────────────────────────────────
uint16_t T_FWD   = 1000;
uint16_t T_BACK  = 1000;
uint16_t T_LEFT  = 1000;
uint16_t T_RIGHT = 1000;
uint16_t T_CW    = 5000;
uint16_t T_CCW   = 5000;
uint16_t T_PAUSE = 2000;

// ── Servo scan configuration ────────────────────────────────────────
const uint8_t SERVO_PIN         = 10;
const int     SERVO_MIN_ANGLE   = 30;
const int     SERVO_MAX_ANGLE   = 150;
const uint16_t SERVO_STEP_MS    = 20;
const uint8_t  SERVO_STEP_DEG   = 2;

// ── Ultrasonic (HC-SR04) pins ───────────────────────────────────────
const uint8_t US_TRIG   = A0;
const uint8_t US_ECHO   = A1;
const uint16_t DIST_SAMPLE_MS = 100;
const uint32_t ECHO_TIMEOUT_US = 30000UL; // ~5 m

// ── 74HC595 control lines (Adafruit v1 convention) ──────────────────
const uint8_t SR_DATA  = 8;   // SER
const uint8_t SR_LATCH = 12;  // RCLK / LATCH
const uint8_t SR_CLK   = 4;   // SRCLK / CLOCK
const uint8_t SR_OE    = 7;   // OE (active LOW). Many clones tie LOW; we also drive LOW.

// ── L293D A/B bit mapping on the 74HC595 Q-lines ───────────────────
#define M1_A_BIT 2
#define M1_B_BIT 3
#define M2_A_BIT 1
#define M2_B_BIT 4
#define M3_A_BIT 5
#define M3_B_BIT 7
#define M4_A_BIT 0
#define M4_B_BIT 6

struct Mbits { uint8_t A, B; };
Mbits MB[4] = { {M1_A_BIT,M1_B_BIT}, {M2_A_BIT,M2_B_BIT}, {M3_A_BIT,M3_B_BIT}, {M4_A_BIT,M4_B_BIT} };

// Your confirmed polarity: true = flip FWD/REV for that motor
const bool REV[4] = { false, true, false, true }; // M1..M4

// ── Types & state ───────────────────────────────────────────────────
enum Dir : uint8_t { REL=0, FWD=1, REVV=2 }; // REL = A=B=0 (acts as brake since EN≡1)
bool running = true, killed = false;
uint8_t latch_state = 0x00;

Servo pan;
int   servoAngle   = 90;
int   servoDir     = +1;
unsigned long nextServoStep = 0;
unsigned long nextDistSample = 0;

// ── Serial "clear screen" helper ────────────────────────────────────
void serialClear() {
  Serial.write(27); Serial.print("[2J");
  Serial.write(27); Serial.print("[H");
  for (int i=0;i<24;++i) Serial.println();
  Serial.println(F("────────────────────────────────────────────────────────"));
}

// ── 74HC595 helpers ─────────────────────────────────────────────────
void latchWrite() {
  digitalWrite(SR_LATCH, LOW);
  for (int i = 7; i >= 0; --i) {
    digitalWrite(SR_CLK, LOW);
    digitalWrite(SR_DATA, (latch_state >> i) & 0x1);
    digitalWrite(SR_CLK, HIGH);
  }
  digitalWrite(SR_LATCH, HIGH);
}
void setBit(uint8_t bit, bool val) {
  if (val) latch_state |=  (1 << bit);
  else     latch_state &= ~(1 << bit);
  latchWrite();
}
void setDirBits(uint8_t m, Dir intended) {
  Dir d = intended;
  if (intended != REL && REV[m]) d = (intended == FWD) ? REVV : FWD;
  if (d==REL)      { setBit(MB[m].A,0); setBit(MB[m].B,0); }   // brake (EN≡1)
  else if (d==FWD) { setBit(MB[m].A,1); setBit(MB[m].B,0); }
  else             { setBit(MB[m].A,0); setBit(MB[m].B,1); }   // REVV
}
void allREL() { for (int m=0;m<4;++m) setDirBits(m, REL); }

// ── Ultrasonic read ─────────────────────────────────────────────────
long readDistanceCM(uint32_t timeout_us = ECHO_TIMEOUT_US) {
  digitalWrite(US_TRIG, LOW); delayMicroseconds(2);
  digitalWrite(US_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(US_TRIG, LOW);
  unsigned long dur = pulseIn(US_ECHO, HIGH, timeout_us);
  if (dur == 0) return -1; // timeout
  return (long)(dur / 58UL); // ~58 us per cm
}

// ── Continuous servo sweep + distance logging ───────────────────────
void servoTick() {
  unsigned long now = millis();
  if (now < nextServoStep) return;

  servoAngle += servoDir * SERVO_STEP_DEG;
  if (servoAngle >= SERVO_MAX_ANGLE) { servoAngle = SERVO_MAX_ANGLE; servoDir = -1; }
  if (servoAngle <= SERVO_MIN_ANGLE) { servoAngle = SERVO_MIN_ANGLE; servoDir = +1; }
  pan.write(servoAngle);

  nextServoStep = now + SERVO_STEP_MS;
}

void distanceTick() {
  unsigned long now = millis();
  if (now < nextDistSample) return;

  long d = readDistanceCM();
  Serial.print(F("[SCAN] ang="));
  if (servoAngle < 100) Serial.print('0');
  if (servoAngle < 10)  Serial.print('0');
  Serial.print(servoAngle);
  Serial.print(F("°, dist="));
  if (d < 0) Serial.println(F("timeout"));
  else { Serial.print(d); Serial.println(F(" cm")); }

  nextDistSample = now + DIST_SAMPLE_MS;
}

// ── Commands & cooperative wait ─────────────────────────────────────
void killAll() {
  allREL();                          // with EN≡1, REL = active brake
  latch_state = 0x00; latchWrite();  // zero bits for good measure
  digitalWrite(LED_BUILTIN, LOW);
  killed = true;
  Serial.println(F("[STATE] KILLED. Reset/power-cycle to recover."));
  while (true) { delay(1000); }
}

void handleSerial() {
  if (!Serial.available()) return;
  String s = Serial.readStringUntil('\n'); s.trim(); s.toUpperCase();
  if      (s == F("STOP")) { running=false; allREL(); Serial.println(F("[STATE] STOPPED (brake).")); } // <- fixed
  else if (s == F("GO"))   { running=true;  Serial.println(F("[STATE] RUNNING.")); }
  else if (s == F("KILL")) { killAll(); }
  else if (s == F("HELP")) { Serial.println(F("Commands: STOP | GO | KILL | CLS")); }
  else if (s == F("CLS"))  { serialClear(); }
}

void waitMs(uint32_t ms, const __FlashStringHelper* label) {
  const uint16_t slice = 10; // small slice so scan feels smooth
  if (label) { Serial.print(F("[WAIT] ")); Serial.print(label); Serial.print(F(" ~")); Serial.print(ms); Serial.println(F(" ms")); }
  while (ms && !killed) {
    handleSerial();
    // keep scanning + logging regardless of running state
    servoTick();
    distanceTick();

    if (!running) allREL(); // motor brake while paused

    delay(slice);
    ms = (ms > slice) ? (ms - slice) : 0;
  }
}

// ── Moves (A/B only; EN is always enabled on this clone) ────────────
void moveForward(uint32_t ms) {
  Serial.println(F("[MOVE] Forward"));
  for (int m=0;m<4;++m) setDirBits(m, FWD);
  waitMs(ms, F("Forward"));
  allREL();
}
void moveBackward(uint32_t ms) {
  Serial.println(F("[MOVE] Backward"));
  for (int m=0;m<4;++m) setDirBits(m, REVV);
  waitMs(ms, F("Backward"));
  allREL();
}
void moveLeftArc(uint32_t ms) {
  Serial.println(F("[MOVE] Left (arc): left REL, right FWD"));
  setDirBits(0, REL); setDirBits(1, REL);   // left off (brake)
  setDirBits(2, FWD); setDirBits(3, FWD);   // right forward
  waitMs(ms, F("Left arc"));
  allREL();
}
void moveRightArc(uint32_t ms) {
  Serial.println(F("[MOVE] Right (arc): left FWD, right REL"));
  setDirBits(0, FWD); setDirBits(1, FWD);   // left forward
  setDirBits(2, REL); setDirBits(3, REL);   // right off (brake)
  waitMs(ms, F("Right arc"));
  allREL();
}
void spinCW(uint32_t ms) {   // clockwise: left FWD, right REV
  Serial.println(F("[MOVE] In-place Spin CW"));
  setDirBits(0, FWD); setDirBits(1, FWD);
  setDirBits(2, REVV); setDirBits(3, REVV);
  waitMs(ms, F("Spin CW"));
  allREL();
}
void spinCCW(uint32_t ms) {  // counter-clockwise: left REV, right FWD
  Serial.println(F("[MOVE] In-place Spin CCW"));
  setDirBits(0, REVV); setDirBits(1, REVV);
  setDirBits(2, FWD);  setDirBits(3, FWD);
  waitMs(ms, F("Spin CCW"));
  allREL();
}

// ── Arduino setup/loop ──────────────────────────────────────────────
void setup() {
  Serial.begin(115200); while (!Serial) {}
  pinMode(LED_BUILTIN, OUTPUT); digitalWrite(LED_BUILTIN, HIGH);
  serialClear();

  // 74HC595
  pinMode(SR_DATA, OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_CLK, OUTPUT);
  pinMode(SR_OE, OUTPUT); digitalWrite(SR_OE, LOW); // enable outputs (if present)
  latch_state = 0x00; latchWrite();                 // prime safe state (all REL)

  // Ultrasonic
  pinMode(US_TRIG, OUTPUT); digitalWrite(US_TRIG, LOW);
  pinMode(US_ECHO, INPUT);

  // Servo: start centered; prime sweep timing
  pan.attach(SERVO_PIN);
  servoAngle = (SERVO_MIN_ANGLE + SERVO_MAX_ANGLE) / 2;
  pan.write(servoAngle);
  nextServoStep  = millis() + SERVO_STEP_MS;
  nextDistSample = millis() + DIST_SAMPLE_MS;

  Serial.println(F("[INIT] R4 + v1-shield (EN ≡ 1) + Servo sweep + Ultrasonic logging ready."));
  Serial.println(F("       Commands: STOP | GO | KILL | HELP | CLS"));
}

void loop() {
  if (killed) return;

  // the servo keeps sweeping + ultrasonic keeps logging inside waitMs()

  moveForward(T_FWD);     waitMs(T_PAUSE, F("Pause"));
  moveBackward(T_BACK);   waitMs(T_PAUSE, F("Pause"));
  moveLeftArc(T_LEFT);    waitMs(T_PAUSE, F("Pause"));
  moveRightArc(T_RIGHT);  waitMs(T_PAUSE, F("Pause"));
  spinCW(T_CW);           waitMs(T_PAUSE, F("Pause"));
  spinCCW(T_CCW);

  Serial.println(F("[STATE] Sequence complete. Auto-KILL."));
  killAll();
}
