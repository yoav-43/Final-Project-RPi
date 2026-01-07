/*
 * WAKEUP SYSTEM - ARDUINO BUZZER CONTROL
 * Receives: 'F' (Fatigue), 'D' (Distracted), 'O' (OK)
 */

const int BUZZER_PIN = 6; // Change this if your buzzer is on a different pin

void setup() {
  Serial.begin(9600);      // Must match the Python script baud rate
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Start-up melody to confirm connection
  tone(BUZZER_PIN, 2000, 100);
  delay(150);
  tone(BUZZER_PIN, 2500, 100);
}

void loop() {
  if (Serial.available() > 0) {
    char state = Serial.read(); // Read the command from Raspberry Pi
    
    if (state == 'F') { 
      // --- FATIGUE ALERT ---
      // Continuous high-pitched tone to wake up the driver
      tone(BUZZER_PIN, 1000); 
    } 
    else if (state == 'D') { 
      // --- DISTRACTION ALERT ---
      // Intermittent beeps (double beep)
      tone(BUZZER_PIN, 1500, 150);
      delay(200);
      tone(BUZZER_PIN, 1500, 150);
      delay(200);
    } 
    else if (state == 'O') {
      // --- ALL OK ---
      noTone(BUZZER_PIN);
    }
  }
}