#pragma once
#include <Arduino.h>

void status_init();
void status_tick();
void status_emit_once();

// Verbosity control: in Bench mode default comes from BENCH_VERBOSE_DEFAULT; in Runtime defaults to verbose
void status_set_verbose(bool on);
bool status_get_verbose();
