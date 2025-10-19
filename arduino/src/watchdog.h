#pragma once
#include <Arduino.h>

void watchdog_init();
void watchdog_tick();
void watchdog_note_hb();
