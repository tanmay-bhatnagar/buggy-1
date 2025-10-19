/*
  MovementTest.ino — Movement test for UNO R4 WiFi + L293D v1 clone + 74HC595

  Serial 115200. Commands: FWD BACK LEFT RIGHT SPINL SPINR STOP KILL
  SPEED <0..255> | TIME <ms> | ENALT ON|OFF | TEST

  Map (locked for 1.1):
    SR_DATA=D8, SR_LATCH=D12, SR_CLK=D4, SR_OE=D7 (active-LOW)
    EN: M1=D11, M2=D3, M3=D3|D11, M4=D3|D11 (toggle via ENALT)
    Wheels: M1=Front-Left, M2=Rear-Left, M3=Rear-Right, M4=Front-Right
    Servo: D10 (unused here) | Ultrasonic: TRIG=A0, ECHO=A1 (unused here)
*/

#include <Arduino.h>

// ---------------------------- Shift Register (74HC595) ----------------------------
constexpr uint8_t SR_DATA  = 8;   // SER
constexpr uint8_t SR_LATCH = 12;  // RCLK
constexpr uint8_t SR_CLK   = 4;   // SRCLK
constexpr uint8_t SR_OE    = 7;   // OE (active LOW)
volatile uint8_t latch_state = 0x00;  // bit0..bit7 map to IN1..IN8

enum : uint8_t { IN1_BIT=0, IN2_BIT, IN3_BIT, IN4_BIT, IN5_BIT, IN6_BIT, IN7_BIT, IN8_BIT };
struct Channel { uint8_t inA_bit; uint8_t inB_bit; };
constexpr Channel CH_M1 = { IN1_BIT, IN2_BIT };
constexpr Channel CH_M2 = { IN3_BIT, IN4_BIT };
constexpr Channel CH_M3 = { IN5_BIT, IN6_BIT };
constexpr Channel CH_M4 = { IN7_BIT, IN8_BIT };

// ---------------------------- EN (PWM) pins ----------------------------
constexpr uint8_t M1_EN = 11;  // Left front
constexpr uint8_t M2_EN = 3;   // Left rear
bool useAltEnForRight = false; // false => right on D3, true => on D11
constexpr uint8_t RIGHT_EN_DEFAULT = 3;
constexpr uint8_t RIGHT_EN_ALT     = 11;
inline uint8_t M3_EN() { return useAltEnForRight ? RIGHT_EN_ALT : RIGHT_EN_DEFAULT; }
inline uint8_t M4_EN() { return useAltEnForRight ? RIGHT_EN_ALT : RIGHT_EN_DEFAULT; }

// ---------------------------- Behavior tuning ----------------------------
uint8_t  PWM_VALUE    = 255;     // full send for test
uint32_t MOVE_TIME_MS = 1200;    // default move duration
bool REV[4] = { true, false, true, false }; // {M1,M2,M3,M4} polarity for FORWARD

// ---------------------------- Direction codes (prototype-safe) ----------------------------
#define DIR_BRAKE 0
#define DIR_FWD   1
#define DIR_REV   2

// ---------------------------- SR helpers ----------------------------
void srApply(){
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLK, MSBFIRST, latch_state);
  digitalWrite(SR_LATCH, HIGH);
}
void srSetBit(uint8_t b, bool h){
  if(h) latch_state |= (1u<<b); else latch_state &= ~(1u<<b);
  srApply();
}
void srZeroAll(){ latch_state = 0x00; srApply(); }

// ---------------------------- Motor helpers ----------------------------
void motorSet(const Channel& ch, uint8_t d){
  switch(d){
    case DIR_BRAKE: srSetBit(ch.inA_bit, LOW);  srSetBit(ch.inB_bit, LOW);  break;
    case DIR_FWD:   srSetBit(ch.inA_bit, HIGH); srSetBit(ch.inB_bit, LOW);  break;
    case DIR_REV:   srSetBit(ch.inA_bit, LOW);  srSetBit(ch.inB_bit, HIGH); break;
  }
}
void allBrake(){
  motorSet(CH_M1, DIR_BRAKE); motorSet(CH_M2, DIR_BRAKE); motorSet(CH_M3, DIR_BRAKE); motorSet(CH_M4, DIR_BRAKE);
  analogWrite(M1_EN,0); analogWrite(M2_EN,0); analogWrite(M3_EN(),0); analogWrite(M4_EN(),0);
}
void applyPWMAll(uint8_t p){ analogWrite(M1_EN,p); analogWrite(M2_EN,p); analogWrite(M3_EN(),p); analogWrite(M4_EN(),p); }

// High-level moves (respecting REV flags)
void moveForward(){
  motorSet(CH_M1, REV[0]?DIR_REV:DIR_FWD); motorSet(CH_M2, REV[1]?DIR_REV:DIR_FWD);
  motorSet(CH_M3, REV[2]?DIR_REV:DIR_FWD); motorSet(CH_M4, REV[3]?DIR_REV:DIR_FWD);
  applyPWMAll(PWM_VALUE);
}
void moveBackward(){
  motorSet(CH_M1, REV[0]?DIR_FWD:DIR_REV); motorSet(CH_M2, REV[1]?DIR_FWD:DIR_REV);
  motorSet(CH_M3, REV[2]?DIR_FWD:DIR_REV); motorSet(CH_M4, REV[3]?DIR_FWD:DIR_REV);
  applyPWMAll(PWM_VALUE);
}
void turnLeft(){
  motorSet(CH_M1, DIR_BRAKE); motorSet(CH_M2, DIR_BRAKE);
  motorSet(CH_M3, REV[2]?DIR_REV:DIR_FWD); motorSet(CH_M4, REV[3]?DIR_REV:DIR_FWD);
  applyPWMAll(PWM_VALUE);
}
void turnRight(){
  motorSet(CH_M1, REV[0]?DIR_REV:DIR_FWD); motorSet(CH_M2, REV[1]?DIR_REV:DIR_FWD);
  motorSet(CH_M3, DIR_BRAKE); motorSet(CH_M4, DIR_BRAKE);
  applyPWMAll(PWM_VALUE);
}
void spinLeft(){
  motorSet(CH_M1, REV[0]?DIR_FWD:DIR_REV); motorSet(CH_M2, REV[1]?DIR_FWD:DIR_REV);
  motorSet(CH_M3, REV[2]?DIR_REV:DIR_FWD); motorSet(CH_M4, REV[3]?DIR_REV:DIR_FWD);
  applyPWMAll(PWM_VALUE);
}
void spinRight(){
  motorSet(CH_M1, REV[0]?DIR_REV:DIR_FWD); motorSet(CH_M2, REV[1]?DIR_REV:DIR_FWD);
  motorSet(CH_M3, REV[2]?DIR_FWD:DIR_REV); motorSet(CH_M4, REV[3]?DIR_FWD:DIR_REV);
  applyPWMAll(PWM_VALUE);
}

// ---------------------------- Command handling ----------------------------
String rx;
void printHelp(){
  Serial.println(F("Commands: FWD BACK LEFT RIGHT SPINL SPINR STOP KILL"));
  Serial.println(F("SPEED <0..255> | TIME <ms> | ENALT ON|OFF | TEST"));
  Serial.println(F("ENALT toggles right-side EN between D3 (OFF) and D11 (ON)."));
}
void doTestScript(){
  const uint16_t pause=300;
  Serial.println(F("[TEST] FORWARD"));  moveForward();  delay(MOVE_TIME_MS); allBrake(); delay(pause);
  Serial.println(F("[TEST] BACK"));     moveBackward(); delay(MOVE_TIME_MS); allBrake(); delay(pause);
  Serial.println(F("[TEST] LEFT"));     turnLeft();     delay(MOVE_TIME_MS); allBrake(); delay(pause);
  Serial.println(F("[TEST] RIGHT"));    turnRight();    delay(MOVE_TIME_MS); allBrake(); delay(pause);
  Serial.println(F("[TEST] SPINL"));    spinLeft();     delay(MOVE_TIME_MS); allBrake(); delay(pause);
  Serial.println(F("[TEST] SPINR"));    spinRight();    delay(MOVE_TIME_MS); allBrake(); delay(pause);
  Serial.println(F("[TEST] STOP"));     allBrake();
}
void handleCommand(const String& line){
  String s=line; s.trim(); s.toUpperCase(); if(!s.length()) return;
  if      (s=="FWD")   { Serial.println(F("→ FORWARD"));   moveForward();  delay(MOVE_TIME_MS); allBrake(); }
  else if (s=="BACK")  { Serial.println(F("→ BACK"));      moveBackward(); delay(MOVE_TIME_MS); allBrake(); }
  else if (s=="LEFT")  { Serial.println(F("→ LEFT"));      turnLeft();     delay(MOVE_TIME_MS); allBrake(); }
  else if (s=="RIGHT") { Serial.println(F("→ RIGHT"));     turnRight();    delay(MOVE_TIME_MS); allBrake(); }
  else if (s=="SPINL") { Serial.println(F("→ SPIN LEFT")); spinLeft();     delay(MOVE_TIME_MS); allBrake(); }
  else if (s=="SPINR") { Serial.println(F("→ SPIN RIGHT"));spinRight();    delay(MOVE_TIME_MS); allBrake(); }
  else if (s=="STOP")  { Serial.println(F("■ STOP"));      allBrake(); }
  else if (s=="KILL")  { Serial.println(F("!! KILL"));     allBrake(); srZeroAll(); }
  else if (s.startsWith("SPEED")) { int v=s.substring(5).toInt(); v=constrain(v,0,255); PWM_VALUE=v; Serial.print(F("PWM_VALUE = ")); Serial.println(PWM_VALUE); }
  else if (s.startsWith("TIME"))  { int ms=s.substring(4).toInt(); ms=max(0,ms); MOVE_TIME_MS=(uint32_t)ms; Serial.print(F("MOVE_TIME_MS = ")); Serial.println((int)MOVE_TIME_MS); }
  else if (s=="TEST")  { doTestScript(); }
  else if (s.startsWith("ENALT")) {
    if (s.indexOf("ON")>0) { useAltEnForRight=true;  Serial.println(F("ENALT=ON (right EN uses D11)")); }
    else if (s.indexOf("OFF")>0){ useAltEnForRight=false; Serial.println(F("ENALT=OFF (right EN uses D3)")); }
    else { Serial.print(F("ENALT is ")); Serial.println(useAltEnForRight?F("ON (D11)"):F("OFF (D3)")); }
    analogWrite(RIGHT_EN_DEFAULT, useAltEnForRight?0:PWM_VALUE);
    analogWrite(RIGHT_EN_ALT,     useAltEnForRight?PWM_VALUE:0);
  }
  else { Serial.print(F("Unknown: ")); Serial.println(s); printHelp(); }
}

// ---------------------------- Setup / Loop ----------------------------
void setup(){
  Serial.begin(115200); delay(50);
  pinMode(SR_DATA,OUTPUT); pinMode(SR_LATCH,OUTPUT); pinMode(SR_CLK,OUTPUT); pinMode(SR_OE,OUTPUT);
  digitalWrite(SR_OE,LOW); latch_state=0x00; srApply();
  pinMode(M1_EN,OUTPUT); pinMode(M2_EN,OUTPUT); pinMode(RIGHT_EN_DEFAULT,OUTPUT); pinMode(RIGHT_EN_ALT,OUTPUT);
  allBrake();
  Serial.println(F("[MovementTest 1.1] UNO R4 + L293D v1 clone + 74HC595"));
  Serial.println(F("Pins: SR(DATA=8,LATCH=12,CLK=4,OE=7), EN(L: D11,D3 | R: D3 or D11)"));
  Serial.println(F("Wheels: M1=FL, M2=RL, M3=RR, M4=FR"));
  Serial.println(F("Type HELP for commands. KILL is case-insensitive."));
  Serial.println(F("Tip: If right motors don’t move, send: ENALT ON"));
}
void loop(){
  while(Serial.available()){
    char c=Serial.read(); if(c=='\r') continue; if(c=='\n'){ handleCommand(rx); rx=""; }
    else{ rx+=c; String up=rx; up.toUpperCase(); if(up.endsWith("KILL")){ handleCommand("KILL"); rx=""; }}
  }
}

