  #include <ESP32Servo.h>
  #include <Wire.h>
  #include <LiquidCrystal_I2C.h>
  #include <Keypad.h>
  #include <Adafruit_AHTX0.h>

  // ==== Pin Definitions ====
  #define DOOR_SERVO_PIN 18
  #define WINDOW_SERVO_PIN 4
  #define FAN_IN1 15
  #define FAN_IN2 2
  #define FAN_ENA 23
  #define BUZZER_PIN 19
  #define GAS_SENSOR_PIN 34
  #define FLAME_SENSOR_PIN 35
  #define LCD_SDA 21
  #define LCD_SCL 22

  // ==== Hardware Objects ====
  Servo doorServo;
  Servo windowServo;
  LiquidCrystal_I2C lcd(0x27, 16, 2);
  Adafruit_AHTX0 aht;

  // ==== Keypad Setup ====
  const byte ROWS = 4, COLS = 4;
  char keys[ROWS][COLS] = {
    {'1','2','3','A'},
    {'4','5','6','B'},
    {'7','8','9','C'},
    {'*','0','#','D'}
  };
  byte rowPins[ROWS] = {13, 12, 14, 27};
  byte colPins[COLS] = {26, 25, 33, 32};
  Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

  // ==== Password ====
  String correctPassword = "1234";
  String inputPassword = "";

  // ==== Timers and State ====
  unsigned long lastSensorCheck = 0;
  const unsigned long sensorCheckInterval = 200;
  unsigned long lastLCDUpdate = 0;
  const unsigned long lcdInterval = 1500;
  const unsigned long alertDisplayTime = 3000; // Alert stays 3s, then reverts
  unsigned long alertStartTime = 0;

  int lastPwm = 0; // Fan PWM

  // ==== State Flags ====
  enum SystemState { NORMAL, GAS_ALERT, FLAME_ALERT, SAFE_DISPLAY };
  SystemState currentState = NORMAL;

  // ==== Helper: Only update LCD if message changed ====
  void showOnLCD(const char* line1, const char* line2 = "") {
    static String prevL1 = "";
    static String prevL2 = "";
    String l1(line1), l2(line2);
    if (l1 != prevL1 || l2 != prevL2) {
      lcd.clear();
      lcd.setCursor(0, 0); lcd.print(l1);
      lcd.setCursor(0, 1); lcd.print(l2);
      prevL1 = l1;
      prevL2 = l2;
    }
  }

  void setup() {
    // ==== Servos ====
    doorServo.attach(DOOR_SERVO_PIN);
    windowServo.attach(WINDOW_SERVO_PIN);
    doorServo.write(0);
    windowServo.write(0);

    // ==== Fan Motor ====
    pinMode(FAN_IN1, OUTPUT); pinMode(FAN_IN2, OUTPUT); pinMode(FAN_ENA, OUTPUT);
    digitalWrite(FAN_IN1, HIGH); digitalWrite(FAN_IN2, LOW);
    analogWrite(FAN_ENA, 0);

    // ==== Buzzer ====
    pinMode(BUZZER_PIN, OUTPUT); digitalWrite(BUZZER_PIN, LOW);

    // ==== Sensors ====
    pinMode(GAS_SENSOR_PIN, INPUT); pinMode(FLAME_SENSOR_PIN, INPUT);

    // ==== LCD & I2C ====
    Wire.begin(LCD_SDA, LCD_SCL);
    lcd.init(); lcd.backlight();

    // ==== Temp/Humidity Sensor ====
    if (!aht.begin()) {
      showOnLCD("AHT21B Error!"); while (1);
    }

    showOnLCD("System Ready");
    delay(1500); // Just at startup
    showOnLCD("Temp:","--C  Hum: --%");
    Serial.begin(115200); // For EEG/fan/door/window
  }

  void loop() {
    handleEEG();        // All BCI control (DOOR, WINDOW, FAN)
    handleKeypad();     // Keypad password
    handleSensors();    // Flame/gas/alerts
    handleStateDisplay(); // LCD, buzzer, temp/hum
    handleFanMotor();   // Fan always uses lastPwm
  }

  // ==== 1. EEG/Serial/Fan Command Handler ====
  void handleEEG() {
    static String eegBuffer = "";
    while (Serial.available()) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') {
        eegBuffer.trim();
        if (eegBuffer.startsWith("ServoAngle:DOOR:")) {
          int angle = eegBuffer.substring(16).toInt();
          openDoorByAngle(angle);
        } else if (eegBuffer.startsWith("ServoAngle:WINDOW:")) {
          int angle = eegBuffer.substring(18).toInt();
          openWindowByAngle(angle);
        } else if (eegBuffer.startsWith("FAN:")) {
          int idx = eegBuffer.indexOf(':');
          if (idx >= 0) {
            int pwmValue = eegBuffer.substring(idx + 1).toInt();
            pwmValue = constrain(pwmValue, 0, 255);
            lastPwm = pwmValue;
            showOnLCD("Fan PWM:", String(lastPwm).c_str());
            lastLCDUpdate = millis();
          }
        }
        eegBuffer = "";
      } else {
        eegBuffer += c;
      }
    }
  }

  // === 2. Door/Window Control via Serial Commands (for EEG) ===
  void openDoorByAngle(int angle) {
    if (currentState != NORMAL) return; // Don't open during alert
    showOnLCD("Door Opened (EEG)");
    doorServo.write(angle);
    delay(1500);
    doorServo.write(0);
    showOnLCD("Door Closed");
    delay(800);
    showOnLCD("Temp:","--C  Hum: --%");
  }
  void openWindowByAngle(int angle) {
    if (currentState != NORMAL) return;
    showOnLCD("Window Opened (EEG)");
    windowServo.write(angle);
    delay(1500);
    windowServo.write(0);
    showOnLCD("Window Closed");
    delay(800);
    showOnLCD("Temp:","--C  Hum: --%");
  }

  // === 3. Keypad Logic (open door with correct password) ===
  void handleKeypad() {
    char key = keypad.getKey();
    if (key && currentState == NORMAL) { // Disable keypad during alert
      // Beep on every key
      digitalWrite(BUZZER_PIN, HIGH); delay(50); digitalWrite(BUZZER_PIN, LOW);

      if (key == '#') {
        if (inputPassword == correctPassword) {
          showOnLCD("Door Opened");
          doorServo.write(90);
          delay(2000);
          doorServo.write(0);
          showOnLCD("Door Closed");
          delay(800);
          showOnLCD("Temp:","--C  Hum: --%");
        } else {
          showOnLCD("Wrong Password");
          // Error beep
          for (int i = 0; i < 2; i++) {
            digitalWrite(BUZZER_PIN, HIGH); delay(80);
            digitalWrite(BUZZER_PIN, LOW); delay(80);
          }
          delay(1000);
          showOnLCD("Temp:","--C  Hum: --%");
        }
        inputPassword = "";
      } else if (key == '*') {
        inputPassword = "";
        showOnLCD("Password Cleared");
        delay(400);
        showOnLCD("Temp:","--C  Hum: --%");
      } else {
        inputPassword += key;
        String stars = "";
        for (unsigned int i = 0; i < inputPassword.length(); i++) stars += '*';
        showOnLCD("Password:", stars.c_str());
      }
    }
  }

  // === 4. Sensor State Logic (Non-blocking, robust) ===
  void handleSensors() {
    unsigned long now = millis();
    static bool buzzerActive = false;

    if (now - lastSensorCheck < sensorCheckInterval) return;
    lastSensorCheck = now;

    int gasVal = analogRead(GAS_SENSOR_PIN);
    int flameVal = analogRead(FLAME_SENSOR_PIN);

    if (gasVal < 500 && currentState != GAS_ALERT) {
      currentState = GAS_ALERT;
      alertStartTime = now;
      buzzerActive = true;
      showOnLCD("Gas Alert!");
    } else if (flameVal < 700 && currentState != FLAME_ALERT) {
      currentState = FLAME_ALERT;
      alertStartTime = now;
      buzzerActive = true;
      showOnLCD("Flame Alert!");
    }

    // End alert after display time if no longer triggered
    if ((currentState == GAS_ALERT && gasVal >= 500) ||
        (currentState == FLAME_ALERT && flameVal >= 700)) {
      if (now - alertStartTime > alertDisplayTime) {
        currentState = SAFE_DISPLAY;
        alertStartTime = now;
        buzzerActive = false;
        digitalWrite(BUZZER_PIN, LOW);
        showOnLCD("Safe");
      }
    }

    // Buzzer only on during active alert
    if ((currentState == GAS_ALERT || currentState == FLAME_ALERT) && buzzerActive) {
      digitalWrite(BUZZER_PIN, HIGH);
    } else {
      digitalWrite(BUZZER_PIN, LOW);
    }
  }

  // === 5. State Display (LCD + temp/humid when safe/normal) ===
  void handleStateDisplay() {
    unsigned long now = millis();
    static bool wasSafe = false;

    // When not in alert or safe-display, show temp/hum
    if (currentState == SAFE_DISPLAY && now - alertStartTime > 2000) {
      currentState = NORMAL;
      showOnLCD("Temp:","--C  Hum: --%");
      lastLCDUpdate = 0;
    }

    // Update temp/humidity on LCD every lcdInterval when normal
    if (currentState == NORMAL && (now - lastLCDUpdate > lcdInterval)) {
      sensors_event_t humidity, temp;
      aht.getEvent(&humidity, &temp);
      char buf1[17], buf2[17];
      snprintf(buf1, 17, "Temp: %.1fC", temp.temperature);
      snprintf(buf2, 17, "Hum: %.1f%%", humidity.relative_humidity);
      showOnLCD(buf1, buf2);
      lastLCDUpdate = now;
    }
  }

  // === 6. Fan Motor (always apply last PWM) ===
  void handleFanMotor() {
    digitalWrite(FAN_IN1, HIGH); digitalWrite(FAN_IN2, LOW);
    analogWrite(FAN_ENA, lastPwm);
  }
