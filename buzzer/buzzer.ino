/*
 * WakeUp System — Arduino Buzzer Controller
 * -----------------------------------------
 * Receives single-byte commands from the Raspberry Pi over USB serial
 * and drives a passive buzzer to produce distinct alert tones.
 *
 * Command protocol:
 *   'F' — Fatigue detected    → continuous 1000 Hz tone
 *   'D' — Distraction detected → double beep at 1500 Hz
 *   'O' — Driver OK            → silence
 */

const int BUZZER_PIN = 6;

void setup() {
  Serial.begin(9600);       // Baud rate must match BuzzerController in buzzer.py.
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Play a two-note startup melody to confirm the serial connection is live.
  tone(BUZZER_PIN, 2000, 100);
  delay(150);
  tone(BUZZER_PIN, 2500, 100);
}

void loop() {
  if (Serial.available() > 0) {
    char state = Serial.read();
    
    if (state == 'F') {
      // Fatigue alert: continuous high-pitched tone to wake the driver.
      tone(BUZZER_PIN, 1000);
    } 
    else if (state == 'D') {
      // Distraction alert: two short beeps to prompt the driver to refocus.
      tone(BUZZER_PIN, 1500, 150);
      delay(200);
      tone(BUZZER_PIN, 1500, 150);
      delay(200);
    } 
    else if (state == 'O') {
      // All clear: silence the buzzer.
      noTone(BUZZER_PIN);
    }
  }
}
