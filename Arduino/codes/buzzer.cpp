const int buzzerPin = 6;
unsigned long buzzerStartTime = 0;
bool buzzerActive = false;

void setup() {
  Serial.begin(9600);
  pinMode(buzzerPin, OUTPUT);
}

void loop() {
  // 1. Check for new signals from Raspberry Pi
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (command == 'W') {
      digitalWrite(buzzerPin, HIGH);
      buzzerStartTime = millis(); // Start the stopwatch
      buzzerActive = true;
    }
  }

  // 2. Check if 2 seconds have passed without freezing the code
  if (buzzerActive && (millis() - buzzerStartTime >= 2000)) {
    digitalWrite(buzzerPin, LOW);
    buzzerActive = false;
  }
  
  // You can add other code here, and it will still run!
}