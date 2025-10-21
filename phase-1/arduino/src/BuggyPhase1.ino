#include "pins.h"
#include "config.h"
#include "motion.h"
#include "servo_scan.h"
#include "ultrasonic.h"
#include "serial_proto.h"
#include "watchdog.h"
#include "status.h"

void setup() {
  Serial.begin(BAUD_RATE);
  delay(250); // avoid UNO R4 boot hang on Jetson

  pins_init();
  motion_init();
  servo_init();
  ultrasonic_init();
  serial_proto_init();
  watchdog_init();
  status_init();

  Serial.println("BOOT,PHASE1");
}

void loop() {
  serial_proto_tick();
  watchdog_tick();
  servo_tick();
  ultrasonic_tick();
  motion_tick();
  status_tick();
}
