#pragma once
#include <Arduino.h>

void ultrasonic_init();
void ultrasonic_tick();
float ultrasonic_measure_cm();
float ultrasonic_last_cm();

// Compact on-demand API
float readUltrasonicCM();
void setSafetyThresholdCM(uint16_t cm); // 0 disables
uint16_t getSafetyThresholdCM();
