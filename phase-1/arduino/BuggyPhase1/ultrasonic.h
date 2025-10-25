#pragma once
#include <Arduino.h>

void ultrasonic_init();
void ultrasonic_tick();
float ultrasonic_measure_cm();
float ultrasonic_last_cm();
