// UNO R4 WiFi + L293D shield test: SG90 + HC-SR04 + STOP/GO over Serial
#include <Arduino.h>
#include <Servo.h>
#include <algorithm>

Servo s;

// ---- Pin map (unchanged) ----
const uint8_t SERVO_PIN = 10;   // SER1 on the motor shield (upper header). Use 9 if you move to SER2/lower header.
const uint8_t TRIG_PIN  = A0;   // HC-SR04 TRIG
const uint8_t ECHO_PIN  = A1;   // HC-SR04 ECHO

// ---- Sweep config ----
int angle      = 20;    // start angle
int step_deg   = 10;    // step per measurement
const int MINA = 20;    // keep some slack so wires don’t twist
const int MAXA = 160;

bool running = true;    // STOP/GO state

// Utility: median of 3 (for noise-robust distance)
static inline unsigned long median3(unsigned long a, unsigned long b, unsigned long c) {
  if (a > b) std::swap(a, b);
  if (b > c) std::swap(b, c);
  if (a > b) std::swap(a, b);
  return b;
}

// Trigger HC-SR04 once; returns echo µs (0 if timeout)
unsigned long echoMicrosOnce() {
  digitalWrite(TRIG_PIN, LOW);   delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  // 25,000 µs timeout ≈ ~4.3 m max
  return pulseIn(ECHO_PIN, HIGH, 25000UL);
}

// Read distance (cm), median of 3 pings. Returns -1 on timeout.
int readDistanceCm() {
  unsigned long a = echoMicrosOnce();
  delay(10);
  unsigned long b = echoMicrosOnce();
  delay(10);
  unsigned long c = echoMicrosOnce();

  unsigned long us = median3(a, b, c);
  if (us == 0) return -1;                // timeout
  // HC-SR04: distance_cm ≈ us / 58.0
  return (int)((us + 29) / 58);          // rounded
}

void printHelp() {
  Serial.println(F("Commands:"));
  Serial.println(F("  STOP  -> pause servo sweep (keeps last angle)"));
  Serial.println(F("  GO    -> resume sweep"));
  Serial.println(F("  HELP  -> show this"));
}

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  Serial.begin(115200);
  while (!Serial) { /* UNO R4 USB enumerate */ }

  s.attach(SERVO_PIN);
  delay(300);

  Serial.println(F("\n[UNO R4 + L293D] Servo+Ultrasonic test ready."));
  Serial.println(F("Servo on D10 (SER1). HC-SR04 TRIG=A0, ECHO=A1."));
  printHelp();
}

void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == F("STOP")) {
    running = false;
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println(F("[STATE] STOPPED."));
  } else if (cmd == F("GO")) {
    running = true;
    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println(F("[STATE] RUNNING."));
  } else if (cmd == F("HELP")) {
    printHelp();
  }
}

void loop() {
  handleSerial();

  if (running) {
    s.write(angle);
    digitalWrite(LED_BUILTIN, HIGH);
    delay(250); // let the horn settle before measuring
  } else {
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }

  // Always read distance so you can observe the sensor even when paused
  int dcm = readDistanceCm();

  // Stream a tidy CSV-ish line you can log/plot later
  // Format: angle,<deg>,distance_cm,<d or -1>
  Serial.print(F("angle,"));
  Serial.print(angle);
  Serial.print(F(",distance_cm,"));
  Serial.println(dcm);

  if (running) {
    angle += step_deg;
    if (angle >= MAXA || angle <= MINA) {
      step_deg = -step_deg;           // bounce
      angle += step_deg;
    }
  }
}
