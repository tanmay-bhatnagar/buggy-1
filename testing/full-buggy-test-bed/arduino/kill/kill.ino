// KillAll.ino — hard KILL sketch (upload to immediately stop everything)
// Board: Arduino UNO R4 WiFi
// Serial: 115200 (prints one line for confirmation)
// Behavior on boot:
//   - Disable L293D outputs (OE HIGH) and latch 0x00 to the 74HC595
//   - Detach servo and drive its pin LOW (quiet)
//   - Stop ultrasonic (TRIG held LOW, ECHO high-impedance)
//   - Blink onboard LED slowly so you can tell it's in KILL mode
//
// Legacy pin map (from your working testbench):
//   74HC595/L293D: DATA=8, LATCH=12, CLK=4, OE=7 (active LOW)
//   Ultrasonic:    TRIG=A0, ECHO=A1
//   Servo:         D10

#include <Arduino.h>
#include <Servo.h>

// ---- Shift register / L293D ----
const uint8_t SR_DATA  = 8;
const uint8_t SR_LATCH = 12;
const uint8_t SR_CLK   = 4;
const uint8_t SR_OE    = 7;   // active LOW

// ---- Ultrasonic ----
const uint8_t US_TRIG = A0;
const uint8_t US_ECHO = A1;

// ---- Servo ----
const uint8_t SERVO_PIN = 10;

Servo srv;

static inline void srWrite(uint8_t v) {
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLK, MSBFIRST, v);
  digitalWrite(SR_LATCH, HIGH);
}

void kill_everything() {
  // 1) Motors OFF (outputs disabled and data neutral)
  pinMode(SR_DATA,  OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_CLK,   OUTPUT);
  pinMode(SR_OE,    OUTPUT);
  digitalWrite(SR_CLK, LOW);
  digitalWrite(SR_LATCH, LOW);
  digitalWrite(SR_OE, HIGH);     // disable (active LOW)
  srWrite(0x00);                 // neutral

  // 2) Ultrasonic idle
  pinMode(US_TRIG, OUTPUT);
  digitalWrite(US_TRIG, LOW);    // no pings
  pinMode(US_ECHO, INPUT);       // high-Z

  // 3) Servo quiet
  if (srv.attached()) srv.detach();
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);  // actively drive LOW to prevent chatter
}

void setup() {
  // Optional: a brief serial note so your Jetson sees confirmation
  Serial.begin(115200);
  delay(80);
  Serial.println(F("STATUS killed (KillAll.ino)"));

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  kill_everything();
}

void loop() {
  // Slow heartbeat blink to indicate the board is in KILL mode
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(LED_BUILTIN, LOW);
  delay(500);
}

