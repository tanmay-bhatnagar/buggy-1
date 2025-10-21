# Phase 1 – Locomotion (Jetson Buggy)

## 1) Overview of Phase 1

**Goal:** reliable obstacle‑aware locomotion with two speed tiers (FAST/SLOW) using an ultrasonic sensor on a pan servo. Intelligence and fancier behaviors are Phase 2.

**Runtime storyboard:**

1. Boot Jetson (keyboard/mouse connected).
2. Launch the locomotion app (`move-buggy`), which opens a Bluetooth pairing countdown (N seconds).
3. After the countdown (or an explicit GO), the robot begins autonomous motion.
4. Control loop: sweep servo → collect distances → choose action (cruise/arc/spin/backoff/stop) → send a single motion command to Arduino → log telemetry.

**Control policy (high‑level, no code):**

- **Speed tiering:** drop to SLOW when center distance is below a threshold; return to FAST when it clears a higher threshold (hysteresis pair to avoid flip‑flop).
- **Turn vs arc:** if ahead is tight but not panic, do a gentle **ARC** toward the side with more space; if boxed or after a backoff, do an in‑place **SPIN**.
- **Backoff:** on very short range, STOP → reverse briefly → choose wider side.
- **Spin bursts:** for Phase‑1, spins run in short bursts with small commit time, then re‑scan and continue only if still needed (semi‑closed loop using the ultrasonic, no IMU required).
- **Failsafes:** heartbeat watchdog (Jetson↔Arduino), E‑stop, lost‑sensor recovery (drop to SLOW, sweep until valid readings return).

---

## 2) Inventory & Hardware Notes

### 2.1 Parts on hand

- **Compute:** Jetson Orin Nano (head unit).
- **MCU:** Arduino **UNO R4 WiFi** (Renesas RA4M1).
- **Motor driver:** L293D **HW‑130** style shield (stacked on UNO).
- **Drive:** 4 × B.O. geared DC motors + 4 wheels; MDF chassis with wooden motor braces.
- **Sensoring:** 1 × ultrasonic range sensor on a pan **servo** (continuous small sweeps).
- **Power:** Jetson via USB‑C PD power bank; motors via separate battery pack; UNO linked to Jetson over USB for data (and optionally 5 V power, depending on wiring).
- **Final motor mapping & polarity:**
  - M1 = Front‑Left, M2 = Rear‑Left, M3 = Rear‑Right, M4 = Front‑Right.
  - **REV mask:** `{false, true, false, true}` (True = reversed; applies M1..M4 in order).

### 2.2 L293D shield + 74HC595 (global OE, no per‑wheel PWM)

- Direction lines are driven through a **74HC595** (Q0..Q7). The register’s **OE is on D7** and is **active‑LOW**; we drive global speed via PWM on OE (duty is inverted: `analogWrite(255 − pwm)`).
- There is no per‑wheel or per‑side EN available in this build; all motors share the single OE line.
- **ARC** is implemented by keeping OE at the chosen tier and briefly pulsing the inner‑side motor bits OFF using `SLOW_PULSE_ON_MS` / `SLOW_PULSE_OFF_MS` (fake a slower track without side EN).
- Upshot for Phase‑1: we run **two speed tiers** (FAST/SLOW) globally and shape arcs via bit‑pulsing; this is sufficient for stable avoidance.

### 2.3 I²C / IMU pin budget (for later)

- **SDA/SCL are available on the UNO under the shield as A4 (SDA) / A5 (SCL).** The shield passes them through; wiring an IMU later uses **A4=Ada/SDA, A5=SCL**, plus **3.3 V** and **GND**.
- Optional **INT** pin from the IMU can land on any free digital pin; not required for Phase‑1.

---

## 3) Code & Folder Structure (top level)

```
buggy/
├─ Phase1README (this file)
├─ jetson/                # Python app (brain)
└─ arduino/               # UNO R4 + L293D firmware (muscle)
```

---

## 3.1 Jetson Code Details (Python “brain”)

**Purpose:** run the state machine, orchestrate servo sweeps + pings, decide actions, send one clear command per loop, and log telemetry.

**Layout:**

```
jetson/
├─ app/
│  ├─ main.py            # entrypoint: run loop + state machine
│  ├─ controller.py      # policy: CRUISE / ARC / SPIN / BACKOFF / RECOVERY / ESTOP
│  ├─ sensing.py         # servo scan plan + ping orchestration (K samples → median)
│  ├─ serial_link.py     # robust ASCII protocol (send/recv, timeouts, retries)
│  ├─ telemetry.py       # CSV logger + console HUD
│  ├─ watchdog.py        # Jetson-side timers, E-stop key handler
│  ├─ config.py          # loads YAML/JSON configs + CLI overrides
│  └─ utils.py           # helpers (median, clamp, timers)
├─ config/
│  ├─ default.yaml       # thresholds, timers, ports, sweep geometry
│  └─ profiles/          # alt profiles (tile, carpet, outdoors)
├─ scripts/
│  ├─ start.sh           # env setup + launch convenience
│  └─ diagnose_serial.py # link check & latency test
└─ systemd/
   └─ buggy.service      # optional: auto-start after boot delay
```

**States (no code, just responsibilities):**

- **IDLE:** pairing countdown; motors off; heartbeats active.
- **CRUISE:** forward FAST/SLOW; hysteresis on center distance.
- **AVOID\_ARC:** gentle arc to wider side; minimum commit time per entry.
- **AVOID\_SPIN:** burst spin with small commit → settle → quick re‑scan → repeat if needed.
- **BACKOFF:** timed reverse; then decide ARC/SPIN/CRUISE.
- **SENSOR\_RECOVERY:** when repeated invalid pings—crawl + mini sweeps until stable.
- **ESTOP / WATCHDOG\_STOP:** latched STOP until explicit clear/heartbeat returns.

**Serial protocol (ASCII, one per line):**

- **To Arduino (commands):** `F,FAST` | `F,SLOW` | `B,SLOW` | `L,SLOW` | `R,SLOW` | `SPINL` | `SPINR` | `STOP` | `SERVO,<deg>` | `PING` | `HB`
- **From Arduino (replies):** `DIST,<cm>` | `DIST,NA` | `STAT,<mode>,<pwmL>,<pwmR>,<last_cm>` | optional `OK`/`ERR,<code>`

**Policy knobs (configured, not hard‑coded):**

- Distance thresholds with hysteresis: **SLOW**, **TURN**, **STOP** pairs.
- Timers: **BACKOFF\_MS**, **MIN\_TURN\_MS**, **RESCAN\_MS**, **STALL\_TIMER\_MS**, **MEAS\_COOLDOWN\_MS**, **SERVO\_SETTLE\_MS**.
- Sweep geometry: **left/right limits**, **step degrees**, **center trim**, **samples per point**.

**Telemetry:** per‑loop CSV row: `t,state,speed,dist_center,dist_left,dist_right,decision,servo_deg,cmd,latency_ms`.

---

## 3.2 Arduino Code Details (UNO R4 + L293D “muscle”)

**Purpose:** execute motion primitives idempotently, manage servo + ultrasonic safely (non‑blocking), enforce watchdog, and provide stable distance readings.

**Sketch structure (fully modular):**

```
arduino/
├─ src/
│  ├─ BuggyPhase1.ino          # setup()/loop(); module init + fixed tick order
│  ├─ pins.h                   # 74HC595 Q-map + global OE, servo D10, trig A0/echo A1; REV mask
│  ├─ config.h                 # PWM tiers, timings, ranges, baud, hysteresis constants
│  ├─ motion.h / motion.cpp    # modes: F_FAST/F_SLOW, ARC_L/R, SPIN_L/R, BACKOFF, STOP
│  ├─ servo_scan.h / .cpp      # commandable servo position + settle window
│  ├─ ultrasonic.h / .cpp      # non-blocking ping, median-of-K, validity clamp
│  ├─ serial_proto.h / .cpp    # line parsing, command dispatch, acks/errors
│  ├─ watchdog.h / .cpp        # heartbeat timeout → force STOP (optional latch)
│  └─ status.h / .cpp          # periodic STAT output, last distance cache
└─ platformio.ini (or use Arduino IDE tabs)
```

**Main loop (non‑blocking tick order):**

1. `serial_proto.tick()` – read line, update desired motion, handle sensor requests.
2. `watchdog.tick()` – if heartbeat stale → force STOP.
3. `servo_scan.tick()` – move toward target; honor settle time.
4. `ultrasonic.tick()` – trigger/measure with cooldown; update `last_dist`.
5. `motion.tick()` – enforce current mode idempotently; handle timed phases (BACKOFF, min‑turn commit).
6. `status.tick()` – emit `STAT,...` periodically or on change.

**Motion modes:** persistent set‑states (`F_FAST`, `F_SLOW`, `ARC_L`, `ARC_R`, `SPIN_L`, `SPIN_R`, `STOP`) plus timed phases (`BACKOFF`, `TURN_COMMIT`).

**Shield considerations:**

- EN pins hard‑HIGH ⇒ per‑wheel PWM not available; prefer **side‑level PWM** if exposed or use coarse pulsing for SLOW.
- Keep motion timing independent from servo/ultrasonic timing; use `millis()` timers, no long `delay()`.

**Ultrasonic discipline:** median of K pings at each angle; cooldown between pings; range clamp; ping only after servo settle.

**Watchdog:** if no `HB` for a configured timeout, force `STOP`. Optionally require a fresh `HB` or explicit clear before resuming.

---

### Appendix: Interface contract (concise)

- **Idempotent commands:** repeating the same motion command should not add side effects (no stutter, no toggles). Jetson may resend current mode periodically.
- **One command per loop:** Jetson decides and sends exactly one motion action each cycle; Arduino executes and keeps it until changed or safety overrides.
- **Spin strategy (Phase‑1):** short spin burst → settle → quick re‑scan; repeat as needed until forward is clear.

### Appendix: Quick test plan (Phase‑1)

- **Static wall:** verify SLOW/TURN/STOP thresholds by measured distances.
- **Doorway offset:** confirm ARC to the open side (no unnecessary spins).
- **Box canyon:** ensure BACKOFF → SPIN selects wider exit consistently.
- **Sensor kill:** cover ultrasonic; verify recovery behavior.

### Appendix: Future‑proofing hooks

- IMU over I²C (A4/A5) with optional INT; yaw‑based “turn‑to‑heading” later.
- Live tuning via config updates; log replay for offline analysis.



---

## 4) Tuning Defaults (Phase‑1 starting profile)

> These are **starting** values. You’ll likely move thresholds by ±5–15 cm and timers by ±100–200 ms after your first logs.

### 4.1 Distance thresholds (with hysteresis)

| Purpose          | Enter at (cm) | Exit/Clear at (cm) | Notes                                                  |
| ---------------- | ------------- | ------------------ | ------------------------------------------------------ |
| **SLOW tier**    | 60            | 75                 | Drop to SLOW when center <60; return to FAST when >75. |
| **TURN (arc)**   | 35            | 45                 | Leave CRUISE for ARC when <35; return when >45.        |
| **STOP/backoff** | 20            | 30                 | Immediate STOP + BACKOFF when <20; resume when >30.    |

**Range clamp:** ignore readings < **3 cm** or > **300 cm**.

### 4.2 Timing & cadence

| Parameter              | Default | Why                                             |
| ---------------------- | ------- | ----------------------------------------------- |
| **RESCAN\_MS**         | 200 ms  | Cruise loop cadence (scan → decide).            |
| **MIN\_TURN\_MS**      | 550 ms  | Commit time for ARC/SPIN to prevent thrash.     |
| **BACKOFF\_MS**        | 500 ms  | Short reverse to create space before re‑aiming. |
| **STALL\_TIMER\_MS**   | 2500 ms | If scene doesn’t improve, inject backoff+spin.  |
| **MEAS\_COOLDOWN\_MS** | 40 ms   | Reduce ultrasonic echo contamination.           |
| **SERVO\_SETTLE\_MS**  | 100 ms  | Let the horn settle before pinging.             |

### 4.3 Sweep geometry & sampling

| Parameter               | Default | Notes                                          |
| ----------------------- | ------- | ---------------------------------------------- |
| **SWEEP\_LEFT**         | 135°    | Left extent from 0–180° scale.                 |
| **SWEEP\_RIGHT**        | 45°     | Right extent from 0–180° scale.                |
| **STEP\_DEG**           | 15°     | Coarse fan: center then a few steps each side. |
| **CENTER\_TRIM**        | 0°      | Use ±3–5° if your mount is biased.             |
| **SAMPLES\_PER\_POINT** | 3       | Median filter at each pose.                    |

### 4.4 Drive tiers (shield‑friendly)

| Parameter     | Default         | Notes                                        |
| ------------- | --------------- | -------------------------------------------- |
| **PWM\_FAST** | 230/255 (\~90%) | If shield exposes side PWM.                  |
| **PWM\_SLOW** | 150/255 (\~60%) | If no PWM, emulate SLOW with coarse pulsing. |
| **RAMP\_MS**  | 200 ms          | Gentle transitions between tiers.            |

### 4.5 Watchdog & health

| Parameter                       | Default | Notes                           |
| ------------------------------- | ------- | ------------------------------- |
| **HB\_PERIOD\_MS (Jetson→UNO)** | 200 ms  | Heartbeat cadence.              |
| **HB\_TIMEOUT\_MS (UNO)**       | 600 ms  | If missed >600 ms → force STOP. |

### 4.6 Logging (Jetson)

CSV per loop: `t,state,speed,dist_center,dist_left,dist_right,decision,servo_deg,cmd,latency_ms`.

### 4.7 Starter profiles (suggested)

| Profile               | Slow/Turn/Stop (enter) | Clear values    | Notes                                                |
| --------------------- | ---------------------- | --------------- | ---------------------------------------------------- |
| **Indoor – tile**     | 60 / 35 / 20 cm        | 75 / 45 / 30 cm | Baseline above.                                      |
| **Indoor – carpet**   | 65 / 40 / 22 cm        | 80 / 50 / 32 cm | Slightly more conservative (draggy turns).           |
| **Outdoors – smooth** | 55 / 30 / 18 cm        | 70 / 40 / 28 cm | Allows tighter approach; more room around obstacles. |

> Keep all of these in `config/default.yaml` so they’re easy to tweak without touching logic. After the first drive, adjust the **TURN** pair first (feel), then **SLOW** (comfort), then **STOP** (safety).



---

## 5) How to Test & Iterate (quick drills)

**Objective:** validate thresholds and timing with short, controlled runs. Capture logs; tune, rerun.

### 5.1 Pre‑flight

- Wheels off ground → issue each motion command once (F\_FAST/SLOW, ARC\_L/R, SPIN\_L/R, B\_SLOW, STOP). Verify directions match the **REV** mask and that resending the same command is smooth (idempotent).
- Servo center/edges sanity: center \~90°, limits at SWEEP\_RIGHT/LEFT, no buzzing at endpoints.
- Ultrasonic sanity at a known distance (e.g., \~50 cm). Confirm median agrees ±3–5 cm.

### 5.2 Drills

1. **Static wall approach** (start 1.5–2 m from a wall)

   - Expect: FAST → SLOW near **60 cm**, ARC or straight depending on left/right space, STOP near **20 cm** if forced.
   - Log tells you if thresholds are too chatty (flip‑flop) or too timid.

2. **Offset doorway** (open doorway on one side)

   - Expect: ARC toward the open side without unnecessary SPINs.
   - If it spins often, increase **TURN\_DIST** or **MIN\_TURN\_MS** slightly.

3. **Box canyon** (two chairs making a U)

   - Expect: STOP → BACKOFF → SPIN toward wider side → CRUISE.
   - If it pinballs, raise **BACKOFF\_MS** and/or turn commit; consider widening sweep.

4. **Narrow corridor** (hallway or taped lane)

   - Expect: mostly CRUISE with occasional ARC; minimal STOPs.
   - If it oscillates, increase **MIN\_TURN\_MS** or reduce **STEP\_DEG** jitter by adding one more angle per side.

5. **Sensor drop test** (hand over ultrasonic briefly)

   - Expect: SENSOR\_RECOVERY state: SLOW + mini‑sweeps until valid, then resume.
   - If it continues blind, shorten **MEAS\_COOLDOWN\_MS** or add more samples per point.

### 5.3 Log reading cheatsheet

- Look for clusters where `dist_center` hovers near thresholds. If rapid state flips occur within <1 s, widen hysteresis gaps (e.g., SLOW 60→75, TURN 35→45).
- If **STOP** triggers at distances > expected, check **SERVO\_SETTLE\_MS** and add a short settle before each center ping.
- If **STALL\_TIMER** fires in open space, your sweep cadence is too slow (reduce **RESCAN\_MS** or **MEAS\_COOLDOWN\_MS** slightly).

### 5.4 Tuning order (fast convergence)

1. **TURN pair** (feel): adjust TURN\_DIST/CLEAR until arcs feel natural and avoid premature spins.
2. **SLOW pair** (comfort): minimize jerky tier swaps; prefer stability over maximal speed indoors.
3. **STOP pair** (safety): tighten only after you trust the above; confirm with the wall test.
4. **Commit timers**: tweak **MIN\_TURN\_MS** and **BACKOFF\_MS** to remove dithering.
5. **Sweep shape**: last mile—STEP\_DEG and angle count for your room geometry.

### 5.5 Regression checklist (before calling Phase‑1 done)

- Zero runaway: ESTOP and watchdog STOP always halt within <200 ms.
- No servo buzz at endpoints; ultrasonic stable (<±5 cm stdev at 50 cm target).
- Five‑minute mixed course shows <5% time in STOP except in deliberate box canyons.
- Logs free of sustained flip‑flops around any single threshold.

