# ESP32 patch: send an acknowledgment when a servo moves

**Already applied to `arduino/final_esp32.ino` on the `ijies-revision`
branch: just upload it.** This page shows exactly what changed.

Without this, the laptop never learns when the servo actually received its
command, and the session can only measure latency up to the serial write.
Four lines in `arduino/final_esp32.ino`. Nothing else changes.

## 1. `openDoorByAngle`

Before:

```cpp
void openDoorByAngle(int angle) {
  if (currentState != NORMAL) return; // Don't open during alert
  showOnLCD("Door Opened (EEG)");
  doorServo.write(angle);
  delay(1500);
```

After:

```cpp
void openDoorByAngle(int angle) {
  if (currentState != NORMAL) { Serial.println("ACK:DOOR:BLOCKED"); return; } // Don't open during alert
  showOnLCD("Door Opened (EEG)");
  doorServo.write(angle);
  Serial.println("ACK:DOOR");
  delay(1500);
```

## 2. `openWindowByAngle`

Before:

```cpp
void openWindowByAngle(int angle) {
  if (currentState != NORMAL) return;
  showOnLCD("Window Opened (EEG)");
  windowServo.write(angle);
  delay(1500);
```

After:

```cpp
void openWindowByAngle(int angle) {
  if (currentState != NORMAL) { Serial.println("ACK:WINDOW:BLOCKED"); return; }
  showOnLCD("Window Opened (EEG)");
  windowServo.write(angle);
  Serial.println("ACK:WINDOW");
  delay(1500);
```

## Flash and check

1. Open `final_esp32.ino` in the Arduino IDE, make the edits, upload to the ESP32.
2. Open the Serial Monitor at 115200 baud, type `ServoAngle:DOOR:90` and press
   Enter. The door should move and `ACK:DOOR` should appear.
3. Close the Serial Monitor before starting a session (only one program can
   hold the COM port).

The `BLOCKED` lines record any command refused because the gas or flame alarm
was active, so a refused command is never mistaken for a missed blink.
