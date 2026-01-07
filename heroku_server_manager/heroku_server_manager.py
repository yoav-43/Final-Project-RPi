import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
import threading
from logger.logger import SystemLogger

class HerokuClient:
    """
    Manages HTTP communication with the backend server (Heroku).
    """

    def __init__(self, base_url, device_id):
        """
        Args:
            base_url (str): The API root URL.
            device_id (str): The unique ID of this RPi.
        """
        self.base_url = base_url
        self.device_id = device_id
        self.current_drive_id = None
        self.logger = SystemLogger("HerokuClient")

    def start_drive(self):
        """
        Initiates a new drive session on the server.
        """
        try:
            payload = {"device_id": self.device_id}
            response = requests.post(f"{self.base_url}/start_drive", json=payload, timeout=5)
            if response.status_code in [200, 201]:
                self.current_drive_id = response.json().get("drive_id")
                self.logger.log("INFO", f"Drive started. ID: {self.current_drive_id}")
                return self.current_drive_id
        except Exception as e:
            self.logger.log("ERROR", f"Failed to start drive: {e}")
        return None

    def send_telemetry(self, ear, perclos, is_distracted, yaw, pitch, lat=0, lon=0):
        """
        Sends telemetry data asynchronously (in a background thread).
        """
        if not self.current_drive_id:
            return

        payload = {
            "drive_id": self.current_drive_id,
            "ear": round(ear, 2),
            "perclos": round(perclos, 2),
            "is_distracted": is_distracted,
            "head_yaw": round(yaw, 2),
            "head_pitch": round(pitch, 2),
            "latitude": lat,
            "longitude": lon
        }

        # Run in thread to not block the video processing loop
        thread = threading.Thread(target=self._post_telemetry, args=(payload,))
        thread.start()

    def _post_telemetry(self, payload):
        try:
            requests.post(f"{self.base_url}/telemetry", json=payload, timeout=2)
        except Exception:
            pass # Silent fail for telemetry to avoid log spam

    def end_drive(self, video_url=None):
        """
        Finalizes the drive session with an optional video link.
        """
        if not self.current_drive_id:
            return

        payload = {
            "drive_id": self.current_drive_id,
            "video_url": video_url
        }
        try:
            requests.post(f"{self.base_url}/end_drive", json=payload, timeout=10)
            self.logger.log("INFO", "Drive ended successfully on server.")
        except Exception as e:
            self.logger.log("ERROR", f"Failed to end drive: {e}")

# --- Main Execution for Testing ---
if __name__ == "__main__":
    client = HerokuClient("https://fake-url.com/api", "test_device")
    print("Testing Backend Client (Simulated)...")
    # client.start_drive()