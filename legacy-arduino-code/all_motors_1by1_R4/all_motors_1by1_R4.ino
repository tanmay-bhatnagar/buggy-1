// UNO R4 + L293D Motor Shield v1 (74HC595) — per-motor EN test (2s each), STOP/GO/KILL
// Set each motor's EN pin below based on what actually spun on your shield.

#include <Arduino.h>

// ---- 74HC595 pins (v1 shields) ----
const uint8_t SR_DATA  = 8;    // SER
const uint8_t SR_LATCH = 12;   // RCLK / LATCH
const uint8_t SR_CLK   = 4;    // SRCLK / CLOCK
const uint8_t SR_OE    = 7;    // Output Enable (active LOW). Many boards hard-tie this LOW; we also drive LOW.

// ---- Per-motor EN pins (EDIT THESE if needed) ----
uint8_t M_EN[4] = {
  11, // M1 (Front-Left / TL)  -> you observed this needs 11
  3,  // M2 (Rear-Left  / BL)  -> you observed this needs 3
  3,  // M3 (Rear-Right / BR)  -> start with 3; if it doesn't move, change to 11
  3   // M4 (Front-Right/ TR)  -> start with 3; if it doesn't move, change to 11
};

// Your confirmed polarity (true = reversed wiring)
const bool REV[4] = { true, false, true, false }; // M1,M2,M3,M4

// 74HC595 bit mapping used by Adafruit v1 shields
#define M1_A_BIT 2
#define M1_B_BIT 3
#define M2_A_BIT 1
#define M2_B_BIT 4
#define M3_A_BIT 5
#define M3_B_BIT 7
#define M4_A_BIT 0
#define M4_B_BIT 6

struct Mbits { uint8_t A, B; };
Mbits MB[4] = {
  { M1_A_BIT, M1_B_BIT }, // M1
  { M2_A_BIT, M2_B_BIT }, // M2
  { M3_A_BIT, M3_B_BIT }, // M3
  { M4_A_BIT, M4_B_BIT }  // M4
};

enum Dir: uint8_t { REL=0, FWD=1, REVV=2 };

const uint8_t  SPEED  = 200;  // 0..255
const uint16_t RUN_MS = 2000; // 2 s per wheel
const uint16_t GAP_MS = 300;

bool running = true, killed = false;
uint8_t latch_state = 0x00;

// ---- 74HC595 helpers ----
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

// ---- Motor control ----
void setDirBits(uint8_t m, Dir d) {
  Dir dd = d;
  if (REV[m] && d != REL) dd = (d == FWD) ? REVV : FWD;
  switch (dd) {
    case REL:  setBit(MB[m].A, 0); setBit(MB[m].B, 0); break;
    case FWD:  setBit(MB[m].A, 1); setBit(MB[m].B, 0); break;
    case REVV: setBit(MB[m].A, 0); setBit(MB[m].B, 1); break;
  }
}
void motorStop(uint8_t m) {
  analogWrite(M_EN[m], 0);
  setDirBits(m, REL);
}
void enableOnly(uint8_t m) {
  // Force all EN pins LOW, then enable chosen motor
  for (int i=0;i<4;++i) { pinMode(M_EN[i], OUTPUT); digitalWrite(M_EN[i], LOW); }
  analogWrite(M_EN[m], SPEED);
}

// ---- Safety / commands ----
void killAll() {
  for (int i=0;i<4;++i) { analogWrite(M_EN[i], 0); pinMode(M_EN[i], OUTPUT); digitalWrite(M_EN[i], LOW); }
  latch_state = 0x00; latchWrite();
  digitalWrite(LED_BUILTIN, LOW);
  killed = true;
  while (true) { delay(1000); }
}
void handleSerial() {
  if (!Serial.available()) return;
  String s = Serial.readStringUntil('\n'); s.trim(); s.toUpperCase();
  if (s == F("STOP")) { running=false; for(int i=0;i<4;++i) motorStop(i); Serial.println(F("[STATE] STOPPED.")); }
  else if (s == F("GO")) { running=true; Serial.println(F("[STATE] RUNNING.")); }
  else if (s == F("KILL")) { Serial.println(F("[STATE] KILLED.")); killAll(); }
}
void waitMs(uint32_t ms) {
  const uint16_t step=20;
  while (ms && !killed) {
    handleSerial();
    if (!running) { for(int i=0;i<4;++i) motorStop(i); }
    delay(step);
    ms = (ms>step)?(ms-step):0;
  }
}

void runOne(uint8_t m, const __FlashStringHelper* name) {
  Serial.print(F("[RUN] ")); Serial.println(name);
  // Set all REL first, then target FWD
  for (int i=0;i<4;++i) setDirBits(i, REL);
  setDirBits(m, FWD);
  enableOnly(m);
  waitMs(RUN_MS);
  motorStop(m);
  waitMs(GAP_MS);
}

void setup() {
  Serial.begin(115200); while(!Serial) {}
  pinMode(LED_BUILTIN, OUTPUT); digitalWrite(LED_BUILTIN, HIGH);

  // 74HC595 wiring
  pinMode(SR_DATA, OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_CLK, OUTPUT);
  pinMode(SR_OE, OUTPUT); digitalWrite(SR_OE, LOW); // enable outputs (if present)

  // Prime latch safe
  latch_state = 0x00; latchWrite();

  // EN pins to outputs, LOW
  for (int i=0;i<4;++i) { pinMode(M_EN[i], OUTPUT); digitalWrite(M_EN[i], LOW); }

  Serial.println(F("\n[R4 v1-shield per-motor EN test] Commands: STOP | GO | KILL"));
  Serial.println(F("Defaults: M1->11, M2->3, M3->3, M4->3 (edit M_EN[] at top if needed)."));
}

void loop() {
  if (killed) return;

  runOne(0, F("M1 (Top-Left)"));
  runOne(3, F("M4 (Top-Right)"));
  runOne(1, F("M2 (Bottom-Left)"));
  runOne(2, F("M3 (Bottom-Right)"));

  Serial.println(F("[STATE] Sequence complete. Auto-KILL."));
  killAll();
}
