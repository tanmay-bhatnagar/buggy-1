#pragma once
#include <Arduino.h>

// 74HC595 + L293D shield mapping (global OE for speed; PWM is inverted)
// SER=D8, CLK=D4, LATCH=D12, OE=D7 (active-LOW)
// Preferred names:
#define PIN_595_SER   8
#define PIN_595_CLK   4
#define PIN_595_LATCH 12
#define PIN_595_OE    7
// Back-compat aliases (used by motion.cpp)
#define SR_DATA   PIN_595_SER
#define SR_CLK    PIN_595_CLK
#define SR_LATCH  PIN_595_LATCH
#define SR_OE     PIN_595_OE

// Legacy per-side EN pins are unused with 595 shield (one global OE)
#define EN_LEFT  -1
#define EN_RIGHT -1

// Ultrasonic sensor
#define ULTRASONIC_TRIG A0
#define ULTRASONIC_ECHO A1

// Servo signal (detach when idle)
#define SERVO_PIN 10

// Motor bit mapping (595 Q lines -> L293D A/B)
// Q-line wiring per shield (documented for clarity):
//   Q0 -> M4_A (IN A for Motor 4 / Front-Right)
//   Q1 -> M2_A (IN A for Motor 2 / Rear-Left)
//   Q2 -> M1_A (IN A for Motor 1 / Front-Left)
//   Q3 -> M1_B (IN B for Motor 1 / Front-Left)
//   Q4 -> M2_B (IN B for Motor 2 / Rear-Left)
//   Q5 -> M3_A (IN A for Motor 3 / Rear-Right)
//   Q6 -> M4_B (IN B for Motor 4 / Front-Right)
//   Q7 -> M3_B (IN B for Motor 3 / Rear-Right)
#define M1_A_BIT 2
#define M1_B_BIT 3
#define M2_A_BIT 1
#define M2_B_BIT 4
#define M3_A_BIT 5
#define M3_B_BIT 7
#define M4_A_BIT 0
#define M4_B_BIT 6

struct Mbits { uint8_t A; uint8_t B; };
static const Mbits MB[4] = { {M1_A_BIT,M1_B_BIT}, {M2_A_BIT,M2_B_BIT}, {M3_A_BIT,M3_B_BIT}, {M4_A_BIT,M4_B_BIT} };

// Motor polarity (false,true,false,true) => {M1 FL, M2 RL, M3 RR, M4 FR}
static const bool REV[4] = { false, true, false, true };

inline void pins_init() {
  pinMode(SR_DATA, OUTPUT);
  pinMode(SR_CLK, OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_OE, OUTPUT);
  // Enable 595 outputs (active-LOW). analogWrite used for PWM (inverted)
  analogWrite(SR_OE, 0); // fully enabled

  pinMode(ULTRASONIC_TRIG, OUTPUT);
  digitalWrite(ULTRASONIC_TRIG, LOW);
  pinMode(ULTRASONIC_ECHO, INPUT);
}
