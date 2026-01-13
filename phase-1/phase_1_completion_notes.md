# Phase 1 Completion Notes ✅

## Key Achievements

✅ **Autonomous Navigation**: Buggy navigates tight indoor spaces with obstacle avoidance  
✅ **Sensor Integration**: HC-SR04 ultrasonic sensor properly configured and validated  
✅ **Servo Scanning**: Center-focused 5-angle sweep pattern for optimal forward awareness  
✅ **Multiple Profiles**: Three working configs (default, run_free, home) for different environments  
✅ **Safety Systems**: Watchdog, heartbeat, backoff, and sensor recovery all functional  
✅ **Robust Communication**: Jetson-Arduino serial protocol stable and reliable  

## Critical Issues Resolved

### Hardware/Timing Issues:
- **Servo PWM Timer Conflict**: Servo library and motor PWM (pin 7) shared timer on UNO R4 - resolved by using `digitalWrite` instead of `analogWrite` for motor control
- **Servo Detaching**: Runtime mode was detaching servo after settle, preventing continuous scanning - fixed by keeping servo attached
- **Heartbeat Handling**: Arduino interpreted `HB` as `H` (help command) - added explicit `HB` handler

### Control Logic Issues:
- **Backoff Retriggering**: Backoff timer reset every tick while obstacle present, causing excessive reverse - fixed with state check
- **Redundant Servo Commands**: Resending same angle reset settle timer - added duplicate command filtering
- **Sensor Directional Limitation**: HC-SR04's 15° beam missed obstacles during side scans - implemented center-heavy scan pattern

## Final Working Configurations

### **`default.yaml`** - Baseline Indoor Profile
- Balanced speed (PWM 150-230)
- 7-angle interleaved sweep
- Thresholds: 20/35/60 cm (stop/turn/slow)
- 3 samples per angle for reliability

### **`run_free.yaml`** - Open Space Testing
- Ignores obstacles (thresholds at 0)
- 60-second runtime
- Fast scanning (1 sample per angle)
- Used for motor/servo validation

### **`home.yaml`** - Tight Indoor Spaces ⭐
- Ultra-slow speeds (PWM 105-140)
- 5-angle center-focused sweep: `90° → 75° → 90° → 105° → 90°`
- Conservative thresholds: 25/50/80 cm
- Fast reactions (250ms decisions)
- 30-second countdown + 30-second runtime
- Optimized for close-quarters navigation

## Hardware Validation

### Ultrasonic Sensor (HC-SR04):
- ✅ Conversion formula validated: `cm = duration / 58.0`
- ✅ Trigger timing correct: 10μs pulse
- ✅ Range limits optimal: 2-300 cm
- ✅ Cooldown tuned: 40ms between pings
- ⚠️ Beam angle: ~15° (highly directional - requires center-focused scanning)

### Motor Control (L293D + 74HC595) - Cheap HW-130 Clone:
- ✅ Global speed control via OE pin (active-LOW)
- ✅ Direction control via shift register
- ✅ REV mask calibrated: `{false, true, false, true}`
- ⚠️ **No per-wheel PWM (timer conflict) - binary ON/OFF only**

**Critical Hardware Limitation - UNO R4 + HW-130 Clone:**

The cheap HW-130 clone shield (not genuine Adafruit) has a critical issue on UNO R4:
- **Servo library** (pin 10) and **motor OE PWM** (pin 7) share the same hardware timer
- When `analogWrite()` is used on pin 7, it disables the servo's PWM signal
- Result: Servo won't move while motors are running

**Root Cause:**
- UNO R4 (Renesas RA4M1) has limited PWM timers
- Pin 7 and pin 10 both use the same timer peripheral
- Servo library claims the timer → `analogWrite(7, ...)` fails silently
- OR vice versa: motor PWM claims timer → servo PWM breaks

**The Workaround (in motion.cpp):**
```cpp
// BEFORE (broken):
analogWrite(SR_OE, 255 - pwm);  // Smooth PWM 0-255, but breaks servo!

// AFTER (working):
digitalWrite(SR_OE, (global_pwm > 0) ? LOW : HIGH);  // Binary ON/OFF only
```

**Trade-offs:**
- ❌ Lost: Smooth speed control (PWM 0-255)
- ❌ Lost: Per-wheel speed differences
- ❌ Lost: Gentle acceleration ramps
- ✅ Gained: Servo works perfectly for scanning
- ✅ Gained: Motors still move (just binary speed)
- ✅ Gained: Obstacle avoidance fully functional

**Why This Works:**
- Binary motor control (full speed or stop) is sufficient for Phase 1
- Speed "tiers" (FAST/SLOW) are emulated via bit-pulsing in software
- ARC turns use timed motor ON/OFF pulses to fake slower inner track
- No smooth PWM needed for basic obstacle avoidance

**Lesson:** Cheap clone shields may have undocumented limitations. Always test servo + motor integration early!

### Servo (Pan Mount):
- ✅ Sweep range: 45°-135° (90° intervals)
- ✅ Settle time: 80ms optimized
- ✅ Center-focused pattern for forward safety
- ✅ Remains attached during runtime (no detaching)

## Lessons Learned

1. **HC-SR04 is highly directional** - forward-looking sensor must check center frequently
2. **UNO R4 timer sharing** - Servo and PWM libraries conflict on shared timers
3. **Backoff logic must not retrigger** - state-based checks prevent timer resets
4. **Slow is safe** - PWM 105-140 gives time to react in tight spaces
5. **Center-heavy scanning** - returning to 90° between side scans crucial for safety
6. **Serial protocol robustness** - explicit command handlers prevent ambiguity

## Performance Metrics

### Scanning Performance:
- Full cycle: 150ms (5 angles × 2 samples)
- Center updates: every 50ms (3× per cycle)
- Decision latency: 250ms

### Movement Performance:
- Speed range: 105-230 PWM (slow to moderate)
- Backoff: 500ms (~20cm reverse)
- Turn commitment: 1.2 seconds
- Stop distance: 25cm (home profile)

---

## Next Steps: Phase 2

Phase 1 provides the foundation - reliable locomotion and obstacle avoidance. Phase 2 will add:
- Advanced navigation strategies
- Path planning and memory
- Multi-sensor fusion (IMU integration)
- Adaptive behavior and learning

**Phase 2 documentation will be in a separate README.**

