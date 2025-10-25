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

void status_init() {
  g_last_stat_ms = millis();
}

void status_tick() {
  unsigned long now = millis();
  bool emit = false;
  unsigned long period = STAT_PERIOD_MS;

  #if BENCH_MODE
    period = 1000; // ~1 Hz in bench mode
  #endif

  // Emit periodically per mode
  if (now - g_last_stat_ms >= period) {
    emit = true;
  }

  // Also emit on change to help bench clarity
  MotionMode m = motion_get_mode();
  int lp = motion_left_pwm();
  int rp = motion_right_pwm();
  float cm = ultrasonic_last_cm();
  if (m != g_last_mode || lp != g_last_left_pwm || rp != g_last_right_pwm) {
    emit = true;
  }

  if (emit) {
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
}
