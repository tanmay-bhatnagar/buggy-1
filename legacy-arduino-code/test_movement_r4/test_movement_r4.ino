/*********************************************************************
 * UNO R4 + L293D v1 shield (74HC595)
 * Brake vs Coast demo with rich logs + shared-EN handling + KILL latch
 *
 * Sequence (2s each):
 *   Forward -> COAST stop -> Forward -> BRAKE stop ->
 *   Right spin -> COAST stop -> Left spin -> BRAKE stop -> Auto-KILL
 *********************************************************************/

#include <Arduino.h>

// 74HC595 control lines (Adafruit v1 convention)
const uint8_t SR_DATA  = 8;   // SER
const uint8_t SR_LATCH = 12;  // RCLK / LATCH
const uint8_t SR_CLK   = 4;   // SRCLK / CLOCK
const uint8_t SR_OE    = 7;   // OE (active LOW); many shields tie this LOW; we drive LOW too.

// #define EN_PIN 10000
// // Per-motor EN pins (your board)
// uint8_t M_EN[4] = {
//   EN_PIN, // M1 (Front-Left)
//   EN_PIN,  // M2 (Rear-Left)  — shares with right side on your clone
//   EN_PIN,  // M3 (Rear-Right)
//   EN_PIN   // M4 (Front-Right)
// };

// Final polarity (true = reverse that motor’s notion of FWD/REV)
const bool REV[4] = { false, true, false, true }; // M1..M4

// 74HC595 bit mapping (Adafruit v1)
#define M1_A_BIT 2
#define M1_B_BIT 3
#define M2_A_BIT 1
#define M2_B_BIT 4
#define M3_A_BIT 5
#define M3_B_BIT 7
#define M4_A_BIT 0
#define M4_B_BIT 6

struct Mbits { uint8_t A,B; } MB[4] = {
  {M1_A_BIT,M1_B_BIT},{M2_A_BIT,M2_B_BIT},{M3_A_BIT,M3_B_BIT},{M4_A_BIT,M4_B_BIT}
};

enum Dir: uint8_t { REL=0, FWD=1, REVV=2, BRK=3 };

const uint16_t T_MOVE  = 1000;  // 2s run segments (as requested)
const uint16_t T_PAUSE = 2000;  // 2s between runs after stop
const uint16_t BRAKE_MS = 300;  // brake pulse length (≈0.3s is plenty)
bool running=true, killed=false;
uint8_t latch_state=0x00;

// ---------- Serial clear ----------
void serialClear(){
  Serial.write(27); Serial.print("[2J"); // ANSI clear
  Serial.write(27); Serial.print("[H");  // cursor home
  for (int i=0;i<20;++i) Serial.println(); // fallback padding
  Serial.println(F("────────────────────────────────────────────────────────"));
}

// ---------- Logs / helpers ----------
const __FlashStringHelper* dirName(Dir d){
  switch(d){ case REL: return F("REL"); case FWD: return F("FWD"); case REVV: return F("REV"); default: return F("BRK"); }
}
Dir effectiveDir(uint8_t m, Dir intended){
  if (intended==REL || intended==BRK) return intended;   // BRK not affected by REV
  return REV[m] ? (intended==FWD ? REVV : FWD) : intended;
}
void printLatchBits(const char* tag){
  Serial.print(F("[LATCH] ")); Serial.print(tag); Serial.print(F(" Q7..Q0="));
  for (int i=7;i>=0;--i) Serial.print((latch_state>>i)&1);
  Serial.println();
}
void printMap(){
  Serial.print(F("[MAP] EN pins  M1->")); Serial.print(M_EN[0]);
  Serial.print(F("  M2->"));               Serial.print(M_EN[1]);
  Serial.print(F("  M3->"));               Serial.print(M_EN[2]);
  Serial.print(F("  M4->"));               Serial.println(M_EN[3]);
  Serial.print(F("[MAP] REV flags M1=")); Serial.print(REV[0]);
  Serial.print(F(" M2="));                 Serial.print(REV[1]);
  Serial.print(F(" M3="));                 Serial.print(REV[2]);
  Serial.print(F(" M4="));                 Serial.println(REV[3]);
}

// ---------- 74HC595 ----------
void latchWrite(){
  digitalWrite(SR_LATCH,LOW);
  for(int i=7;i>=0;--i){ digitalWrite(SR_CLK,LOW); digitalWrite(SR_DATA,(latch_state>>i)&1); digitalWrite(SR_CLK,HIGH); }
  digitalWrite(SR_LATCH,HIGH);
}
void setBit(uint8_t bit, bool v){
  if(v) latch_state |= (1<<bit); else latch_state &= ~(1<<bit);
  latchWrite();
}
void setDirBits(uint8_t m, Dir intended){
  Dir d = effectiveDir(m,intended);
  if (d==REL) { setBit(MB[m].A,0); setBit(MB[m].B,0); }
  else if (d==FWD){ setBit(MB[m].A,1); setBit(MB[m].B,0); }
  else if (d==REVV){ setBit(MB[m].A,0); setBit(MB[m].B,1); }
  else { /* BRK */ setBit(MB[m].A,1); setBit(MB[m].B,1); }
}

// ---------- EN handling (shared-EN aware) ----------
void enSetAllLow(){ for(int i=0;i<4;++i){ pinMode(M_EN[i],OUTPUT); digitalWrite(M_EN[i],LOW);} }

// Drive each physical EN pin HIGH if any motor mapped to it requests ON
void applyEN(const bool want[4]){
  uint8_t pins[4]; uint8_t n=0;
  for(int m=0;m<4;++m){ bool seen=false; for(uint8_t i=0;i<n;++i) if(pins[i]==M_EN[m]){ seen=true; break; }
                        if(!seen) pins[n++]=M_EN[m]; }
  for(uint8_t i=0;i<n;++i){
    uint8_t p = pins[i]; bool on=false;
    for(int m=0;m<4;++m) if(M_EN[m]==p && want[m]) { on=true; break; }
    pinMode(p,OUTPUT); digitalWrite(p, on?HIGH:LOW);
  }
}

// ---------- Stops ----------
void coastStopAll(){
  // True coast: EN LOW, inputs ignored. (We also set REL to be explicit.)
  bool enWant[4]={0,0,0,0};
  Dir d[4]={REL,REL,REL,REL};
  for(int m=0;m<4;++m) setDirBits(m,d[m]);
  applyEN(enWant);
  Serial.println(F("[STOP] COAST  -> EN=LOW; outputs Hi-Z, robot freewheels"));
  printLatchBits("after COAST");
}

void brakeStopAll(){
  // Active brake: EN HIGH for a short pulse, inputs A=B=1, then EN LOW
  bool enWant[4]={1,1,1,1};
  Dir d[4]={BRK,BRK,BRK,BRK};
  for(int m=0;m<4;++m) setDirBits(m,d[m]);
  applyEN(enWant);
  Serial.print(F("[STOP] BRAKE  -> EN=HIGH, A=B=1 for ")); Serial.print(BRAKE_MS); Serial.println(F(" ms"));
  delay(BRAKE_MS);
  // Drop EN LOW and (optionally) leave inputs at REL to idle cool
  enSetAllLow();
  for(int m=0;m<4;++m) setDirBits(m,REL);
  printLatchBits("after BRAKE");
}

// ---------- Commands & waits ----------
void killAll(){
  enSetAllLow();
  for(int m=0;m<4;++m) setDirBits(m,REL);
  latch_state=0x00; latchWrite();
  Serial.println(F("[STATE] KILLED. Reset/power-cycle to recover."));
  digitalWrite(LED_BUILTIN,LOW);
  killed=true; while(true){ delay(1000); }
}
void handleSerial(){
  if(!Serial.available()) return;
  String s=Serial.readStringUntil('\n'); s.trim(); s.toUpperCase();
  if(s==F("STOP")){ running=false; coastStopAll(); Serial.println(F("[STATE] STOPPED.")); }
  else if(s==F("GO")){ running=true; Serial.println(F("[STATE] RUNNING.")); }
  else if(s==F("KILL")){ killAll(); }
  else if(s==F("HELP")){ Serial.println(F("Commands: STOP | GO | KILL | CLS")); }
  else if(s==F("CLS")){ serialClear(); }
}
void waitMs(uint32_t ms, const __FlashStringHelper* tag){
  const uint16_t step=20; unsigned long dot=millis()+500;
  Serial.print(F("[WAIT] ")); Serial.print(tag); Serial.print(F(" ~")); Serial.print(ms); Serial.println(F(" ms"));
  while(ms && !killed){
    handleSerial();
    if(!running) { coastStopAll(); }
    delay(step);
    if(millis()>=dot){ Serial.print('.'); dot+=500; }
    ms = (ms>step)?(ms-step):0;
  }
  Serial.println();
}

// ---------- Moves (2s) ----------
void runForward(){
  serialClear();
  Serial.println(F("[MOVE] Forward 2s (after REV)"));
  bool enWant[4]={1,1,1,1};
  for(int m=0;m<4;++m) setDirBits(m,FWD);
  applyEN(enWant);
  waitMs(T_MOVE, F("Forward"));
}
void runRightSpin(){ // left forward, right reverse
  serialClear();
  Serial.println(F("[MOVE] Right spin 2s (left FWD, right REV)"));
  bool enWant[4]={1,1,1,1};
  setDirBits(0,FWD); setDirBits(1,FWD);
  setDirBits(2,REVV); setDirBits(3,REVV);
  applyEN(enWant);
  waitMs(T_MOVE, F("Right spin"));
}
void runLeftSpin(){ // left reverse, right forward
  serialClear();
  Serial.println(F("[MOVE] Left spin 2s (left REV, right FWD)"));
  bool enWant[4]={1,1,1,1};
  setDirBits(0,REVV); setDirBits(1,REVV);
  setDirBits(2,FWD);  setDirBits(3,FWD);
  applyEN(enWant);
  waitMs(T_MOVE, F("Left spin"));
}

// ---------- Arduino ----------
void setup(){
  Serial.begin(115200); while(!Serial){}
  pinMode(LED_BUILTIN,OUTPUT); digitalWrite(LED_BUILTIN,HIGH);

  serialClear();
  pinMode(SR_DATA,OUTPUT); pinMode(SR_LATCH,OUTPUT); pinMode(SR_CLK,OUTPUT);
  pinMode(SR_OE,OUTPUT); digitalWrite(SR_OE,LOW); // enable outputs (if present)
  latch_state=0x00; latchWrite(); printLatchBits("init");
  enSetAllLow();
  printMap();
  Serial.println(F("\n[Brake vs Coast demo] STOP | GO | KILL | HELP | CLS"));
}

void loop(){
  if(killed) return;

  // Forward -> COAST stop
  runForward();         coastStopAll(); waitMs(T_PAUSE, F("Pause"));

  // Forward -> BRAKE stop
  runForward();         brakeStopAll(); waitMs(T_PAUSE, F("Pause"));

  // Right spin -> COAST stop
  runRightSpin();       coastStopAll(); waitMs(T_PAUSE, F("Pause"));

  // Left spin -> BRAKE stop
  runLeftSpin();        brakeStopAll();

  Serial.println(F("[STATE] Demo complete. Auto-KILL."));
  killAll();
}
