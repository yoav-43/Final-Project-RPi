import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
import threading
from logger.logger import SystemLogger

class HerokuClient:
    """
    HTTP client for the WakeUp Flask backend hosted on Heroku.
    Manages drive session lifecycle (start/end) and streams telemetry
    data asynchronously to avoid blocking the video processing loop.
    """

    def __init__(self, base_url, device_id):
        """
        Args:
            base_url (str): Root URL of the backend API
                            (e.g., https://your-app.herokuapp.com/api).
            device_id (str): Unique identifier for this Raspberry Pi unit,
                             used to tag sessions in the database.
        """
        self.base_url = base_url
        self.device_id = device_id
        self.current_drive_id = None
        self.logger = SystemLogger("HerokuClient")

    def start_drive(self, retries=3):
        """
        Registers a new drive session on the server and stores the
        returned drive ID for use in subsequent telemetry calls.
        Retries up to `retries` times to handle cold Heroku dyno starts.
        """
        for attempt in range(1, retries + 1):
            try:
                payload = {"device_id": self.device_id}
                response = requests.post(f"{self.base_url}/start_drive", json=payload, timeout=15)
                if response.status_code in [200, 201]:
                    self.current_drive_id = response.json().get("drive_id")
                    self.logger.log("INFO", f"Drive started. ID: {self.current_drive_id}")
                    return self.current_drive_id
            except Exception as e:
                self.logger.log("WARNING", f"start_drive attempt {attempt}/{retries} failed: {e}")
        self.logger.log("ERROR", "Failed to start drive after all retries. Running offline.")
        return None

    def send_telemetry(self, ear, perclos, is_distracted, yaw, pitch, lat=0, lon=0):
        """
        Sends a telemetry sample to the backend in a background thread
        so the call returns immediately and does not stall the video loop.

        Args:
            ear (float): Eye Aspect Ratio for the current frame.
            perclos (float): PERCLOS score (% closed-eye frames) for the current window.
            is_distracted (bool): True if head pose exceeded distraction thresholds.
            yaw (float): Horizontal head rotation in degrees.
            pitch (float): Vertical head rotation in degrees.
            lat (float): GPS latitude in decimal degrees.
            lon (float): GPS longitude in decimal degrees.
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

        # Fire-and-forget: telemetry failures are silently discarded to
        # prevent log spam from transient network interruptions.
        thread = threading.Thread(target=self._post_telemetry, args=(payload,))
        thread.start()

    def _post_telemetry(self, payload):
        try:
            requests.post(f"{self.base_url}/telemetry", json=payload, timeout=2)
        except Exception:
            pass

    def end_drive(self, video_url=None):
        """
        Finalizes the drive session on the server, attaching the Cloudinary
        video URL to the session record.

        Args:
            video_url (str | None): CDN URL of the uploaded session recording.
        """
        if not self.current_drive_id:
            return

        payload = {
            "drive_id": self.current_drive_id,
            "video_url": video_url
        }
        try:
            requests.post(f"{self.base_url}/end_drive", json=payload, timeout=30)
            self.logger.log("INFO", "Drive ended successfully on server.")
        except Exception as e:
            self.logger.log("ERROR", f"Failed to end drive: {e}")

# --- Standalone Test ---
if __name__ == "__main__":
    client = HerokuClient("https://fake-url.com/api", "test_device")
    print("Testing Backend Client (Simulated)...")
    # client.start_drive()
