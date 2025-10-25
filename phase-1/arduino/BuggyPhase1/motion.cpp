#include <Arduino.h>
#include "motion.h"
#include "pins.h"
#include "config.h"

static MotionMode g_mode = MODE_STOP;
static int g_left_pwm = 0;
static int g_right_pwm = 0;
static unsigned long g_pulse_ms = 0;
static int g_pwm_override = -1; // -1 = none; else 0..255

// 74HC595 shift register state
static uint8_t g_latch_state = 0x00;

static void sr_apply() {
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLK, MSBFIRST, g_latch_state);
  digitalWrite(SR_LATCH, HIGH);
}
static void sr_set_bit(uint8_t bit, bool high) {
  if (high) g_latch_state |=  (1u << bit); else g_latch_state &= ~(1u << bit);
  sr_apply();
}
static void sr_zero_all() {
  g_latch_state = 0x00; sr_apply();
}

// dir: -1 = REV, 0 = REL (brake/coast), +1 = FWD; applies REV[] mapping
static void set_motor_dir(uint8_t motorIndex, int dir) {
  int d = dir;
  if (d != 0 && REV[motorIndex]) d = (d > 0) ? -1 : +1;
  const Mbits &mb = MB[motorIndex];
  if (d == 0) { sr_set_bit(mb.A, 0); sr_set_bit(mb.B, 0); }
  else if (d > 0) { sr_set_bit(mb.A, 1); sr_set_bit(mb.B, 0); }
  else { sr_set_bit(mb.A, 0); sr_set_bit(mb.B, 1); }
}

static void set_all_rel() { for (uint8_t m=0;m<4;m++) set_motor_dir(m, 0); }

void motion_init() {
  set_all_rel();
  // Enable outputs fully initially
  analogWrite(SR_OE, 0); // active-LOW OE, 0 = fully enabled
  motion_set_mode(MODE_STOP);
}

void motion_set_mode(MotionMode mode) {
  if (g_mode != mode) {
    g_mode = mode;
  }
}

MotionMode motion_get_mode() { return g_mode; }

const char* motion_mode_name(MotionMode m) {
  switch (m) {
    case MODE_STOP: return "STOP";
    case MODE_FORWARD_FAST: return "F_FAST";
    case MODE_FORWARD_SLOW: return "F_SLOW";
    case MODE_BACK_SLOW: return "B_SLOW";
    case MODE_ARC_LEFT: return "ARC_L";
    case MODE_ARC_RIGHT: return "ARC_R";
    case MODE_SPIN_LEFT: return "SPIN_L";
    case MODE_SPIN_RIGHT: return "SPIN_R";
  }
  return "UNKNOWN";
}

int motion_left_pwm() { return g_left_pwm; }
int motion_right_pwm() { return g_right_pwm; }
int motion_get_pwm_override() { return g_pwm_override; }

void motion_tick() {
  // Decide directions and conceptual per-side speeds
  int dirL = 0, dirR = 0;
  int pwmL = 0, pwmR = 0;
  // Global OE speed tier (one for all motors, inverted on OE)
  int global_pwm = 0;

  switch (g_mode) {
    case MODE_STOP:
      dirL = dirR = 0; pwmL = pwmR = 0; global_pwm = 0; break;
    case MODE_FORWARD_FAST:
      dirL = +1; dirR = +1; pwmL = pwmR = PWM_FAST; global_pwm = PWM_FAST; break;
    case MODE_FORWARD_SLOW:
      dirL = +1; dirR = +1; pwmL = pwmR = PWM_SLOW; global_pwm = PWM_SLOW; break;
    case MODE_BACK_SLOW:
      dirL = -1; dirR = -1; pwmL = pwmR = PWM_SLOW; global_pwm = PWM_SLOW; break;
    case MODE_ARC_LEFT:
      dirL = +1; dirR = +1; pwmL = PWM_SLOW; pwmR = PWM_FAST; global_pwm = PWM_FAST; break;
    case MODE_ARC_RIGHT:
      dirL = +1; dirR = +1; pwmL = PWM_FAST; pwmR = PWM_SLOW; global_pwm = PWM_FAST; break;
    case MODE_SPIN_LEFT:
      dirL = -1; dirR = +1; pwmL = PWM_SLOW; pwmR = PWM_SLOW; global_pwm = PWM_SLOW; break;
    case MODE_SPIN_RIGHT:
      dirL = +1; dirR = -1; pwmL = PWM_SLOW; pwmR = PWM_SLOW; global_pwm = PWM_SLOW; break;
  }

  // Apply explicit override if present
  if (g_pwm_override >= 0) {
    global_pwm = g_pwm_override;
  }
  // Apply global speed tier via OE (active-LOW)
  #if BENCH_MODE
    // In Bench Mode, avoid PWM on OE to prevent timer conflicts; treat any >0 as fully enabled
    digitalWrite(SR_OE, (global_pwm > 0) ? LOW : HIGH);
  #else
    analogWrite(SR_OE, 255 - constrain(global_pwm, 0, 255));
  #endif

  // Pulse-gate sides that should be "slow" under a FAST global tier (arcs)
  unsigned long now = millis();
  unsigned long phase = now - g_pulse_ms;
  if (phase > (SLOW_PULSE_ON_MS + SLOW_PULSE_OFF_MS)) {
    g_pulse_ms = now;
    phase = 0;
  }
  bool pulse_on = (phase < SLOW_PULSE_ON_MS);

  auto drive_side = [&](bool left, int pwm, int dir){
    uint8_t m1 = left ? 0 : 2; // left pair: M1,M2 ; right pair: M3,M4
    uint8_t m2 = left ? 1 : 3;
    if (dir == 0) { set_motor_dir(m1, 0); set_motor_dir(m2, 0); return; }
    bool wants_slow = (pwm <= PWM_SLOW);
    bool use_pulse = (global_pwm == PWM_FAST) && wants_slow; // only pulse-reduce when global is FAST
    if (!use_pulse || pulse_on) {
      set_motor_dir(m1, dir);
      set_motor_dir(m2, dir);
    } else {
      set_motor_dir(m1, 0);
      set_motor_dir(m2, 0);
    }
  };

  drive_side(true, pwmL, dirL);
  drive_side(false, pwmR, dirR);

  g_left_pwm = pwmL;
  g_right_pwm = pwmR;
}

void motion_pwm_speed(uint8_t pwm) {
  g_pwm_override = (int)pwm;
}
void motion_clear_pwm_speed() {
  g_pwm_override = -1;
}
int motion_get_global_pwm() {
  // Return last applied global PWM value (override wins during tick)
  if (g_pwm_override >= 0) return g_pwm_override;
  switch (g_mode) {
    case MODE_FORWARD_FAST: return PWM_FAST;
    case MODE_FORWARD_SLOW: return PWM_SLOW;
    case MODE_BACK_SLOW: return PWM_SLOW;
    case MODE_ARC_LEFT: return PWM_FAST;
    case MODE_ARC_RIGHT: return PWM_FAST;
    case MODE_SPIN_LEFT: return PWM_SLOW;
    case MODE_SPIN_RIGHT: return PWM_SLOW;
    default: return 0;
  }
}
