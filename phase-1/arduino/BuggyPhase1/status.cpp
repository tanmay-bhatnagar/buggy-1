#include <Arduino.h>
#include "status.h"
#include "motion.h"
#include "ultrasonic.h"
#include "config.h"

static unsigned long g_last_stat_ms = 0;
static MotionMode g_last_mode = MODE_STOP;
static int g_last_left_pwm = -1;
static int g_last_right_pwm = -1;
static float g_last_cm_sent = NAN;
static bool g_verbose = true;

void status_init() {
  g_last_stat_ms = millis();
  #if BENCH_MODE
    g_verbose = (BENCH_VERBOSE_DEFAULT != 0);
  #else
    g_verbose = true;
  #endif
}

void status_tick() {
  unsigned long now = millis();
  MotionMode m = motion_get_mode();
  int lp = motion_left_pwm();
  int rp = motion_right_pwm();
  float cm = ultrasonic_last_cm();

  #if BENCH_MODE
    // In Bench Mode, do not auto-print unless verbose is enabled
    if (!g_verbose) return;
  #endif

  // Runtime (or Bench+verbose): emit periodically
  bool emit = false;
  if (now - g_last_stat_ms >= STAT_PERIOD_MS) emit = true;
  if (!emit) return;

  Serial.print("STAT,");
  Serial.print(motion_mode_name(m));
  Serial.print(",");
  Serial.print(lp);
  Serial.print(",");
  Serial.print(rp);
  Serial.print(",");
  if (isnan(cm)) Serial.print("NA"); else Serial.print(cm, 1);
  #if BENCH_MODE
    Serial.print(",MODE=BENCH");
  #endif
  Serial.println();

  g_last_stat_ms = now;
  g_last_mode = m;
  g_last_left_pwm = lp;
  g_last_right_pwm = rp;
  g_last_cm_sent = cm;
}

void status_emit_once() {
  MotionMode m = motion_get_mode();
  int lp = motion_left_pwm();
  int rp = motion_right_pwm();
  float cm = ultrasonic_last_cm();
  Serial.print("STAT,");
  Serial.print(motion_mode_name(m));
  Serial.print(",");
  Serial.print(lp);
  Serial.print(",");
  Serial.print(rp);
  Serial.print(",");
  if (isnan(cm)) Serial.print("NA"); else Serial.print(cm, 1);
  #if BENCH_MODE
    Serial.print(",MODE=BENCH");
  #endif
  Serial.println();
}

void status_set_verbose(bool on) { g_verbose = on; }
bool status_get_verbose() { return g_verbose; }
