// Arduino UNO: All 6 LEDs ON (for hardware check)

const int ledPins[6] = {3, 5, 6, 9, 10, 11}; // PWM pins

void setup() {
  for (int i = 0; i < 6; ++i) {
    pinMode(ledPins[i], OUTPUT);
    analogWrite(ledPins[i], 255); // Full brightness (ON)
  }
}

void loop() {
  // No action needed until mobile/app/ESP32 control is ready
}