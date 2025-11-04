#include <Arduino.h>
#include <Servo.h>
#include "servo_scan.h"
#include "pins.h"
#include "config.h"

static Servo g_servo;
static int g_target_deg = 90;
static int g_current_deg = 90;
static unsigned long g_last_move_ms = 0;
static bool g_attached = false;
static bool g_sweeping = false;

void servo_init() {
  // Start detached to avoid idle jitter
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  g_attached = false;
  g_last_move_ms = millis();
}

void servo_set_target_deg(int deg) {
  if (deg < 0) deg = 0; if (deg > 180) deg = 180;
  if (deg != g_target_deg) {
    g_target_deg = deg;
    if (!g_attached) { g_servo.attach(SERVO_PIN); g_attached = true; }
    g_servo.write(g_target_deg);
    g_current_deg = g_target_deg;
    g_last_move_ms = millis();
    g_sweeping = false; // stop any sweep when explicit target is set
  }
}

bool servo_is_settled() {
  return (millis() - g_last_move_ms) >= SERVO_SETTLE_MS && g_current_deg == g_target_deg;
}

int servo_get_target_deg() { return g_target_deg; }
int servo_get_current_deg() { return g_current_deg; }

void servo_tick() {
  // Keep servo attached during runtime for continuous scanning
  // Detaching causes issues with the autonomous sweep behavior
  // The servo needs to remain attached to respond quickly to new positions
  
  // Note: If jitter becomes an issue, we can add a longer idle timeout
  // before detaching (e.g., only detach if no movement for 5+ seconds)
}

void servo_stopSweep() {
  g_sweeping = false;
  // Keep servo attached even when stopping sweep
  // This allows quick response to new positioning commands
}

void servo_startSweep() {
  g_sweeping = true; // placeholder for future sweep implementation
}

bool servo_is_sweeping() { return g_sweeping; }
