#pragma once
#include <Arduino.h>

// Observed HW-130 shield mapping (example):
//  - Left side direction: L_FWD_PIN, L_BWD_PIN
//  - Right side direction: R_FWD_PIN, R_BWD_PIN
//  - Some variants DO NOT expose EN (PWM) pins per side.
// Adjust to your unit if different and set EN_* = -1 when absent.

// Left side H-bridge direction pins
#define L_FWD_PIN 2
#define L_BWD_PIN 3
// Right side H-bridge direction pins
#define R_FWD_PIN 4
#define R_BWD_PIN 5

// Optional side PWM enable pins (set to -1 if not present on your shield)
#define EN_LEFT  -1
#define EN_RIGHT -1

// Servo and Ultrasonic pins
#define SERVO_PIN 6
#define ULTRASONIC_TRIG 7
#define ULTRASONIC_ECHO 8

// Motor polarity mask (True means that motor wiring is reversed)
static const bool REV[4] = {true, false, true, false};

inline void pins_init() {
  pinMode(L_FWD_PIN, OUTPUT);
  pinMode(L_BWD_PIN, OUTPUT);
  pinMode(R_FWD_PIN, OUTPUT);
  pinMode(R_BWD_PIN, OUTPUT);
  if (EN_LEFT >= 0) pinMode(EN_LEFT, OUTPUT);
  if (EN_RIGHT >= 0) pinMode(EN_RIGHT, OUTPUT);
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);
}
