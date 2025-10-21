// UNO R4 + L293D v1-style shield (74HC595) + Ultrasonic + Servo
// Compact protocol @115200 (bidirectional monitor)
// Commands: F/B/L/R<n>, S, P<deg>, T<n>, Q, H
//  - T<n>: safety threshold in cm (0 disables). Debounced: need 3 consecutive hits <= n.
// Telemetry: STATUS READY, STAT ..., ULS cm=..., EVT stop=<command|safety>

#include <Arduino.h>
#include <Servo.h>

// ---------------- Pins (match your wiring) -----------------
const uint8_t SR_DATA  = 8;   // 74HC595 SER
const uint8_t SR_LATCH = 12;  // RCLK / LATCH
const uint8_t SR_CLK   = 4;   // SRCLK / CLOCK
const uint8_t SR_OE    = 7;   // OE (active LOW) — PWM gate for speed

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
const bool REV[4] = { false, true, false, true }; // FL, RL, RR, FR flip map

const uint8_t US_TRIG = A0;   // Ultrasonic TRIG
const uint8_t US_ECHO = A1;   // Ultrasonic ECHO

const uint8_t SERVO_PIN = 10; // Servo signal
const int SERVO_MIN = 30, SERVO_MAX = 150, SERVO_STEP = 2;
const unsigned long SERVO_TICK_MS = 20;

// ---------------- Types BEFORE usage (fix) -----------------
// Avoid forward-declare issues by defining the enum up here.
enum Dir : uint8_t { REL=0, FWD=1, REVv=2 };

// ---------------- State -----------------------------------
Servo scanServo;
int  servoAngle = (SERVO_MIN + SERVO_MAX)/2;
int  servoDir   = +1;
bool servoAttached = false;
bool sweepEnabled  = false;
unsigned long nextServoTick = 0;

volatile bool abortFlag = false;
uint8_t latch_state = 0x00;
char mode = 'S';
uint8_t speedVal = 0;         // 0..255
int stopThresholdCm = 25;     // 0 disables; default
long lastCM = -1;

// ---------------- Shift register helpers ------------------
void latchWrite(){
  digitalWrite(SR_LATCH, LOW);
  for (int i=7; i>=0; --i){
    digitalWrite(SR_CLK, LOW);
    digitalWrite(SR_DATA, (latch_state >> i) & 0x1);
    digitalWrite(SR_CLK, HIGH);
  }
  digitalWrite(SR_LATCH, HIGH);
}
void setBit(uint8_t bit, bool val){
  if (val) latch_state |=  (1 << bit);
  else     latch_state &= ~(1 << bit);
  latchWrite();
}
void setDirBits(uint8_t m, Dir intended){
  Dir d = intended;
  if (intended != REL && REV[m]) d = (intended == FWD) ? REVv : FWD;
  if (d == REL)      { setBit(MB[m].A,0); setBit(MB[m].B,0); }
  else if (d == FWD) { setBit(MB[m].A,1); setBit(MB[m].B,0); }
  else               { setBit(MB[m].A,0); setBit(MB[m].B,1); }
}
void allREL(){ for (int i=0;i<4;i++) setDirBits(i, REL); }

void pwmSpeed(uint8_t spd){
  speedVal = spd;
  // OE is active LOW; analogWrite duty 0..255; duty=0 => fully enabled
  uint8_t duty = 255 - spd; // spd=255 -> duty=0; spd=0 -> duty=255
  analogWrite(SR_OE, duty);
}

// ---------------- Ultrasonic -------------------------------
long readUltrasonicCM(){
  digitalWrite(US_TRIG, LOW); delayMicroseconds(2);
  digitalWrite(US_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(US_TRIG, LOW);
  unsigned long dur = pulseIn(US_ECHO, HIGH, 30000UL);
  if (!dur) return -1; // timeout
  long cm = (long)(dur / 58UL);
  if (cm < 0) cm = -1;
  return cm;
}

// ---------------- Servo -----------------------------------
void servo_stopSweep(){
  sweepEnabled = false;
  if (servoAttached){ scanServo.detach(); servoAttached=false; }
  pinMode(SERVO_PIN, OUTPUT); digitalWrite(SERVO_PIN, LOW);
}
void servo_startSweep(){
  if (!servoAttached){ scanServo.attach(SERVO_PIN); scanServo.write(servoAngle); servoAttached=true; }
  sweepEnabled = true; nextServoTick = millis() + SERVO_TICK_MS;
}
void servo_tick(){
  if (!sweepEnabled || millis() < nextServoTick) return;
  servoAngle += servoDir * SERVO_STEP;
  if (servoAngle >= SERVO_MAX){ servoAngle = SERVO_MAX; servoDir = -1; }
  if (servoAngle <= SERVO_MIN){ servoAngle = SERVO_MIN; servoDir = +1; }
  scanServo.write(servoAngle);
  nextServoTick = millis() + SERVO_TICK_MS;
}

// ---------------- Serial utils -----------------------------
bool readLine(String &out){ static String buf; while(Serial.available()){ char c=(char)Serial.read(); if(c=='\r') continue; if(c=='\n'){ out=buf; buf=""; return true; } buf+=c; if(buf.length()>120) buf=""; } return false; }

void printStat(){
  Serial.print(F("STAT mode=")); Serial.print(mode);
  Serial.print(F(" spd=")); Serial.print((int)speedVal);
  Serial.print(F(" thresh=")); Serial.print(stopThresholdCm);
  Serial.print(F(" last_cm=")); Serial.print(lastCM);
  Serial.print(F(" sweep=")); Serial.println(sweepEnabled?1:0);
}
void printULS(){
  Serial.print(F("ULS cm=")); Serial.print(lastCM);
  Serial.print(F(" angle=")); Serial.print(sweepEnabled?servoAngle:-1);
  Serial.print(F(" t_ms=")); Serial.println(millis());
}

// ---------------- Motion -----------------------------------
void applyMode(char m){
  mode = m;
  if (m=='S'){ allREL(); pwmSpeed(0); servo_stopSweep(); return; }
  if (m=='F'){ for(int i=0;i<4;i++) setDirBits(i, FWD); }
  else if (m=='B'){ for(int i=0;i<4;i++) setDirBits(i, REVv); }
  else if (m=='L'){ setDirBits(0,REVv); setDirBits(1,REVv); setDirBits(2,FWD); setDirBits(3,FWD); }
  else if (m=='R'){ setDirBits(0,FWD); setDirBits(1,FWD); setDirBits(2,REVv); setDirBits(3,REVv); }
  if (speedVal==0) pwmSpeed(160); // default if not set
  servo_startSweep();
}

// ---------------- Parser -----------------------------------
void parseAndRun(String line){
  line.trim(); if(!line.length()) return; char c=line[0];
  if (c=='H'){ Serial.println(F("CMD: F/B/L/R<n>, S, P<deg>, T<n>, Q, H")); return; }
  if (c=='Q'){ printStat(); lastCM=readUltrasonicCM(); printULS(); return; }
  if (c=='S'){ applyMode('S'); Serial.println(F("EVT stop=command")); printStat(); lastCM=readUltrasonicCM(); printULS(); return; }
  if (c=='P'){
    int v = line.substring(1).toInt(); v = constrain(v,0,180);
    if (!servoAttached) { scanServo.attach(SERVO_PIN); servoAttached=true; }
    sweepEnabled=false; servoAngle=v; scanServo.write(v);
    printStat(); lastCM=readUltrasonicCM(); printULS(); return; }
  if (c=='T'){
    int v = line.substring(1).toInt(); if (v<0) v=0; if (v>400) v=400; stopThresholdCm=v;
    printStat(); lastCM=readUltrasonicCM(); printULS(); return; }
  if (c=='F'||c=='B'||c=='L'||c=='R'){
    int v = line.substring(1).toInt(); v = constrain(v,0,255); pwmSpeed(v); applyMode(c); printStat(); lastCM=readUltrasonicCM(); printULS(); return; }
  Serial.println(F("ERR unknown"));
}

// ---------------- Setup / Loop ------------------------------
void setup(){
  Serial.begin(115200);
  pinMode(SR_DATA,OUTPUT); pinMode(SR_LATCH,OUTPUT); pinMode(SR_CLK,OUTPUT); pinMode(SR_OE,OUTPUT);
  digitalWrite(SR_OE, LOW); // enable 595 outputs (PWM will modulate)
  latch_state=0; latchWrite(); allREL(); pwmSpeed(0);

  pinMode(US_TRIG,OUTPUT); digitalWrite(US_TRIG,LOW); pinMode(US_ECHO,INPUT);
  servo_stopSweep();
  analogWrite(SR_OE, 255); // outputs disabled at boot

  delay(30);
  Serial.println(F("STATUS READY"));
}

void loop(){
  String line; if (readLine(line)) parseAndRun(line);

  // periodic tasks: servo sweep, ultrasonic, safety debounce
  static unsigned long nextSample=0; if (sweepEnabled) servo_tick();
  unsigned long now = millis();
  if (now >= nextSample){
    lastCM = readUltrasonicCM();
    static uint8_t hits=0;
    if (stopThresholdCm>0){
      if (lastCM>=0 && lastCM<=stopThresholdCm) { if (hits<255) hits++; }
      else { hits=0; }
      if (hits>=3 && mode!='S'){
        applyMode('S');
        Serial.println(F("EVT stop=safety"));
        printStat(); printULS();
      }
    } else { hits=0; }
    nextSample = now + 80; // ~12.5 Hz
  }
}

