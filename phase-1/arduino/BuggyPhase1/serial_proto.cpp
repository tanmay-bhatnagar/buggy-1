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
  // Compact parser with legacy aliases. line is trimmed of CR/LF.
  if (line.length() == 0) return;

  // Legacy aliases to compact forms
  if (line.startsWith("SERVO,")) {
    int comma = line.indexOf(',');
    String deg = line.substring(comma + 1);
    handle_command(String("P") + deg);
    return;
  }
  // PING must reply with a single DIST line for Jetson runtime
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
  if (line == "STOP") { handle_command("S"); return; }
  if (line == "SPINL") { handle_command("L"); return; }
  if (line == "SPINR") { handle_command("R"); return; }
  if (line == "F,FAST") { handle_command("F230"); return; }
  if (line == "F,SLOW") { handle_command("F150"); return; }

  // Control of verbosity and quick status
  if (line == "STAT?") { status_emit_once(); return; }
  if (line == "VERBOSE,ON") { status_set_verbose(true); return; }
  if (line == "VERBOSE,OFF") { status_set_verbose(false); return; }
  if (line == "H") { Serial.println("CMD: F/B/L/R<n>, S, P<deg>, T<n>, Q, H"); return; }

  char c = line.charAt(0);
  String arg = line.substring(1);
  arg.trim();

  auto parseIntSafe = [&](const String& s, int def)->int{
    if (s.length() == 0) return def;
    return s.toInt();
  };

  switch (c) {
    case 'H': Serial.println("CMD: F/B/L/R<n>, S, P<deg>, T<n>, Q, H"); return;
    case 'Q':
      // One-shot STAT and ULS
      printStat();
      printULS();
      return;
    case 'S':
      motion_set_mode(MODE_STOP);
      motion_pwm_speed(0);
      return;
    case 'P': {
      int deg = constrain(parseIntSafe(arg, 90), 0, 180);
      servo_stopSweep();
      servo_set_target_deg(deg);
      return; }
    case 'T': {
      int cm = max(0, parseIntSafe(arg, 0));
      setSafetyThresholdCM((uint16_t)cm);
      return; }
    case 'F': {
      int spd = constrain(parseIntSafe(arg, DEFAULT_BENCH_PWM), 0, 255);
      motion_pwm_speed(spd);
      motion_set_mode(MODE_FORWARD_FAST); // treat as forward; speed via override
      return; }
    case 'B': {
      int spd = constrain(parseIntSafe(arg, DEFAULT_BENCH_PWM), 0, 255);
      motion_pwm_speed(spd);
      motion_set_mode(MODE_BACK_SLOW);
      return; }
    case 'L': {
      int spd = constrain(parseIntSafe(arg, DEFAULT_BENCH_PWM), 0, 255);
      motion_pwm_speed(spd);
      motion_set_mode(MODE_SPIN_LEFT);
      return; }
    case 'R': {
      int spd = constrain(parseIntSafe(arg, DEFAULT_BENCH_PWM), 0, 255);
      motion_pwm_speed(spd);
      motion_set_mode(MODE_SPIN_RIGHT);
      return; }
  }
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
        // Trim surrounding whitespace
        g_line.trim();
        handle_command(g_line);
        g_line = "";
      }
    } else {
      if (g_line.length() < 63) g_line += c;
    }
  }
}
