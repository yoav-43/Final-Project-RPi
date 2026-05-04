import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import serial
import time
from logger.logger import SystemLogger

class BuzzerController:
    """
    Manages serial communication with the Arduino buzzer controller.
    Translates high-level alert states into single-byte serial commands
    that the Arduino firmware interprets to produce distinct tones.
    """

    def __init__(self, port='/dev/ttyACM0', baud_rate=9600):
        """
        Opens the serial connection to the Arduino and waits for it to
        complete its reset cycle before any commands are sent.

        Args:
            port (str): Serial port of the Arduino (e.g., /dev/ttyACM0 or COM3).
            baud_rate (int): Baud rate; must match Serial.begin() in the firmware.
        """
        self.logger = SystemLogger("Buzzer")
        self.arduino = None
        try:
            self.arduino = serial.Serial(port, baud_rate, timeout=1)
            time.sleep(2)  # Allow the Arduino to complete its hardware reset.
            self.logger.log("INFO", f"Connected to Arduino on {port}")
        except Exception as e:
            self.logger.log("ERROR", f"Failed to connect to Arduino: {e}")

    def send_command(self, command_char):
        """
        Transmits a single-byte command to the Arduino over the serial link.
        Silently skips the write if the connection is unavailable.

        Args:
            command_char (bytes): The command byte to send (b'F', b'D', or b'O').
        """
        if self.arduino and self.arduino.is_open:
            try:
                self.arduino.write(command_char)
            except Exception as e:
                self.logger.log("ERROR", f"Serial write failed: {e}")

    def alert_fatigue(self):
        """Sends the fatigue alert command. Arduino responds with a continuous tone."""
        self.send_command(b'F')

    def alert_distraction(self):
        """Sends the distraction alert command. Arduino responds with a double beep."""
        self.send_command(b'D')

    def status_ok(self):
        """Sends the all-clear command. Arduino silences the buzzer."""
        self.send_command(b'O')

    def close(self):
        """Closes the serial port and releases the connection resource."""
        if self.arduino:
            self.arduino.close()

# --- Standalone Test ---
if __name__ == "__main__":
    buzzer = BuzzerController()
    print("Testing Fatigue Alert...")
    buzzer.alert_fatigue()
    time.sleep(1)
    print("Testing OK Status...")
    buzzer.status_ok()
    buzzer.close()
