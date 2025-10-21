#include <Arduino.h>
#include "ultrasonic.h"
#include "pins.h"
#include "config.h"

static float g_last_cm = NAN;
static unsigned long g_last_ping_ms = 0;

void ultrasonic_init() {
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);
}

static float clamp_cm(float cm) {
  if (cm < DIST_MIN_CM || cm > DIST_MAX_CM) return NAN;
  return cm;
}

float ultrasonic_measure_cm() {
  // Respect measurement cooldown
  if (millis() - g_last_ping_ms < MEAS_COOLDOWN_MS) {
    return g_last_cm;
  }
  // Ensure servo is settled before pinging to avoid echo contamination
  extern bool servo_is_settled();
  if (!servo_is_settled()) {
    g_last_cm = NAN;
    g_last_ping_ms = millis();
    return g_last_cm;
  }
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);

  unsigned long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 30000UL);
  if (duration == 0) {
    g_last_cm = NAN;
    g_last_ping_ms = millis();
    return g_last_cm;
  }
  float cm = (float)duration / 58.0f;
  g_last_cm = clamp_cm(cm);
  g_last_ping_ms = millis();
  return g_last_cm;
}

float ultrasonic_last_cm() { return g_last_cm; }

void ultrasonic_tick() {
  // No periodic autonomous pings; measurements occur on demand from protocol
}
