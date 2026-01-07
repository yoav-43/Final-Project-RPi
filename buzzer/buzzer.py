import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import serial
import time
from logger.logger import SystemLogger

class BuzzerController:
    """
    Manages serial communication with the Arduino for buzzer alerts.
    """

    def __init__(self, port='/dev/ttyACM0', baud_rate=9600):
        """
        Initializes the connection to the Arduino.

        Args:
            port (str): Serial port (e.g., COM3 or /dev/ttyACM0).
            baud_rate (int): Communication speed.
        """
        self.logger = SystemLogger("Buzzer")
        self.arduino = None
        try:
            self.arduino = serial.Serial(port, baud_rate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            self.logger.log("INFO", f"Connected to Arduino on {port}")
        except Exception as e:
            self.logger.log("ERROR", f"Failed to connect to Arduino: {e}")

    def send_command(self, command_char):
        """
        Sends a single character command to the Arduino.
        
        Args:
            command_char (bytes): The character to send (e.g., b'F').
        """
        if self.arduino and self.arduino.is_open:
            try:
                self.arduino.write(command_char)
            except Exception as e:
                self.logger.log("ERROR", f"Serial write failed: {e}")

    def alert_fatigue(self):
        """Triggers the fatigue alarm (Red/High Priority)."""
        self.send_command(b'F')

    def alert_distraction(self):
        """Triggers the distraction alarm (Yellow/Medium Priority)."""
        self.send_command(b'D')

    def status_ok(self):
        """Sets status to OK (Green/Silent)."""
        self.send_command(b'O')

    def close(self):
        """Closes the serial connection."""
        if self.arduino:
            self.arduino.close()

# --- Main Execution for Testing ---
if __name__ == "__main__":
    # Note: This requires an actual Arduino connected to test fully.
    buzzer = BuzzerController() # Change port as needed
    print("Testing Fatigue Alert...")
    buzzer.alert_fatigue()
    time.sleep(1)
    print("Testing OK Status...")
    buzzer.status_ok()
    buzzer.close()