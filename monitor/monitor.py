import sys
import os
import time
import json
import cv2
import dlib
import atexit
from imutils import face_utils
from dotenv import load_dotenv

# Ensure we can import from sibling folders
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger.logger import SystemLogger
from image_processor.image_processor import ImageProcessor 
from buzzer.buzzer import BuzzerController
from cloudinary_server_manager.cloudinary_server_manager import CloudinaryManager
from heroku_server_manager.heroku_server_manager import HerokuClient
from gps.gps_manager import GPSManager

class DriverMonitor:
    """
    Main Application Class: Orchestrates all modules for driver monitoring.
    """

    def __init__(self, config_path='monitor/config.json'):
        # 1. Load Environment Variables (Security Fix)
        load_dotenv()

        # 2. Load Config JSON (Structure & Non-secrets)
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # 3. OVERWRITE Secrets with Environment Variables
        # This injects the keys from the hidden .env file into the config
        self.config['base_url'] = os.getenv('HEROKU_API_URL')
        
        # We use .get() here to avoid errors if the key doesn't exist in .env (though it should)
        self.config['cloudinary']['cloud_name'] = os.getenv('CLOUDINARY_CLOUD_NAME')
        self.config['cloudinary']['api_key'] = os.getenv('CLOUDINARY_API_KEY')
        self.config['cloudinary']['api_secret'] = os.getenv('CLOUDINARY_API_SECRET')

        # Safety Check: Stop if keys are missing
        if not self.config['cloudinary']['api_key']:
            print("ERROR: API Keys not found! Make sure you created the .env file with your credentials.")
            sys.exit(1)

        # 4. Initialize Logger
        self.logger = SystemLogger("MainMonitor")
        
        # 5. Initialize Modules
        self.buzzer = BuzzerController(port=self.config['arduino_port'])
        self.cloud_mgr = CloudinaryManager(**self.config['cloudinary'])
        self.backend = HerokuClient(self.config['base_url'], self.config['device_id'])
        self.gps = GPSManager(port=self.config.get('gps_port', '/dev/ttyUSB0'))
        
        # 6. Initialize Image Processor
        self.logger.log("INFO", "Initializing Image Processor...")
        self.img_proc = ImageProcessor(
            predictor_path=self.config['predictor_path'],
            camera_index=0
        )
        
        # 7. State Variables
        self.video_out = None
        self.video_path = None # Will be set in run()
        self.eye_closed_frames = 0
        self.total_frames_in_minute = 0
        self.running = False

    def run(self):
        """Main execution loop."""
        self.gps.start()
        
        # Setup Camera via Processor
        try:
            self.img_proc.setup_camera()
        except IOError as e:
            self.logger.log("ERROR", str(e))
            return

        # Start Backend Session
        self.backend.start_drive()

        # --- VIDEO RECORDER SETUP (FIXED) ---
        # We use MJPG + .avi for robustness against Ctrl+C crashes
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        
        # Force .avi extension regardless of what config says
        base_name = os.path.splitext(self.config['video_temp_file'])[0]
        self.video_path = f"{base_name}.avi"
        
        self.logger.log("INFO", f"Recording video to: {self.video_path}")
        self.video_out = cv2.VideoWriter(self.video_path, fourcc, 10.0, (640, 480))
        
        # Constants for Landmarks
        (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
        (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
        
        last_telemetry_time = time.time()
        self.running = True

        self.logger.log("INFO", "System Live. Waiting for driver...")

        try:
            while self.running:
                ret, frame = self.img_proc.get_frame()
                if not ret: break
                
                # Resize is crucial for the video writer to work
                frame = cv2.resize(frame, (640, 480))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Use detector from img_proc
                rects = self.img_proc.detector(gray, 0)

                # Reset Per-Frame States
                is_distracted = len(rects) == 0
                is_fatigued = False
                ear, yaw, pitch = 0.0, 0.0, 0.0
                self.total_frames_in_minute += 1

                # ---------------- AI PROCESSING ----------------
                if not is_distracted:
                    # Use predictor from img_proc
                    shape = face_utils.shape_to_np(self.img_proc.predictor(gray, rects[0]))
                    
                    # EAR Calculation via Processor
                    leftEAR = self.img_proc.calculate_ear(shape[lS:lE])
                    rightEAR = self.img_proc.calculate_ear(shape[rS:rE])
                    ear = (leftEAR + rightEAR) / 2.0

                    # Pose Calculation via Processor
                    yaw, pitch = self.img_proc.get_head_pose(shape, 480, 640)

                    # Logic Checks
                    thresh = self.config['thresholds']
                    
                    # Fatigue (PERCLOS)
                    if ear < thresh['ear']:
                        self.eye_closed_frames += 1
                    
                    perclos = (self.eye_closed_frames / self.total_frames_in_minute) * 100
                    if perclos > thresh['perclos_fatigue_limit']:
                        is_fatigued = True

                    # Distraction (Pose)
                    if abs(yaw) > thresh['head_yaw'] or pitch < thresh['head_pitch']:
                        is_distracted = True

                # ---------------- FEEDBACK ----------------
                box_color = (0, 255, 0) # Green
                box_label = "FOCUSED"

                if is_fatigued:
                    box_color, box_label = (0, 0, 255), "FATIGUE!"
                    self.buzzer.alert_fatigue()
                elif is_distracted:
                    box_color, box_label = (0, 255, 255), "DISTRACTED"
                    self.buzzer.alert_distraction()
                else:
                    self.buzzer.status_ok()

                # Draw UI using Processor
                for rect in rects:
                    self.img_proc.draw_feedback(frame, rect, box_color, box_label)

                self.video_out.write(frame)

                # ---------------- TELEMETRY (1Hz) ----------------
                if time.time() - last_telemetry_time > 1.0:
                    perclos = (self.eye_closed_frames / self.total_frames_in_minute) * 100
                    lat, lon = self.gps.get_location()
                    
                    self.backend.send_telemetry(ear, perclos, is_distracted, yaw, pitch, lat, lon)
                    
                    # Console Log
                    log_lvl = "ERROR" if is_fatigued else ("WARNING" if is_distracted else "DEBUG")
                    self.logger.log(log_lvl, f"EAR:{ear:.2f} | PERCLOS:{perclos:.1f}% | Yaw:{yaw:.1f}")
                    
                    last_telemetry_time = time.time()

        except KeyboardInterrupt:
            self.logger.log("INFO", "Stopped by user (Ctrl+C).")
        finally:
            self.cleanup()

    def cleanup(self):
        """Releases resources and uploads data."""
        self.logger.log("INFO", "Starting cleanup...")
        self.running = False
        
        # Release Camera via Processor
        self.img_proc.release_camera()
        
        if self.video_out: 
            self.video_out.release()
            self.logger.log("INFO", "Video saved locally.")

        self.gps.stop()
        self.buzzer.close()

        # Upload Video (FIXED: Uses self.video_path, which is the .avi file)
        video_url = None
        if self.video_path and os.path.exists(self.video_path):
            video_url = self.cloud_mgr.upload_video(self.video_path)
        
        # End Session
        self.backend.end_drive(video_url)
        self.logger.log("INFO", "System shutdown complete.")

if __name__ == "__main__":
    if not os.path.exists('monitor/config.json'):
        print("Error: monitor/config.json not found.")
    else:
        app = DriverMonitor()
        app.run()