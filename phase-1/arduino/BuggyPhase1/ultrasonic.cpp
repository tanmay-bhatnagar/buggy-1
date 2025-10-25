#include <Arduino.h>
#include "ultrasonic.h"
#include "pins.h"
#include "config.h"

static float g_last_cm = NAN;
static unsigned long g_last_ping_ms = 0;
static uint16_t g_safety_thresh_cm = 0; // 0 = disabled
static uint8_t g_consec_hits = 0;
static unsigned long g_last_sample_ms = 0;

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
  // Optional background sampler for safety threshold with debounce
  if (g_safety_thresh_cm == 0) return;
  unsigned long now = millis();
  if (now - g_last_sample_ms < 80) return;
  g_last_sample_ms = now;
  float cm = readUltrasonicCM();
  if (!isnan(cm) && cm > 0 && cm < (float)g_safety_thresh_cm) {
    if (g_consec_hits < 255) g_consec_hits++;
  } else {
    g_consec_hits = 0;
  }
  if (g_consec_hits >= 3) {
    // 3-hit debounce: trigger STOP once
    extern void motion_set_mode(MotionMode);
    extern void status_emit_once();
    motion_set_mode(MODE_STOP);
    status_emit_once();
    Serial.println("EVT stop=safety");
    g_consec_hits = 0;
  }
}

float readUltrasonicCM() {
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);
  unsigned long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 30000UL);
  if (duration == 0) {
    g_last_cm = NAN;
    return g_last_cm;
  }
  float cm = (float)duration / 58.0f;
  if (cm < DIST_MIN_CM || cm > DIST_MAX_CM) {
    g_last_cm = NAN;
  } else {
    g_last_cm = cm;
  }
  return g_last_cm;
}

void setSafetyThresholdCM(uint16_t cm) { g_safety_thresh_cm = cm; }
uint16_t getSafetyThresholdCM() { return g_safety_thresh_cm; }
