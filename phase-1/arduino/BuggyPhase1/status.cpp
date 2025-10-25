#include <Arduino.h>
#include "status.h"
#include "motion.h"
#include "ultrasonic.h"
#include "config.h"
#include "servo_scan.h"

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

void printStat() {
  // STAT mode=<F|B|L|R|S> spd=<0..255> thresh=<cm or 0> last_cm=<value> sweep=<0|1>
  MotionMode m = motion_get_mode();
  char modeChar = 'S';
  switch (m) {
    case MODE_FORWARD_FAST: case MODE_FORWARD_SLOW: modeChar = 'F'; break;
    case MODE_BACK_SLOW: modeChar = 'B'; break;
    case MODE_ARC_LEFT: case MODE_SPIN_LEFT: modeChar = 'L'; break;
    case MODE_ARC_RIGHT: case MODE_SPIN_RIGHT: modeChar = 'R'; break;
    case MODE_STOP: default: modeChar = 'S'; break;
  }
  extern uint16_t getSafetyThresholdCM();
  extern int motion_get_global_pwm();
  Serial.print("STAT mode="); Serial.print(modeChar);
  Serial.print(" spd="); Serial.print(motion_get_global_pwm());
  Serial.print(" thresh="); Serial.print(getSafetyThresholdCM());
  float cm = ultrasonic_last_cm();
  Serial.print(" last_cm="); if (isnan(cm)) Serial.print(-1); else Serial.print(cm, 1);
  Serial.print(" sweep="); Serial.println(servo_is_sweeping() ? 1 : 0);
}

void printULS() {
  // ULS cm=<val> angle=<deg or -1> t_ms=<millis>
  float cm = ultrasonic_last_cm();
  Serial.print("ULS cm="); if (isnan(cm)) Serial.print(-1); else Serial.print(cm, 1);
  Serial.print(" angle="); Serial.print(servo_get_current_deg());
  Serial.print(" t_ms="); Serial.println(millis());
}
