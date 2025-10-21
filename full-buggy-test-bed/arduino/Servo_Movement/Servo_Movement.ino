// 1_3.ino — Movement + Servo(auto-sweep on move) + Ultrasonic (prints only on command)
// Board: Arduino UNO R4 WiFi
// Serial: 115200
//
// Commands (ASCII):
//   F<spd> / B<spd> / L<spd> / R<spd> / S      (0..255)
//   p<angle>                                   (0..180) — direct set (optional)
//   t<cm>                                      obstacle threshold (1..399)
//   q                                          status snapshot (includes one ultrasonic read)
//
// Telemetry (minimal by design):
//   new code
//   STATUS ready
//   SRV deg=<angle>      (on p<angle> and at boot; servo sweep doesn’t spam)
//   ULS cm=<val>         (only when a command executes or a stop event occurs)
//   DRV mode=<...> spd=<...>  (on drive commands)
//   EVT stop=obstacle|deadman|command
//
// Behavior highlights:
// - Ultrasonic sampling runs at ~10 Hz for safety, but prints only on command or stop.
// - Any non-zero movement (F/B/L/R) starts a servo sweep. Stop/auto-stop halts and detaches.
// - Robust serial parser: accepts CR, LF, or CRLF; case-insensitive command letters; echoes CMD.

#include <Arduino.h>
#include <Servo.h>

// ---- Pins (legacy) ----
const uint8_t SR_DATA  = 8;    // 74HC595 SER
const uint8_t SR_LATCH = 12;   // 74HC595 RCLK
const uint8_t SR_CLK   = 4;    // 74HC595 SRCLK
const uint8_t SR_OE    = 7;    // 74HC595 OE (active LOW)
const uint8_t US_TRIG  = A0;
const uint8_t US_ECHO  = A1;
const uint8_t SERVO_PIN = 10;  // legacy servo header D10

// ---- Timing knobs ----
const unsigned long ULS_PERIOD_MS     = 100;   // sampling cadence (no printing)
const unsigned long DEADMAN_MS        = 1000;  // auto-stop if no cmd
const unsigned long RAMP_MS           = 180;   // speed ramp time
const uint16_t      PWM_PERIOD_US     = 2000;  // ~500 Hz OE gating

volatile int stop_threshold_cm = 25;

// ---- 74HC595 → L293D mapping (from legacy testbench) ----
#define M1_A_BIT 2
#define M1_B_BIT 3
#define M2_A_BIT 1
#define M2_B_BIT 4
#define M3_A_BIT 5
#define M3_B_BIT 7
#define M4_A_BIT 0
#define M4_B_BIT 6

// Per-motor polarity (true = flip FWD/REV for that motor)
// Legacy: M1..M4 ≡ (FL, RL, RR, FR)
const bool REV_M1 = false;
const bool REV_M2 = true;
const bool REV_M3 = false;
const bool REV_M4 = true;

#define BIT_(b) (uint8_t(1U<<(b)))

const uint8_t M1_FWD = REV_M1 ? BIT_(M1_B_BIT) : BIT_(M1_A_BIT);
const uint8_t M1_REV = REV_M1 ? BIT_(M1_A_BIT) : BIT_(M1_B_BIT);
const uint8_t M2_FWD = REV_M2 ? BIT_(M2_B_BIT) : BIT_(M2_A_BIT);
const uint8_t M2_REV = REV_M2 ? BIT_(M2_A_BIT) : BIT_(M2_B_BIT);
const uint8_t M3_FWD = REV_M3 ? BIT_(M3_B_BIT) : BIT_(M3_A_BIT);
const uint8_t M3_REV = REV_M3 ? BIT_(M3_A_BIT) : BIT_(M3_B_BIT);
const uint8_t M4_FWD = REV_M4 ? BIT_(M4_B_BIT) : BIT_(M4_A_BIT);
const uint8_t M4_REV = REV_M4 ? BIT_(M4_A_BIT) : BIT_(M4_B_BIT);

const uint8_t MASK_FWD   = (M1_FWD | M2_FWD | M3_FWD | M4_FWD);
const uint8_t MASK_REV   = (M1_REV | M2_REV | M3_REV | M4_REV);
const uint8_t MASK_LEFT  = (M1_REV | M2_REV | M3_FWD | M4_FWD);
const uint8_t MASK_RIGHT = (M1_FWD | M2_FWD | M3_REV | M4_REV);
const uint8_t MASK_STOP  = 0x00;

// ---- Globals ----
Servo srv;

enum Mode : uint8_t { M_STOP, M_FWD, M_REV, M_LEFT, M_RIGHT };
volatile Mode drive_mode = M_STOP;

volatile uint8_t sr_pattern = MASK_STOP;
volatile int target_speed = 0;      // 0..255
volatile int current_speed = 0;     // 0..255

unsigned long t_last_cmd   = 0;
unsigned long t_last_uls   = 0;
unsigned long t_ramp_start = 0;
unsigned long pwm_t0       = 0;

// --- Servo sweep state (auto during movement) ---
const int SERVO_MIN = 30, SERVO_MAX = 150, SERVO_STEP = 2;
const unsigned long SERVO_TICK_MS = 20;
bool servoAttached = false, sweepEnabled = false;
int  servoAngle = (SERVO_MIN + SERVO_MAX)/2, servoDir = +1;
unsigned long nextServoTick = 0;

// ---- 595 helpers ----
static inline void srWrite(uint8_t v) {
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLK, MSBFIRST, v);
  digitalWrite(SR_LATCH, HIGH);
}
static inline void motors_idle_safe() {
  digitalWrite(SR_OE, HIGH);
  srWrite(MASK_STOP);
  sr_pattern = MASK_STOP;
}
static inline void set_drive_pattern(Mode m) {
  uint8_t pat = MASK_STOP;
  switch (m) {
    case M_FWD:  pat = MASK_FWD;  break;
    case M_REV:  pat = MASK_REV;  break;
    case M_LEFT: pat = MASK_LEFT; break;
    case M_RIGHT:pat = MASK_RIGHT;break;
    default:     pat = MASK_STOP; break;
  }
  sr_pattern = pat;
  srWrite(pat);
}

// ---- PWM + ramp ----
static inline void pwm_service() {
  const unsigned long now = micros();
  const unsigned long dt = now - pwm_t0;
  if (dt >= PWM_PERIOD_US) pwm_t0 = now;
  unsigned long on_us = (unsigned long)current_speed * PWM_PERIOD_US / 255;
  digitalWrite(SR_OE, (dt < on_us) ? LOW : HIGH);  // LOW=enabled
}
static inline void ramp_service() {
  if (current_speed == target_speed) return;
  unsigned long now = millis();
  if (t_ramp_start == 0) t_ramp_start = now;
  long elapsed = (long)(now - t_ramp_start);
  if (elapsed >= (long)RAMP_MS) { current_speed = target_speed; return; }
  long delta = (long)target_speed - (long)current_speed;
  int step = max(1, (int)(abs(delta) * 10L / (long)RAMP_MS));
  current_speed += (delta > 0 ? +step : -step);
  if ((delta > 0 && current_speed > target_speed) ||
      (delta < 0 && current_speed < target_speed)) current_speed = target_speed;
}

// ---- Ultrasonic ----
static inline long uls_ping_us() {
  digitalWrite(US_TRIG, LOW); delayMicroseconds(2);
  digitalWrite(US_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(US_TRIG, LOW);
  return pulseIn(US_ECHO, HIGH, 30000UL);
}
static inline float us_to_cm(long us) { return (us > 0) ? (us / 58.0f) : -1.0f; }
static inline long uls_read_and_print_once(const __FlashStringHelper* tag) {
  long us = uls_ping_us();
  if (us == 0) { Serial.println(F("ULS timeout")); return -1; }
  float cm = us_to_cm(us);
  Serial.print(F("ULS cm=")); Serial.println(cm,1);
  if (tag) { (void)tag; }
  return (long)cm;
}

// ---- Servo helpers ----
static inline void servo_attach_if() {
  if (!servoAttached) { srv.attach(SERVO_PIN); servoAttached = true; }
}
static inline void servo_detach_if() {
  if (servoAttached) { srv.detach(); servoAttached = false; }
}
static inline void servo_set(int deg) {
  servo_attach_if();
  if (deg < 0) deg = 0; if (deg > 180) deg = 180;
  srv.write(deg);
  Serial.print(F("SRV deg=")); Serial.println(deg);
}
static inline void servo_start_sweep() {
  sweepEnabled = true;
  servo_attach_if();
  nextServoTick = millis() + SERVO_TICK_MS;
}
static inline void servo_stop_sweep() {
  sweepEnabled = false;
  servo_detach_if();
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
}
static inline void servo_tick() {
  if (!sweepEnabled || millis() < nextServoTick) return;
  servoAngle += servoDir * SERVO_STEP;
  if (servoAngle >= SERVO_MAX) { servoAngle = SERVO_MAX; servoDir = -1; }
  if (servoAngle <= SERVO_MIN) { servoAngle = SERVO_MIN; servoDir = +1; }
  srv.write(servoAngle);
  nextServoTick = millis() + SERVO_TICK_MS;
}

// ---- Drive control ----
static inline void drive(Mode m, int spd, bool print_ultra_after=true) {
  if (spd < 0) spd = 0; if (spd > 255) spd = 255;

  if (m != drive_mode) {
    digitalWrite(SR_OE, HIGH);
    srWrite(MASK_STOP);
    delay(20);
    set_drive_pattern(m);
    drive_mode = m;
  }

  target_speed = spd; t_ramp_start = 0;

  // Servo rule: sweep when moving, stop when not
  if (drive_mode != M_STOP && spd > 0) servo_start_sweep();
  else                                  servo_stop_sweep();

  Serial.print(F("DRV mode="));
  Serial.print(m==M_FWD?'F':m==M_REV?'B':m==M_LEFT?'L':m==M_RIGHT?'R':'S');
  Serial.print(F(" spd=")); Serial.println(target_speed);

  if (print_ultra_after) uls_read_and_print_once(F("cmd"));
}

static inline void drive_stop(const __FlashStringHelper* reason, bool print_ultra_after=true) {
  target_speed = 0; current_speed = 0;
  digitalWrite(SR_OE, HIGH);
  set_drive_pattern(M_STOP);
  drive_mode = M_STOP;
  servo_stop_sweep();
  Serial.print(F("EVT stop=")); Serial.println(reason);
  if (print_ultra_after) uls_read_and_print_once(F("stop"));
}

// ---- Command parser ----
String inbuf;

static inline void handle_line(String ln) {
  ln.trim();
  if (!ln.length()) return;

  // Echo what we got (useful on Jetson terminals)
  Serial.print(F("CMD=")); Serial.println(ln);

  char c = ln.charAt(0);
  if (c >= 'a' && c <= 'z') c = c - 'a' + 'A';
  String arg = ln.substring(1);
  arg.trim();

  t_last_cmd = millis();

  if (c=='F'||c=='B'||c=='L'||c=='R') {
    int spd = arg.toInt();
    drive(c=='F'?M_FWD:c=='B'?M_REV:c=='L'?M_LEFT:M_RIGHT, spd, true);
    return;
  }
  if (c=='S') { drive_stop(F("command"), true); return; }

  if (c=='P') {                 // direct servo set (optional)
    int ang = arg.toInt();
    servo_set(ang);
    uls_read_and_print_once(F("cmd"));
    return;
  }

  if (c=='T') {                 // threshold
    int cm = arg.toInt();
    if (cm > 0 && cm < 400) {
      stop_threshold_cm = cm;
      Serial.print(F("CFG stop_threshold_cm=")); Serial.println(stop_threshold_cm);
    }
    uls_read_and_print_once(F("cmd"));
    return;
  }

  if (c=='Q') {                 // snapshot
    Serial.print(F("STAT mode="));
    Serial.print(drive_mode==M_FWD?'F':drive_mode==M_REV?'B':drive_mode==M_LEFT?'L':drive_mode==M_RIGHT?'R':'S');
    Serial.print(F(" spd=")); Serial.print(current_speed);
    Serial.print(F(" thresh=")); Serial.println(stop_threshold_cm);
    uls_read_and_print_once(F("cmd"));
    return;
  }

  Serial.println(F("ERROR BAD_CMD"));
}

// ---- Setup/Loop ----
void setup() {
  Serial.begin(115200); delay(80);
  Serial.println(F("new code"));
  Serial.println(F("STATUS ready"));

  pinMode(SR_DATA,OUTPUT); pinMode(SR_LATCH,OUTPUT); pinMode(SR_CLK,OUTPUT); pinMode(SR_OE,OUTPUT);
  digitalWrite(SR_CLK,LOW); motors_idle_safe();

  pinMode(US_TRIG,OUTPUT); pinMode(US_ECHO,INPUT);

  // Park servo at neutral (reported once); sweep starts only on movement
  servo_set(90);

  t_last_cmd = millis(); pwm_t0 = micros();
}

void loop() {
  // Robust line reader: end on LF or CR; tolerate CRLF; guard length
  while (Serial.available()) {
    char ch = (char)Serial.read();

    if (ch == '\n' || ch == '\r') {
      if (inbuf.length()) { handle_line(inbuf); inbuf = ""; }
      continue;
    }
    if ((uint8_t)ch < 0x20) continue; // skip other control chars

    inbuf += ch;
    if (inbuf.length() > 120) inbuf = "";  // safety reset
  }

  unsigned long now = millis();

  // Dead-man
  if (drive_mode!=M_STOP && (now - t_last_cmd) > DEADMAN_MS) drive_stop(F("deadman"), true);

  // Periodic ultrasonic sampling (NO printing) for safety stop
  if ((now - t_last_uls) >= ULS_PERIOD_MS) {
    t_last_uls = now;
    long us = uls_ping_us();
    if (us != 0) {
      float cm = us_to_cm(us);
      if (drive_mode != M_STOP && cm > 0 && cm <= stop_threshold_cm) {
        drive_stop(F("obstacle"), true);
      }
    }
  }

  // Servo sweep tick (only when moving)
  servo_tick();

  // Speed ramp & OE PWM
  ramp_service();
  if (drive_mode==M_STOP || current_speed==0) digitalWrite(SR_OE, HIGH);
  else pwm_service();
}
