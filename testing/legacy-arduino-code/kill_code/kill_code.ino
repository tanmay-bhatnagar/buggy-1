// KILL.ino — Upload this before shutdown so buggy won't move on next boot.

void setup() {
  // Set all motor pins as OUTPUT and drive them LOW
  pinMode(2, OUTPUT);
  pinMode(3, OUTPUT);
  pinMode(4, OUTPUT);
  pinMode(5, OUTPUT);
  
  digitalWrite(2, LOW);
  digitalWrite(3, LOW);
  digitalWrite(4, LOW);
  digitalWrite(5, LOW);

  // Optional: give yourself a little confirmation on Serial
  Serial.begin(9600);
  Serial.println("KILL mode active. Motors disabled.");
}

void loop() {
  // Do nothing forever.
}
