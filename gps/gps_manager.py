import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import serial
import time
import threading
from logger.logger import SystemLogger

class GPSManager:
    """
    Reads NMEA sentences from a serial GPS module (e.g., u-blox NEO-6M)
    in a background daemon thread and exposes the latest coordinates
    to the main application via a thread-safe getter.
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
        """Spawns the GPS reader as a daemon thread and returns immediately."""
        self.running = True
        self.thread = threading.Thread(target=self._read_gps_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.log("INFO", "GPS Background thread started.")

    def _read_gps_loop(self):
        """
        Internal loop that continuously reads lines from the serial port
        and forwards GPGGA/GNGGA sentences to the parser.
        If the hardware is unavailable, logs a warning and exits gracefully
        so the rest of the system continues without GPS data.
        """
        try:
            with serial.Serial(self.port, self.baud_rate, timeout=1) as ser:
                while self.running:
                    line = ser.readline().decode('utf-8', errors='ignore')
                    if line.startswith("$GPGGA") or line.startswith("$GNGGA"):
                        self._parse_gpgqa(line)
        except Exception as e:
            self.logger.log("WARNING", f"GPS Hardware unavailable: {e}")
            self.current_lat = 0.0000
            self.current_lon = 0.0000

    def _parse_gpgqa(self, line):
        """
        Parses a GPGGA/GNGGA NMEA sentence and updates the stored coordinates.
        Converts the raw DDMM.MMMM format to decimal degrees:
            decimal = DD + (MM.MMMM / 60)
        """
        try:
            parts = line.split(',')
            if parts[2] and parts[4]:
                lat = float(parts[2])
                lon = float(parts[4])
                self.current_lat = int(lat / 100) + (lat % 100) / 60
                self.current_lon = int(lon / 100) + (lon % 100) / 60
        except Exception:
            pass

    def get_location(self):
        """
        Returns the most recently parsed GPS coordinates.

        Returns:
            tuple: (latitude, longitude) in decimal degrees.
                   Returns (0.0, 0.0) if no fix has been acquired.
        """
        return self.current_lat, self.current_lon

    def stop(self):
        """Signals the background thread to exit on its next iteration."""
        self.running = False

# --- Standalone Test ---
if __name__ == "__main__":
    gps = GPSManager()
    gps.start()
    time.sleep(60)
    print(f"Current Location: {gps.get_location()}")
    gps.stop()
