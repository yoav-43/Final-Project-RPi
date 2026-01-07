import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import serial
import time
import threading
from logger.logger import SystemLogger

class GPSManager:
    """
    Reads GPS data from a serial module (e.g., NEO-6M).
    """

    def __init__(self, port='/dev/ttyAMA0', baud_rate=38400):
        self.logger = SystemLogger("GPS")
        self.port = port
        self.baud_rate = baud_rate
        self.current_lat = 0.0
        self.current_lon = 0.0
        self.running = False
        self.thread = None

    def start(self):
        """Starts the GPS reading thread."""
        self.running = True
        self.thread = threading.Thread(target=self._read_gps_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.log("INFO", "GPS Background thread started.")

    def _read_gps_loop(self):
        """Internal loop to parse NMEA sentences."""
        try:
            # Note: For testing without HW, this might fail immediately
            with serial.Serial(self.port, self.baud_rate, timeout=1) as ser:
                while self.running:
                    line = ser.readline().decode('utf-8', errors='ignore')
                    # self.logger.log("INFO", "serial line: " + line)
                    if line.startswith("$GPGGA") or line.startswith("$GNGGA"):
                        self._parse_gpgqa(line)
        except Exception as e:
            self.logger.log("WARNING", f"GPS Hardware unavailable: {e}")
            # Mock data for testing if hardware fails
            self.current_lat = 0.0000
            self.current_lon = 0.0000

    def _parse_gpgqa(self, line):
        """Simple NMEA parser (can be replaced with pynmea2 lib)."""
        try:
            parts = line.split(',')
            if parts[2] and parts[4]:
                # Convert DDMM.MMMM to Decimal Degrees
                lat = float(parts[2])
                lon = float(parts[4])
                self.current_lat = int(lat / 100) + (lat % 100) / 60
                self.current_lon = int(lon / 100) + (lon % 100) / 60
        except Exception:
            pass

    def get_location(self):
        """Returns the last known (lat, lon)."""
        return self.current_lat, self.current_lon

    def stop(self):
        self.running = False

# --- Main Execution for Testing ---
if __name__ == "__main__":
    gps = GPSManager()
    gps.start()
    time.sleep(60)
    print(f"Current Location: {gps.get_location()}")
    gps.stop()