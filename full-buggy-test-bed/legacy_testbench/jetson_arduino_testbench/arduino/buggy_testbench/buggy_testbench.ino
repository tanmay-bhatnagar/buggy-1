// UNO R4 + L293D v1-style shield (74HC595) + Ultrasonic + (optional) Servo
// Serial protocol (115200):
//   MOVE <FWD|BACK|LEFT|RIGHT|SPIN_CW|SPIN_CCW|STOP> <secs>
//   ULTRASONIC ON <secs> [SPIN <ON|OFF>]
//   DIAG
//   ABORT
// Arduino -> Host:
//   STATUS READY
//   EVENT START ...
//   DATA ULS <cm> <angle> <t_ms>
//   EVENT COMPLETE ...
//   EVENT ABORTED
//   ERROR BUSY

#include <Arduino.h>

#define USE_SERVO 1
#if USE_SERVO
  #include <Servo.h>
#endif

// 74HC595 lines (matches your working test sketch)
const uint8_t SR_DATA  = 8;   // SER
const uint8_t SR_LATCH = 12;  // RCLK / LATCH
const uint8_t SR_CLK   = 4;   // SRCLK / CLOCK
const uint8_t SR_OE    = 7;   // OE (active LOW)

// L293D A/B bit mapping on the 74HC595 Q lines
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

// Polarity (true = flip FWD/REV for that motor) from your proven test.
const bool REV[4] = { false, true, false, true }; // M1..M4 (FL, RL, RR, FR)

// Ultrasonic pins (matches your test)
const uint8_t US_TRIG = A0;
const uint8_t US_ECHO = A1;

// Direction constants (no enum, no forward-declare drama)
const uint8_t DIR_REL = 0;
const uint8_t DIR_FWD = 1;
const uint8_t DIR_REV = 2;

// Servo config: quiet by default; only moves during ULTRASONIC SPIN ON
#if USE_SERVO
const uint8_t SERVO_PIN = 10;
const int SERVO_MIN = 30, SERVO_MAX = 150, SERVO_STEP = 2;
const unsigned long SERVO_TICK_MS = 20;

Servo scanServo;
int  servoAngle = (SERVO_MIN + SERVO_MAX)/2, servoDir = +1;
unsigned long nextServoTick = 0;
bool servoAttached = false, sweepEnabled = false;

void servo_stop() {
  sweepEnabled = false;
  if (servoAttached) { scanServo.detach(); servoAttached = false; }
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW); // hold line steady
}
void servo_start() {
  if (!servoAttached) { scanServo.attach(SERVO_PIN); scanServo.write(servoAngle); servoAttached = true; }
  sweepEnabled = true; nextServoTick = millis() + SERVO_TICK_MS;
}
void servo_tick() {
  if (!sweepEnabled || millis() < nextServoTick) return;
  servoAngle += servoDir * SERVO_STEP;
  if (servoAngle >= SERVO_MAX) { servoAngle = SERVO_MAX; servoDir = -1; }
  if (servoAngle <= SERVO_MIN) { servoAngle = SERVO_MIN; servoDir = +1; }
  scanServo.write(servoAngle);
  nextServoTick = millis() + SERVO_TICK_MS;
}
#endif

volatile bool abortFlag = false;
uint8_t latch_state = 0x00;

// Shift-register helpers
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
void setDirBits(uint8_t m, uint8_t intended) {
  uint8_t d = intended;
  if (intended != DIR_REL && REV[m]) d = (intended == DIR_FWD) ? DIR_REV : DIR_FWD;
  if (d == DIR_REL)      { setBit(MB[m].A,0); setBit(MB[m].B,0); }
  else if (d == DIR_FWD) { setBit(MB[m].A,1); setBit(MB[m].B,0); }
  else                   { setBit(MB[m].A,0); setBit(MB[m].B,1); }
}
void allREL() { for (int m=0; m<4; ++m) setDirBits(m, DIR_REL); }

// Ultrasonic
long readUltrasonicCM() {
  digitalWrite(US_TRIG, LOW); delayMicroseconds(2);
  digitalWrite(US_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(US_TRIG, LOW);
  unsigned long dur = pulseIn(US_ECHO, HIGH, 30000UL);
  if (!dur) return -1;
  return (long)(dur / 58UL);
}

// Serial line reader
bool readLine(String &out) {
  static String buf;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') { out = buf; buf = ""; return true; }
    buf += c;
    if (buf.length() > 120) buf = "";
  }
  return false;
}

// Actions
void doMove(const char* mode, float secs) {
  Serial.print(F("EVENT START MOVE ")); Serial.println(mode);
  abortFlag = false;
  #if USE_SERVO
  servo_stop(); // keep servo quiet during motion
  #endif

  if      (!strcmp(mode,"FWD"))      { for(int i=0;i<4;i++) setDirBits(i, DIR_FWD); }
  else if (!strcmp(mode,"BACK"))     { for(int i=0;i<4;i++) setDirBits(i, DIR_REV); }
  else if (!strcmp(mode,"LEFT"))     { setDirBits(0,DIR_REV); setDirBits(1,DIR_REV); setDirBits(2,DIR_FWD);  setDirBits(3,DIR_FWD);  }
  else if (!strcmp(mode,"RIGHT"))    { setDirBits(0,DIR_FWD); setDirBits(1,DIR_FWD); setDirBits(2,DIR_REV);  setDirBits(3,DIR_REV);  }
  else if (!strcmp(mode,"SPIN_CW"))  { setDirBits(0,DIR_FWD); setDirBits(1,DIR_FWD); setDirBits(2,DIR_REV);  setDirBits(3,DIR_REV);  }
  else if (!strcmp(mode,"SPIN_CCW")) { setDirBits(0,DIR_REV); setDirBits(1,DIR_REV); setDirBits(2,DIR_FWD);  setDirBits(3,DIR_FWD);  }
  else if (!strcmp(mode,"STOP"))     { allREL(); secs = 0; }
  else { allREL(); Serial.println(F("EVENT COMPLETE MOVE")); return; }

  unsigned long tEnd = millis() + (unsigned long)(secs * 1000.0f);
  while ((long)(tEnd - millis()) > 0) {
    if (Serial.available()) {
      String line; if (readLine(line)) {
        line.trim(); line.toUpperCase();
        if (line == "ABORT") abortFlag = true;
        else Serial.println(F("ERROR BUSY"));
      }
    }
    if (abortFlag) break;
    delay(5);
  }
  allREL();
  Serial.println(abortFlag ? F("EVENT ABORTED") : F("EVENT COMPLETE MOVE"));
}

void doUltrasonic(bool spin, float secs) {
  Serial.print(F("EVENT START ULTRASONIC "));
  Serial.println(spin ? F("SPIN_ON") : F("SPIN_OFF"));
  abortFlag = false;

  #if USE_SERVO
  if (spin) servo_start(); else servo_stop();
  #endif

  unsigned long tEnd = millis() + (unsigned long)(secs * 1000.0f);
  unsigned long nextSample = 0;

  while ((long)(tEnd - millis()) > 0) {
    if (Serial.available()) {
      String line; if (readLine(line)) {
        line.trim(); line.toUpperCase();
        if (line == "ABORT") abortFlag = true;
        else Serial.println(F("ERROR BUSY"));
      }
    }
    if (abortFlag) break;

    #if USE_SERVO
    servo_tick();
    #endif

    if (millis() >= nextSample) {
      long cm = readUltrasonicCM();
      int angleOut =
      #if USE_SERVO
        (spin ? servoAngle : -1);
      #else
        -1;
      #endif
      Serial.print(F("DATA ULS ")); Serial.print(cm);
      Serial.print(F(" ")); Serial.print(angleOut);
      Serial.print(F(" ")); Serial.println(millis());
      nextSample = millis() + 80; // ~12.5 Hz
    }
    delay(1);
  }

  #if USE_SERVO
  servo_stop();
  #endif

  Serial.println(abortFlag ? F("EVENT ABORTED") : F("EVENT COMPLETE ULTRASONIC"));
}

void doDiag() {
  Serial.println(F("EVENT START DIAG"));
  for (int i=0;i<4;i++) {
    setDirBits(i, DIR_FWD);
    delay(700);
    allREL();
    delay(250);
  }
  Serial.println(F("EVENT COMPLETE DIAG"));
}

// Parser
void parseAndRun(String line) {
  line.trim(); if (!line.length()) return;
  String up = line; up.toUpperCase();

  if (up == "ABORT") { abortFlag = true; allREL(); Serial.println(F("EVENT ABORTED")); return; }
  if (up == "DIAG")  { doDiag(); return; }

  if (up.startsWith("MOVE ")) {
    int a = up.indexOf(' ');
    int b = up.indexOf(' ', a+1);
    if (b < 0) { Serial.println(F("ERROR BAD_MOVE")); return; }
    String mode = up.substring(a+1, b);
    float secs = up.substring(b+1).toFloat();
    if (!(mode=="FWD"||mode=="BACK"||mode=="LEFT"||mode=="RIGHT"||mode=="SPIN_CW"||mode=="SPIN_CCW"||mode=="STOP")) {
      Serial.println(F("ERROR BAD_MODE")); return;
    }
    doMove(mode.c_str(), secs);
    return;
  }

  if (up.startsWith("ULTRASONIC ")) {
    int a = up.indexOf(' ');
    int b = up.indexOf(' ', a+1);
    if (b < 0) { Serial.println(F("ERROR BAD_ULS")); return; }
    String onoff = up.substring(a+1, b);
    int c = up.indexOf(' ', b+1);
    float secs = up.substring(b+1, c < 0 ? up.length() : c).toFloat();
    bool spin = false;
    if (c > 0) {
      String tail = up.substring(c+1); tail.trim();
      if (tail.startsWith("SPIN ")) { String v = tail.substring(5); v.trim(); spin = (v == "ON"); }
    }
    if (onoff != "ON") { Serial.println(F("EVENT COMPLETE ULTRASONIC")); return; }
    doUltrasonic(spin, secs);
    return;
  }

  Serial.println(F("ERROR BAD_CMD"));
}

// Setup/loop
void setup() {
  Serial.begin(115200);

  pinMode(SR_DATA,  OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_CLK,   OUTPUT);
  pinMode(SR_OE,    OUTPUT);
  digitalWrite(SR_OE, LOW);      // enable 595 outputs
  latch_state = 0x00; latchWrite();
  allREL();

  #if USE_SERVO
  servo_stop();                  // keep servo detached and quiet
  #endif

  pinMode(US_TRIG, OUTPUT); digitalWrite(US_TRIG, LOW);
  pinMode(US_ECHO, INPUT);

  delay(30);
  Serial.println(F("STATUS READY"));
}

void loop() {
  String line; if (readLine(line)) parseAndRun(line);
}
