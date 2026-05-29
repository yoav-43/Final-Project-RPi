import sys
import sys
import os
import signal
import time
import json
import cv2
import dlib
import atexit
from datetime import datetime
from collections import deque
from imutils import face_utils
from dotenv import load_dotenv

# Allow imports from sibling modules by adding the project root to the path.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger.logger import SystemLogger
from image_processor.image_processor import ImageProcessor 
from buzzer.buzzer import BuzzerController
from cloudinary_server_manager.cloudinary_server_manager import CloudinaryManager
from heroku_server_manager.heroku_server_manager import HerokuClient
from gps.gps_manager import GPSManager

class DriverMonitor:
    """
    Main application class that orchestrates all subsystems of the WakeUp
    driver monitoring system. Manages the detection loop, telemetry pipeline,
    video recording, and graceful shutdown sequence.
    """

    def __init__(self, config_path='monitor/config.json'):
        # Load secret credentials from the .env file in the project root.
        load_dotenv()

        # Load non-secret configuration (thresholds, ports, device ID).
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Inject secrets from environment variables, overwriting the
        # "ENV_VAR" placeholders present in config.json.
        self.config['base_url'] = os.getenv('HEROKU_API_URL')
        
        self.config['cloudinary']['cloud_name'] = os.getenv('CLOUDINARY_CLOUD_NAME')
        self.config['cloudinary']['api_key'] = os.getenv('CLOUDINARY_API_KEY')
        self.config['cloudinary']['api_secret'] = os.getenv('CLOUDINARY_API_SECRET')

        # Abort early if credentials are missing to prevent cryptic runtime errors.
        if not self.config['cloudinary']['api_key']:
            print("ERROR: API Keys not found! Make sure you created the .env file with your credentials.")
            sys.exit(1)

        # Initialize the logger for this module.
        os.makedirs("logs", exist_ok=True)
        log_filename = datetime.now().strftime("logs/drive_%Y-%m-%d_%H-%M-%S.log")
        # Update the latest.log symlink to point to this drive's log file.
        if os.path.islink("latest.log") or os.path.exists("latest.log"):
            os.remove("latest.log")
        os.symlink(log_filename, "latest.log")
        self.logger = SystemLogger("MainMonitor", log_file=log_filename)
        
        # Instantiate all subsystem modules.
        self.buzzer = BuzzerController(port=self.config['arduino_port'])
        self.cloud_mgr = CloudinaryManager(**self.config['cloudinary'])
        self.backend = HerokuClient(self.config['base_url'], self.config['device_id'])
        self.gps = GPSManager(port=self.config.get('gps_port', '/dev/ttyUSB0'))
        
        # Initialize the image processor and load the dlib landmark model.
        self.logger.log("INFO", "Initializing Image Processor...")
        self.img_proc = ImageProcessor(
            predictor_path=self.config['predictor_path'],
            camera_index=0
        )
        
        # State variables for the detection loop.
        self.video_out = None
        self.video_path = None
        # Sliding window for PERCLOS: stores 1 (closed) or 0 (open) per frame.
        # 30 frames ≈ 3 seconds at 10 fps — adjust via config if needed.
        perclos_window = self.config.get('perclos_window_frames', 30)
        self.eye_state_window = deque(maxlen=perclos_window)
        self.last_buzzer_state = None  # Track last sent command to avoid re-triggering mid-beep
        self.running = False
        self._fps = 0.0
        self._fps_frame_count = 0
        self._fps_last_time = None

    def run(self):
        """Starts all subsystems and enters the main frame-processing loop."""
        # Handle SIGTERM (sent by systemd on shutdown) the same as Ctrl+C.
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

        self.gps.start()
        
        # Open the camera; raise an error if the device is unavailable.
        try:
            self.img_proc.setup_camera()
        except IOError as e:
            self.logger.log("ERROR", str(e))
            return

        # Register the drive session with the backend server.
        self.backend.start_drive()

        # Use MJPG codec with .avi container for crash-safe incremental writes.
        # Frames are flushed to disk immediately, preventing data loss on abrupt exit.
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        
        # Force the .avi extension regardless of the configured file name.
        base_name = os.path.splitext(self.config['video_temp_file'])[0]
        self.video_path = f"{base_name}.avi"
        
        self.logger.log("INFO", f"Recording video to: {self.video_path}")
        self.video_out = cv2.VideoWriter(self.video_path, fourcc, 10.0, (640, 480))
        
        # Retrieve the landmark index ranges for the left and right eyes.
        (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
        (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
        
        last_telemetry_time = time.time()
        self._fps_last_time = time.time()
        self.running = True

        self.logger.log("INFO", "System Live. Waiting for driver...")

        try:
            while self.running:
                ret, frame = self.img_proc.get_frame()
                if not ret: break
                
                # Resize to a fixed resolution required by the VideoWriter.
                frame = cv2.resize(frame, (640, 480))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # FPS — measured every frame regardless of detection.
                self._fps_frame_count += 1
                now = time.time()
                elapsed = now - self._fps_last_time
                if elapsed >= 1.0:
                    self._fps = self._fps_frame_count / elapsed
                    self._fps_frame_count = 0
                    self._fps_last_time = now
                
                # Run the dlib HOG face detector on the grayscale frame.
                rects = self.img_proc.detector(gray, 0)

                # Default state: no face detected → silence buzzer and skip.
                is_distracted = False
                if len(rects) == 0:
                    self.buzzer.status_ok()
                    self.img_proc.draw_stats_overlay(frame, 0.0, 0.0, 0.0, 0.0, self._fps, self.config['thresholds'])
                    self.video_out.write(frame)
                    continue
                is_fatigued = False
                ear, yaw, pitch = 0.0, 0.0, 0.0

                # --- Computer Vision Processing ---
                # Extract the 68 facial landmark coordinates.
                shape = face_utils.shape_to_np(self.img_proc.predictor(gray, rects[0]))
                
                # Compute EAR for each eye and average them.
                leftEAR = self.img_proc.calculate_ear(shape[lS:lE])
                rightEAR = self.img_proc.calculate_ear(shape[rS:rE])
                ear = (leftEAR + rightEAR) / 2.0

                # Estimate head orientation from the landmark geometry.
                yaw, pitch = self.img_proc.get_head_pose(shape, 480, 640)

                thresh = self.config['thresholds']
                
                # Sliding-window PERCLOS: push 1 (closed) or 0 (open) each frame.
                # The deque automatically drops frames older than perclos_window_frames.
                self.eye_state_window.append(1 if ear < thresh['ear'] else 0)
                perclos = (sum(self.eye_state_window) / len(self.eye_state_window)) * 100
                if perclos > thresh['perclos_fatigue_limit']:
                    is_fatigued = True

                # Distraction is flagged when head rotation exceeds either threshold.
                if abs(yaw) > thresh['head_yaw'] or pitch < thresh['head_pitch']:
                    is_distracted = True

                # --- Driver Feedback ---
                box_color = (0, 255, 0)
                box_label = "FOCUSED"

                if is_fatigued:
                    box_color, box_label = (0, 0, 255), "FATIGUE!"
                    self.buzzer.alert_fatigue()
                elif is_distracted:
                    box_color, box_label = (0, 255, 255), "DISTRACTED"
                    self.buzzer.alert_distraction()
                else:
                    self.buzzer.status_ok()

                # Annotate the frame with the detection bounding box and status label.
                for rect in rects:
                    self.img_proc.draw_feedback(frame, rect, box_color, box_label)

                self.img_proc.draw_stats_overlay(frame, ear, perclos, yaw, pitch, self._fps, self.config['thresholds'])
                self.video_out.write(frame)
                if os.environ.get('DISPLAY'):
                    cv2.imshow("WakeUp Monitor", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                # --- Telemetry Transmission (1 Hz) ---
                if time.time() - last_telemetry_time > 1.0:
                    perclos = (sum(self.eye_state_window) / len(self.eye_state_window)) * 100 if self.eye_state_window else 0.0
                    lat, lon = self.gps.get_location()
                    
                    self.backend.send_telemetry(ear, perclos, is_distracted, yaw, pitch, lat, lon)
                    
                    # Log level reflects the current driver state for easy monitoring.
                    log_lvl = "ERROR" if is_fatigued else ("WARNING" if is_distracted else "DEBUG")
                    R, G, E = "\033[91m", "\033[92m", "\033[0m"
                    t = self.config['thresholds']
                    msg = (
                        f"EAR:{(G if ear >= t['ear'] else R)}{ear:.2f}{E} | "
                        f"PERCLOS:{(G if perclos <= t['perclos_fatigue_limit'] else R)}{perclos:.1f}%{E} | "
                        f"Yaw:{(G if abs(yaw) <= t['head_yaw'] else R)}{yaw:.1f}{E} | "
                        f"Pitch:{(G if pitch >= t['head_pitch'] else R)}{pitch:.1f}{E}"
                    )
                    self.logger.log_raw(log_lvl, msg)
                    
                    last_telemetry_time = time.time()

        except KeyboardInterrupt:
            self.logger.log("INFO", "Stopped by user (Ctrl+C).")
        finally:
            self.cleanup()

    def cleanup(self):
        """Releases all hardware resources, uploads the session video, and finalizes the drive record."""
        self.logger.log("INFO", "Starting cleanup...")
        self.running = False
        
        # Release the camera capture device.
        self.img_proc.release_camera()
        if os.environ.get('DISPLAY'):
            cv2.destroyAllWindows()
        
        if self.video_out: 
            self.video_out.release()
            self.logger.log("INFO", "Video saved locally.")

        self.gps.stop()
        self.buzzer.status_ok()
        self.buzzer.close()

        # Upload the recorded session video to Cloudinary and retrieve the CDN URL.
        video_url = None
        if self.video_path and os.path.exists(self.video_path):
            video_url = self.cloud_mgr.upload_video(self.video_path)
        
        # Finalize the drive session on the backend with the video URL.
        self.backend.end_drive(video_url)
        self.logger.log("INFO", "System shutdown complete.")

if __name__ == "__main__":
    if not os.path.exists('monitor/config.json'):
        print("Error: monitor/config.json not found.")
    else:
        app = DriverMonitor()
        app.run()
