#include <Arduino.h>
#include "motion.h"
#include "pins.h"
#include "config.h"

static MotionMode g_mode = MODE_STOP;
static int g_left_pwm = 0;
static int g_right_pwm = 0;
static unsigned long g_pulse_ms = 0;

static void set_side(bool left, int pwm, int dir) {
  int pwm_pin = left ? EN_LEFT : EN_RIGHT;
  int fwd_pin = left ? L_FWD_PIN : R_FWD_PIN;
  int bwd_pin = left ? L_BWD_PIN : R_BWD_PIN;

  if (dir > 0) {
    digitalWrite(fwd_pin, HIGH);
    digitalWrite(bwd_pin, LOW);
  } else if (dir < 0) {
    digitalWrite(fwd_pin, LOW);
    digitalWrite(bwd_pin, HIGH);
  } else {
    digitalWrite(fwd_pin, LOW);
    digitalWrite(bwd_pin, LOW);
  }

  if (pwm_pin >= 0) {
    analogWrite(pwm_pin, pwm);
  }
}

void motion_init() {
  motion_set_mode(MODE_STOP);
}

void motion_set_mode(MotionMode mode) {
  // Idempotent: don't reset timers if same mode
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

void motion_tick() {
  int fast = PWM_FAST;
  int slow = PWM_SLOW;
  if (EN_LEFT < 0 || EN_RIGHT < 0) {
    slow = fast;
  }

  int dirL = 0, dirR = 0;
  int pwmL = 0, pwmR = 0;

  switch (g_mode) {
    case MODE_STOP:
      dirL = dirR = 0; pwmL = pwmR = 0; break;
    case MODE_FORWARD_FAST:
      dirL = +1; dirR = +1; pwmL = pwmR = fast; break;
    case MODE_FORWARD_SLOW:
      dirL = +1; dirR = +1; pwmL = pwmR = slow; break;
    case MODE_BACK_SLOW:
      dirL = -1; dirR = -1; pwmL = pwmR = slow; break;
    case MODE_ARC_LEFT:
      dirL = +1; dirR = +1; pwmL = slow; pwmR = fast; break;
    case MODE_ARC_RIGHT:
      dirL = +1; dirR = +1; pwmL = fast; pwmR = slow; break;
    case MODE_SPIN_LEFT:
      dirL = -1; dirR = +1; pwmL = slow; pwmR = slow; break;
    case MODE_SPIN_RIGHT:
      dirL = +1; dirR = -1; pwmL = slow; pwmR = slow; break;
  }

  if (EN_LEFT >= 0 && EN_RIGHT >= 0) {
    set_side(true, pwmL, dirL);
    set_side(false, pwmR, dirR);
  } else {
    // Emulate SLOW via coarse pulsing when EN pins are not available
    unsigned long now = millis();
    bool pulse_on = true;
    unsigned long phase = now - g_pulse_ms;
    if (phase > (SLOW_PULSE_ON_MS + SLOW_PULSE_OFF_MS)) {
      g_pulse_ms = now;
      phase = 0;
    }
    if (phase < SLOW_PULSE_ON_MS) pulse_on = true; else pulse_on = false;

    auto drive = [&](bool left, int pwm, int dir) {
      int fwd_pin = left ? L_FWD_PIN : R_FWD_PIN;
      int bwd_pin = left ? L_BWD_PIN : R_BWD_PIN;
      if (dir == 0) {
        digitalWrite(fwd_pin, LOW);
        digitalWrite(bwd_pin, LOW);
        return;
      }
      bool use_pulse = (pwm <= PWM_SLOW);
      if (!use_pulse || pulse_on) {
        if (dir > 0) { digitalWrite(fwd_pin, HIGH); digitalWrite(bwd_pin, LOW); }
        else { digitalWrite(fwd_pin, LOW); digitalWrite(bwd_pin, HIGH); }
      } else {
        // Off phase of pulse: coast/stop that side
        digitalWrite(fwd_pin, LOW);
        digitalWrite(bwd_pin, LOW);
      }
    };

    drive(true, pwmL, dirL);
    drive(false, pwmR, dirR);
  }

  g_left_pwm = pwmL;
  g_right_pwm = pwmR;
}
