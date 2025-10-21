// ServoTest.ino — Jetson-terminal-friendly, loud output + heartbeat
// Board: Arduino UNO R4 WiFi
// Serial: 115200
// Legacy carry: SR pins, ULS pins; Servo moved to D2 to avoid shield PWM pins.

#include <Arduino.h>
#include <Servo.h>

// ---- Shift register / L293D (legacy) ----
const uint8_t SR_DATA  = 8;
const uint8_t SR_LATCH = 12;
const uint8_t SR_CLK   = 4;
const uint8_t SR_OE    = 7;    // active LOW

// ---- Ultrasonic (legacy) ----
const uint8_t US_TRIG = A0;
const uint8_t US_ECHO = A1;

// ---- Servo on safe pin ----
const uint8_t SERVO_PIN = 10;

Servo srv;

// ---------- Utils ----------
static inline void srWrite(uint8_t v) {
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLK, MSBFIRST, v);
  digitalWrite(SR_LATCH, HIGH);
}

static inline void motors_disable_now() {
  pinMode(SR_DATA,  OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_CLK,   OUTPUT);
  pinMode(SR_OE,    OUTPUT);
  digitalWrite(SR_CLK, LOW);
  digitalWrite(SR_LATCH, LOW);
  // Keep outputs disabled BEFORE touching data
  digitalWrite(SR_OE, HIGH);   // disable (active LOW)
  srWrite(0x00);               // neutral pattern
}

static inline long uls_ping_us() {
  digitalWrite(US_TRIG, LOW); delayMicroseconds(2);
  digitalWrite(US_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(US_TRIG, LOW);
  return pulseIn(US_ECHO, HIGH, 30000UL); // 30 ms timeout
}

static inline float us_to_cm(long us) {
  return (us > 0) ? (us / 58.0f) : -1.0f;
}

// ---------- State ----------
unsigned long t_beat = 0, t_ultra = 0, t_servo = 0;
int beat = 0;
int pos = 90, dir = +1;

void setup() {
  // Kill motors FIRST so nothing twitches
  motors_disable_now();

  // LED heartbeat
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // Serial next — very small delay to let CDC come up
  Serial.begin(115200);
  delay(100);
  Serial.println(F("new code"));
  Serial.println(F("STATUS ready"));

  // Sensors/actuators
  pinMode(US_TRIG, OUTPUT);
  pinMode(US_ECHO, INPUT);

  srv.attach(SERVO_PIN);
  srv.write(90);
  delay(150);

  // Immediate first heartbeat line so you see SOMETHING
  Serial.println(F("HEARTBEAT 0"));
}

void loop() {
  unsigned long now = millis();

  // ---- 1) Heartbeat every 1000 ms: LED blink + print ----
  if (now - t_beat >= 1000) {
    t_beat = now;
    beat++;
    digitalWrite(LED_BUILTIN, (beat & 1) ? HIGH : LOW);
    Serial.print(F("HEARTBEAT "));
    Serial.println(beat);
    // Ensure bytes leave the buffer even if host is flaky
    Serial.flush();
  }

  // ---- 2) Ultrasonic every ~250 ms ----
  if (now - t_ultra >= 250) {
    t_ultra = now;
    long us = uls_ping_us();
    if (us == 0) {
      Serial.println(F("ULS timeout"));
    } else {
      float cm = us_to_cm(us);
      Serial.print(F("ULS cm="));
      Serial.println(cm, 1);
    }
  }

  // ---- 3) Servo small nudge every ~1200 ms ----
  if (now - t_servo >= 1200) {
    t_servo = now;
    pos += 10 * dir;
    if (pos > 120) { pos = 120; dir = -1; }
    if (pos < 60)  { pos = 60;  dir = +1; }
    srv.write(pos);
    Serial.print(F("SRV deg="));
    Serial.println(pos);
  }
}
