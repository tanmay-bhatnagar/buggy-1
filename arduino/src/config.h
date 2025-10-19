#pragma once

#define BAUD_RATE 115200

// PWM tiers (side-level). If EN pins are not available, SLOW=FAST fallback.
#define PWM_FAST 230
#define PWM_SLOW 150

// Timing (ms)
#define SERVO_SETTLE_MS 100
#define MEAS_COOLDOWN_MS 40
#define HB_TIMEOUT_MS 600
#define STAT_PERIOD_MS 250

// Pulsed SLOW emulation when no EN pins (ms)
#define SLOW_PULSE_ON_MS 40
#define SLOW_PULSE_OFF_MS 15

// Ultrasonic validity clamp (cm)
#define DIST_MIN_CM 3
#define DIST_MAX_CM 300
