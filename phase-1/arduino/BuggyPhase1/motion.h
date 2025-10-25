#pragma once
#include <Arduino.h>

enum MotionMode {
  MODE_STOP = 0,
  MODE_FORWARD_FAST,
  MODE_FORWARD_SLOW,
  MODE_BACK_SLOW,
  MODE_ARC_LEFT,
  MODE_ARC_RIGHT,
  MODE_SPIN_LEFT,
  MODE_SPIN_RIGHT
};

void motion_init();
void motion_set_mode(MotionMode mode);
MotionMode motion_get_mode();
void motion_tick();
const char* motion_mode_name(MotionMode m);
int motion_left_pwm();
int motion_right_pwm();

// Explicit OE PWM override for compact commands (0–255); -1 clears override
void motion_pwm_speed(uint8_t pwm);
void motion_clear_pwm_speed();
int motion_get_pwm_override();
int motion_get_global_pwm();
