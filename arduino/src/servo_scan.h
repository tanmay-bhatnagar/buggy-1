#pragma once
#include <Arduino.h>

void servo_init();
void servo_set_target_deg(int deg);
bool servo_is_settled();
int servo_get_target_deg();
int servo_get_current_deg();
void servo_tick();
