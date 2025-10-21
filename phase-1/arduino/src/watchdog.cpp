#include <Arduino.h>
#include "watchdog.h"
#include "config.h"
#include "motion.h"

static unsigned long g_last_hb_ms = 0;
static bool g_latched = false;

void watchdog_init() {
  g_last_hb_ms = millis();
}

void watchdog_tick() {
  // This watchdog relies on serial layer to be alive. If no HB observed
  // via higher-level integration, we can periodically force STOP here.
  unsigned long now = millis();
  if (!g_latched && (now - g_last_hb_ms > HB_TIMEOUT_MS)) {
    motion_set_mode(MODE_STOP);
    g_latched = true; // latch until HB or explicit motion cmd
  }
}

// Optional: expose a function that serial layer can call on receiving HB
void watchdog_note_hb() {
  g_last_hb_ms = millis();
  g_latched = false;
}
