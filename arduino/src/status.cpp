#include <Arduino.h>
#include "status.h"
#include "motion.h"
#include "ultrasonic.h"
#include "config.h"

static unsigned long g_last_stat_ms = 0;

void status_init() {
  g_last_stat_ms = millis();
}

void status_tick() {
  unsigned long now = millis();
  if (now - g_last_stat_ms >= STAT_PERIOD_MS) {
    Serial.print("STAT,");
    Serial.print(motion_mode_name(motion_get_mode()));
    Serial.print(",");
    Serial.print(motion_left_pwm());
    Serial.print(",");
    Serial.print(motion_right_pwm());
    Serial.print(",");
    float cm = ultrasonic_last_cm();
    if (isnan(cm)) Serial.println("NA"); else Serial.println(cm, 1);
    g_last_stat_ms = now;
  }
}
