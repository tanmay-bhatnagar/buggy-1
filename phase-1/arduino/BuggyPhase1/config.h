#pragma once

#define BAUD_RATE 115200

// Bench Mode vs Runtime Mode
// Set BENCH_MODE to 1 to enable manual bench testing from a serial terminal.
//   - Bench Mode: long heartbeat timeout (no rapid STOP while typing),
//                 silent by default (no periodic status), boot banner includes "+BENCH".
//   - Runtime Mode: short heartbeat timeout; Jetson app must send HB.
// Flip this flag and reflash to switch modes.
#define BENCH_MODE 1

// Default verbosity in Bench Mode: 0 = fully silent (no periodic STAT)
// You can toggle at runtime via VERBOSE,ON / VERBOSE,OFF in the serial console.
#define BENCH_VERBOSE_DEFAULT 0

// Default PWM for compact F/B/L/R when <n> is omitted (0–255)
#define DEFAULT_BENCH_PWM 160

// Global PWM tiers (applied on 74HC595 OE; active-LOW so duty is inverted)
#define PWM_FAST 230
#define PWM_SLOW 150

// Timing (ms)
#define SERVO_SETTLE_MS 100
#define MEAS_COOLDOWN_MS 40
#define STAT_PERIOD_MS 250

// Heartbeat timeout derived from mode
#if BENCH_MODE
#define HB_TIMEOUT_MS 60000
#else
#define HB_TIMEOUT_MS 600
#endif

// Pulsing knobs for ARC inner track (ms)
#define SLOW_PULSE_ON_MS 40
#define SLOW_PULSE_OFF_MS 15

// Ultrasonic validity clamp (cm)
#define DIST_MIN_CM 3
#define DIST_MAX_CM 300
