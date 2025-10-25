#include <Arduino.h>
#include "serial_proto.h"
#include "motion.h"
#include "servo_scan.h"
#include "ultrasonic.h"
#include "servo_scan.h"
#include "config.h"
#include "watchdog.h"
#include "status.h"

static String g_line;

static void handle_command(const String& line) {
  // line has been trimmed of CR/LF before reaching here
  if (line == "HB") {
    extern void watchdog_note_hb();
    watchdog_note_hb();
    return;
  }
  if (line == "STAT?") {
    status_emit_once();
    return;
  }
  if (line == "VERBOSE,ON") { status_set_verbose(true); return; }
  if (line == "VERBOSE,OFF") { status_set_verbose(false); return; }
  if (line.startsWith("SERVO,")) {
    int comma = line.indexOf(',');
    int deg = line.substring(comma + 1).toInt();
    if (deg < 0) deg = 0; if (deg > 180) deg = 180;
    servo_set_target_deg(deg);
    return;
  }
  if (line == "PING") {
    if (servo_is_settled()) {
      float cm = ultrasonic_measure_cm();
      if (isnan(cm)) Serial.println("DIST,NA");
      else { Serial.print("DIST,"); Serial.println(cm, 1); }
    } else {
      Serial.println("DIST,NA");
    }
    return;
  }
  if (line == "STOP") { motion_set_mode(MODE_STOP); return; }
  if (line == "SPINL") { watchdog_note_hb(); motion_set_mode(MODE_SPIN_LEFT); return; }
  if (line == "SPINR") { watchdog_note_hb(); motion_set_mode(MODE_SPIN_RIGHT); return; }
  if (line == "F,FAST") { watchdog_note_hb(); motion_set_mode(MODE_FORWARD_FAST); return; }
  if (line == "F,SLOW") { watchdog_note_hb(); motion_set_mode(MODE_FORWARD_SLOW); return; }
  if (line == "B,SLOW") { watchdog_note_hb(); motion_set_mode(MODE_BACK_SLOW); return; }
  if (line == "L,SLOW") { watchdog_note_hb(); motion_set_mode(MODE_ARC_LEFT); return; }
  if (line == "R,SLOW") { watchdog_note_hb(); motion_set_mode(MODE_ARC_RIGHT); return; }
}

void serial_proto_init() {
  g_line.reserve(64);
}

void serial_proto_tick() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (g_line.length() > 0) {
        // Trim any stray CR that may have been appended (e.g., \r\n terminals)
        while (g_line.length() > 0) {
          char last = g_line.charAt(g_line.length() - 1);
          if (last == '\r' || last == '\n') g_line.remove(g_line.length() - 1); else break;
        }
        handle_command(g_line);
        g_line = "";
      }
    } else {
      if (g_line.length() < 63) g_line += c;
    }
  }
}
