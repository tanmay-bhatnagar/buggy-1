/*
  Servo + Ultrasonic — Minimal Test (v1.2-min2) | UNO R4 WiFi

  WHAT THIS DOES
  • Controls ONE servo on D10 (pan) and ONE ultrasonic sensor (HC‑SR04).
  • Provides a tiny serial command language that works with arduino‑cli monitor.
  • No motor/shield code at all.

  SERIAL MONITOR BASICS
  • Baud: 115200. Press RESET to see the banner and prompt.
  • End your command with Enter. CR or LF both work.
  • Prompt: "> "

  COMMANDS (case‑insensitive)
  • HELP
      Prints this cheat‑sheet.

  • STATUS
      Prints: whether the servo is attached, current angle, ultrasonic pin mapping,
      whether STREAM is on, and the current stream PERIOD in milliseconds.

  • ATTACH / DETACH / CENTER
      ATTACH starts servo pulses; DETACH stops them (no holding torque).
      CENTER moves to 90° and reports STATUS.

  • SET <0..180>
      Absolute servo angle. Example:  SET 135

  • NUDGE <delta>
      Relative move. Example:  NUDGE -10

  • PINS <TRIG> <ECHO>
      Change ultrasonic pins at runtime. Accepts A0..A5 or D2..D19. Examples:
        PINS A0 A1
        PINS D2 D3

  • PING
      Take ONE ultrasonic reading and print one line:  ping_cm=<value|timeout>

  • STREAM ON | STREAM OFF
      When ON, the firmware performs a PING every PERIOD ms and prints the result.
      Use this for a live distance feed without moving the servo.

  • PERIOD <ms>
      Set the interval (in milliseconds) for STREAM ON. Example:  PERIOD 100

  • ULTRASONIC ON <secs> [SPIN ON|OFF]
      Run a timed ranging loop. Prints one line per reading:
        DATA ULS cm=<value|timeout> angle=<deg> t_ms=<elapsed>
      If you add SPIN ON, the servo will sweep from 30°..150° during the run.
      Example:  ULTRASONIC ON 5 SPIN ON

  • SCAN <start> <stop> <step>
      Do a single pass, stepping the servo and taking a PING at each angle.
      Example:  SCAN 0 180 10

  • KILL
      Immediately turns STREAM OFF and DETACHes the servo.

  BOOT BANNER:  STATUS READY
*/

#include <Arduino.h>
#include <Servo.h>

// --- Pins ---
constexpr uint8_t SERVO_PIN = 10; // D10
uint8_t US_TRIG = A0;             // default
uint8_t US_ECHO = A1;             // default

// --- Serial ---
constexpr unsigned long BAUD = 115200;

// --- Servo state ---
Servo servo;
bool servoAttached = false;
int  angleDeg = 90;
int  sweepMin = 30, sweepMax = 150, sweepStep = 10;

// --- Streaming state ---
bool streamOn = false;
unsigned long streamPeriodMs = 200;
unsigned long lastStreamMs = 0;

// --- Helpers ---
static void prompt(){ Serial.print(F("> ")); }

void attachIfNeeded(){ if(!servoAttached){ servo.attach(SERVO_PIN); servoAttached=true; }}
void detachIfNeeded(){ if(servoAttached){ servo.detach(); servoAttached=false; }}
void goToAngle(int a){ attachIfNeeded(); a=constrain(a,0,180); angleDeg=a; servo.write(a); }

// Parse pin token like "A0", "D2", or raw number
bool parsePin(const String& tok, uint8_t& out){ String t=tok; t.trim(); t.toUpperCase();
  if(t==F("A0")){out=A0;return true;} if(t==F("A1")){out=A1;return true;} if(t==F("A2")){out=A2;return true;}
  if(t==F("A3")){out=A3;return true;} if(t==F("A4")){out=A4;return true;} if(t==F("A5")){out=A5;return true;}
  if(t.startsWith(F("D"))){ int n=t.substring(1).toInt(); if(n>=0&&n<=19){ out=(uint8_t)n; return true; } }
  if(t[0]>='0'&&t[0]<='9'){ int n=t.toInt(); if(n>=0&&n<=19){ out=(uint8_t)n; return true; }}
  return false;
}

// Ultrasonic helpers
unsigned long pingRawUs(){
  pinMode(US_TRIG, OUTPUT); digitalWrite(US_TRIG, LOW); delayMicroseconds(2);
  digitalWrite(US_TRIG, HIGH); delayMicroseconds(10); digitalWrite(US_TRIG, LOW);
  pinMode(US_ECHO, INPUT);
  return pulseIn(US_ECHO, HIGH, 30000UL); // 0 on timeout
}
float usToCm(unsigned long us){ if(us==0) return NAN; return us/58.0f; }
float pingCmMedian3(){ unsigned long a=pingRawUs(); delay(10); unsigned long b=pingRawUs(); delay(10); unsigned long c=pingRawUs();
  unsigned long lo=min(a,min(b,c)); unsigned long hi=max(a,max(b,c)); unsigned long med=a+b+c-lo-hi; return usToCm(med);
}

// CR/LF tolerant reader
bool readLine(String &out){ static String buf; while(Serial.available()){ char c=(char)Serial.read(); if(c=='\r'||c=='\n'){ if(buf.length()){ out=buf; buf=""; return true; } } else { buf+=c; if(buf.length()>120) buf=""; } } return false; }

// --- Commands ---
void doStatus(){ Serial.print(F("servo=")); Serial.print(servoAttached?F("attached"):F("detached")); Serial.print(F(" angle=")); Serial.print(angleDeg);
  Serial.print(F(" trig=")); Serial.print((int)US_TRIG); Serial.print(F(" echo=")); Serial.print((int)US_ECHO);
  Serial.print(F(" stream=")); Serial.print(streamOn?F("ON"):F("OFF")); Serial.print(F(" periodMs=")); Serial.println(streamPeriodMs); }

void doPing(){ float cm=pingCmMedian3(); if(isnan(cm)) Serial.println(F("ping_cm=timeout")); else { Serial.print(F("ping_cm=")); Serial.println(cm,1);} }

void doUltrasonicTimed(float secs, bool spin){
  Serial.println(F("EVENT START ULS"));
  unsigned long t0=millis(), duration=(unsigned long)(max(0.0f,secs)*1000.0f);
  int a=angleDeg; if(spin && !servoAttached) attachIfNeeded();
  while(millis()-t0<duration){
    float cm=pingCmMedian3(); unsigned long t=millis()-t0;
    Serial.print(F("DATA ULS cm=")); if(isnan(cm)) Serial.print(F("timeout")); else Serial.print(cm,1);
    Serial.print(F(" angle=")); Serial.print(a); Serial.print(F(" t_ms=")); Serial.println(t);
    if(spin){ a+=sweepStep; if(a> sweepMax) a=sweepMin; goToAngle(a);} // step after reading
    delay(80);
  }
  Serial.println(F("EVENT COMPLETE ULS"));
}

void doScan(int start,int stop,int step){ start=constrain(start,0,180); stop=constrain(stop,0,180); if(step==0) step=10; attachIfNeeded();
  if((start<stop && step<0) || (start>stop && step>0)) step=-step; for(int a=start; (step>0)?(a<=stop):(a>=stop); a+=step){ goToAngle(a); delay(120); doPing(); }
}

void printHelp(){ Serial.println(F("HELP — Commands:")); Serial.println(F("STATUS | HELP | KILL")); Serial.println(F("ATTACH | DETACH | CENTER | SET <0..180> | NUDGE <delta>")); Serial.println(F("PINS <TRIG> <ECHO> (A0..A5, D2..D19)")); Serial.println(F("PING | STREAM ON|OFF | PERIOD <ms>")); Serial.println(F("ULTRASONIC ON <secs> [SPIN ON|OFF]")); Serial.println(F("SCAN <start> <stop> <step>")); }

void handleCommand(const String& line){ String s=line; s.trim(); if(!s.length()) return; String up=s; up.toUpperCase();
  if(up==F("HELP")) { printHelp(); }
  else if(up==F("STATUS")) { doStatus(); }
  else if(up==F("KILL")) { streamOn=false; detachIfNeeded(); Serial.println(F("KILLED (stream OFF, servo detached)")); }
  else if(up==F("ATTACH")) { attachIfNeeded(); doStatus(); }
  else if(up==F("DETACH")||up==F("OFF")) { detachIfNeeded(); doStatus(); }
  else if(up==F("CENTER")) { goToAngle(90); doStatus(); }
  else if(up.startsWith(F("SET"))) { long v=s.substring(3).toInt(); goToAngle((int)v); doStatus(); }
  else if(up.startsWith(F("NUDGE"))) { long d=s.substring(5).toInt(); goToAngle(angleDeg+(int)d); doStatus(); }
  else if(up.startsWith(F("PINS"))) { int sp1=s.indexOf(' '); if(sp1>0){ String rest=s.substring(sp1+1); rest.trim(); int sp2=rest.indexOf(' ');
      if(sp2>0){ String t1=rest.substring(0,sp2), t2=rest.substring(sp2+1); uint8_t nt,ne; if(parsePin(t1,nt)&&parsePin(t2,ne)){ US_TRIG=nt; US_ECHO=ne; pinMode(US_TRIG,OUTPUT); digitalWrite(US_TRIG,LOW); pinMode(US_ECHO,INPUT); doStatus(); } else { Serial.println(F("PINS parse error")); } } } }
  else if(up==F("PING")) { doPing(); }
  else if(up.startsWith(F("STREAM"))) { if(up.indexOf(F(" ON"))>0){ streamOn=true; lastStreamMs=0; Serial.println(F("stream=ON")); } else if(up.indexOf(F(" OFF"))>0){ streamOn=false; Serial.println(F("stream=OFF")); } else { Serial.print(F("stream=")); Serial.println(streamOn?F("ON"):F("OFF")); } }
  else if(up.startsWith(F("PERIOD"))) { long ms=s.substring(6).toInt(); streamPeriodMs=(unsigned long)max(10L,ms); Serial.print(F("periodMs=")); Serial.println(streamPeriodMs); }
  else if(up.startsWith(F("ULTRASONIC"))) {
    // Robust parse: look for token " ON " (avoid matching the "ON" inside "ULTRASONIC")
    bool spin = (up.indexOf(F(" SPIN ON")) > 0);
    float secs = 3.0;
    // token after ULTRASONIC should be ON, then seconds
    int firstSpace = up.indexOf(' ');
    String rest = s.substring(firstSpace + 1); rest.trim();
    String restUp = rest; restUp.toUpperCase();
    if (restUp.startsWith("ON")) {
      String afterOn = rest.substring(2); afterOn.trim();
      int sp = afterOn.indexOf(' ');
      String secTok = (sp >= 0) ? afterOn.substring(0, sp) : afterOn;
      secs = secTok.toFloat(); if (secs < 0) secs = 0;
    }
    doUltrasonicTimed(secs, spin);
  }
  else if(up.startsWith(F("SCAN"))) { int sp1=s.indexOf(' '); if(sp1>0){ String rest=s.substring(sp1+1); rest.trim(); int sp2=rest.indexOf(' '); int sp3=(sp2>0)?rest.indexOf(' ',sp2+1):-1; if(sp2>0 && sp3>0){ int st=rest.substring(0,sp2).toInt(); int en=rest.substring(sp2+1,sp3).toInt(); int stp=rest.substring(sp3+1).toInt(); doScan(st,en,stp); } else { Serial.println(F("SCAN needs: SCAN <start> <stop> <step>")); } } }
  else { Serial.print(F("Unknown: ")); Serial.println(s); printHelp(); }
  prompt();
}

void setup(){
  Serial.begin(BAUD);
  unsigned long t0=millis(); while(!Serial && millis()-t0<4000){}
  pinMode(US_TRIG, OUTPUT); digitalWrite(US_TRIG, LOW);
  pinMode(US_ECHO, INPUT);
  delay(20);
  Serial.println(F("STATUS READY"));
  prompt();
}

void loop(){
  String line; if(readLine(line)) handleCommand(line);
  if(streamOn){ unsigned long now=millis(); if(now-lastStreamMs>=streamPeriodMs){ lastStreamMs=now; doPing(); }}
}

