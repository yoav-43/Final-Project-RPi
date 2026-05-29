/*
 * WakeUp System — Arduino Buzzer Controller
 * -----------------------------------------
 * Receives single-byte commands from the Raspberry Pi over USB serial
 * and drives a passive buzzer to produce distinct alert tones.
 *
 * Command protocol:
 *   'F' — Fatigue (PERCLOS)     → fast beeping 800 Hz  (100ms on / 100ms off)
 *   'D' — Distraction (yaw/pitch) → continuous 1500 Hz tone
 *   'N' — No face detected      → slow beeping 2500 Hz (100ms on / 400ms off)
 *   'O' — Driver OK             → silence
 */

const int BUZZER_PIN = 6;

char currentState = 'O';
unsigned long lastToggle = 0;
bool buzzerOn = false;

void setup() {
  Serial.begin(9600);
  pinMode(BUZZER_PIN, OUTPUT);

  // Startup melody
  tone(BUZZER_PIN, 2000, 100);
  delay(150);
  tone(BUZZER_PIN, 2500, 100);
  delay(150);
}

void loop() {
  // Read latest command (drain buffer to always use most recent)
  while (Serial.available() > 0) {
    currentState = Serial.read();
  }

  unsigned long now = millis();

  if (currentState == 'F') {
    // Fast beeping: 100ms on / 100ms off at 800 Hz
    if (now - lastToggle >= 100) {
      lastToggle = now;
      buzzerOn = !buzzerOn;
      buzzerOn ? tone(BUZZER_PIN, 800) : noTone(BUZZER_PIN);
    }
  }
  else if (currentState == 'D') {
    // Continuous 1500 Hz tone
    tone(BUZZER_PIN, 1500);
  }
  else if (currentState == 'N') {
    // Slow beeping: 100ms on / 400ms off at 2500 Hz
    if (now - lastToggle >= (buzzerOn ? 100 : 400)) {
      lastToggle = now;
      buzzerOn = !buzzerOn;
      buzzerOn ? tone(BUZZER_PIN, 2500) : noTone(BUZZER_PIN);
    }
  }
  else if (currentState == 'O') {
    noTone(BUZZER_PIN);
    buzzerOn = false;
  }
}
