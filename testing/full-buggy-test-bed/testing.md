# Testbed v1 — Hardware + Test Scripts (1.2, 1.3)

## 1) Purpose & Scope
- This repo, as of now, is for bring-up and testing of **motors (L293D + 74HC595)**, **ultrasonic sensor**, and **servo** via serial.
- In scope: **Servo + Utrasonic Test**, **Servo+Ultrasonic+Movement Test**; hardware setup; how to flash; commands; expected outputs; pass/fail gates.
- Out of scope: autonomy logic (handled in the next phase/document).

---

## 2) Hardware Essentials

**Board**: Arduino **UNO R4 WiFi** — FQBN `arduino:renesas_uno:unor4wifi`; Serial **115200 baud**.

**Motor shield**: L293D v1-style using **74HC595** shift register.

| Function                    | Arduino Pin | Notes |
|---                          |---          |---|
| 74HC595 **SER**             | D8          | Data in |
| 74HC595 **LATCH** (RCLK)    | D12         | Latch |
| 74HC595 **CLK** (SRCLK)     | D4          | Shift clock |
| 74HC595 **OE**              | D7          | **Active-LOW**, PWM for speed (duty = `255 - speed`) |
| **Ultrasonic TRIG**         | A0          | HC-SR04 |
| **Ultrasonic ECHO**         | A1          | HC-SR04 |
| **Servo signal**            | D10         | Detach at idle to avoid jitter |

**Motor bit mapping (74HC595 Q lines → L293D A/B):**

- **M1**: A=Q2, B=Q3  
- **M2**: A=Q1, B=Q4  
- **M3**: A=Q5, B=Q7  
- **M4**: A=Q0, B=Q6

**Polarity flip map** (`REV[]` for M1..M4 = FL, RL, RR, FR):  
`{ false, true, false, true }`

**Power/EMI notes**
- Provide a clean 5 V rail to the HC‑SR04 (avoid motor sag).  
- Route TRIG/ECHO away from motor leads; twist pairs if possible.  
- Mount/aim the sensor so it doesn’t “see” the chassis/table at close range.

---

## 3) Tooling
- **Uploader/Monitor:** `upload_to_arduino.py` — compile/upload + **bidirectional** serial monitor.  
  - Useful switches: `--eol CRLF`, auto-port detect, `--dtr-reset`, `--no-upload` (monitor only).
- **Install core:**
  ```bash
  arduino-cli core update-index
  arduino-cli core install arduino:renesas_uno
  ```
- **Flash & monitor (one-liner):**
  ```bash
  python3 upload_to_arduino.py --sketch ./arduino/<TEST_FOLDER>/ --eol CRLF
  ```

---

## 5) Servo + Utrasonic Test
**Goal:** Validate servo attach/detach, angle accuracy, jitter-free idle.

**Sketch path:** `./arduino/ServoTest/`

**Commands:** (per this sketch’s parser)
```
P90
P45
P135
```
**Expected:** servo moves to commanded angles; detaches at idle (no buzz).

**Pass / Fail:** reaches angle; no twitch after detach; prints confirm.

**Pitfalls:** power sag; mechanical interference at min/max travel.

---

## 6) Servo+Ultrasonic+Movement Test
**Goal:** Integrated verification — motors respond; servo sweeps during motion; ultrasonic safety works.

**Sketch path:** `./arduino/Servo_Movement/`

**Compact command dialect:**
```
F<n> / B<n> / L<n> / R<n>   # speed 0–255 (servo auto-sweeps while moving)
S                           # stop
P<deg>                      # servo 0–180, pauses sweep
T<N>                        # safety threshold in cm; T0 disables
Q                           # status + one ultrasonic read
H                           # brief help
```

**Safety semantics:**
- Trips when **3 consecutive samples ≤ N** (≈240 ms at ~12.5 Hz).  
- Timeouts (`-1`) are ignored.

**Telemetry:**
- On boot: `STATUS READY`  
- `STAT mode=<S|F|B|L|R> spd=<0..255> thresh=<cm> last_cm=<cm> sweep=<0|1>`  
- `ULS cm=<cm> angle=<deg|-1> t_ms=<millis>`  
- Stops: `EVT stop=command` (manual `S`) or `EVT stop=safety` (threshold)

**Quick bring-up sequence (copy‑paste):**
```
Q
T0
F160
S
T60
F160
```

**Pass / Fail gates:**
- With `T0`, sustained motion >10 s until `S`.
- With `T60`, stop within ≈240 ms when approaching an obstacle.
- LEFT/RIGHT steering correct (validate `REV[]`).

**Pitfalls:** sensor pointed at chassis/table; noisy 5 V rail; wrong line endings.

---

## 7) Minimal Troubleshooting
- **No output:** ensure `--eol CRLF`; try `--no-upload` + `--dtr-reset`; confirm baud 115200.
- **Instant stop:** `T0` to disable safety; re‑aim sensor; ensure a clean 5 V to HC‑SR04; then re‑enable `T40–T80`.
- **Wrong wheel directions:** adjust `REV[]` mapping and reflash.
- **No motion but prints OK:** check OE on **D7** (PWM gate); remember duty = `255 − speed`.

