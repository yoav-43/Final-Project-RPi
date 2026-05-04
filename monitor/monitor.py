import sys
import os
import time
import json
import cv2
import dlib
import atexit
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
        self.logger = SystemLogger("MainMonitor")
        
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
        self.eye_closed_frames = 0
        self.total_frames_in_minute = 0
        self.running = False

    def run(self):
        """Starts all subsystems and enters the main frame-processing loop."""
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
        self.running = True

        self.logger.log("INFO", "System Live. Waiting for driver...")

        try:
            while self.running:
                ret, frame = self.img_proc.get_frame()
                if not ret: break
                
                # Resize to a fixed resolution required by the VideoWriter.
                frame = cv2.resize(frame, (640, 480))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Run the dlib HOG face detector on the grayscale frame.
                rects = self.img_proc.detector(gray, 0)

                # Default state: no face detected is treated as distraction.
                is_distracted = len(rects) == 0
                is_fatigued = False
                ear, yaw, pitch = 0.0, 0.0, 0.0
                self.total_frames_in_minute += 1

                # --- Computer Vision Processing ---
                if not is_distracted:
                    # Extract the 68 facial landmark coordinates.
                    shape = face_utils.shape_to_np(self.img_proc.predictor(gray, rects[0]))
                    
                    # Compute EAR for each eye and average them.
                    leftEAR = self.img_proc.calculate_ear(shape[lS:lE])
                    rightEAR = self.img_proc.calculate_ear(shape[rS:rE])
                    ear = (leftEAR + rightEAR) / 2.0

                    # Estimate head orientation from the landmark geometry.
                    yaw, pitch = self.img_proc.get_head_pose(shape, 480, 640)

                    thresh = self.config['thresholds']
                    
                    # Increment the closed-eye frame counter for PERCLOS calculation.
                    if ear < thresh['ear']:
                        self.eye_closed_frames += 1
                    
                    # PERCLOS: percentage of frames with closed eyes in the current window.
                    perclos = (self.eye_closed_frames / self.total_frames_in_minute) * 100
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

                self.video_out.write(frame)

                # --- Telemetry Transmission (1 Hz) ---
                if time.time() - last_telemetry_time > 1.0:
                    perclos = (self.eye_closed_frames / self.total_frames_in_minute) * 100
                    lat, lon = self.gps.get_location()
                    
                    self.backend.send_telemetry(ear, perclos, is_distracted, yaw, pitch, lat, lon)
                    
                    # Log level reflects the current driver state for easy monitoring.
                    log_lvl = "ERROR" if is_fatigued else ("WARNING" if is_distracted else "DEBUG")
                    self.logger.log(log_lvl, f"EAR:{ear:.2f} | PERCLOS:{perclos:.1f}% | Yaw:{yaw:.1f}")
                    
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
        
        if self.video_out: 
            self.video_out.release()
            self.logger.log("INFO", "Video saved locally.")

        self.gps.stop()
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
