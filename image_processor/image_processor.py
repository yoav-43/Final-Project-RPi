import sys
import os
import numpy as np
import cv2
import dlib
from scipy.spatial import distance as dist
from imutils import face_utils

# Allow standalone execution from any working directory.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class ImageProcessor:
    """
    Encapsulates all computer vision operations for the WakeUp system:
    camera I/O, Eye Aspect Ratio (EAR) computation, head pose estimation
    via solvePnP, and visual feedback rendering.
    """

    def __init__(self, predictor_path=None, camera_index=0, night_vision=False):
        """
        Args:
            predictor_path (str): Path to the dlib 68-point shape predictor model file.
                                  If None, the detector and predictor are not loaded.
            camera_index (int): OpenCV camera device index (default: 0).
            night_vision (bool): If True, drives GPIO17 LOW (IR-CUT filter open, night mode).
                                 If False (default), drives GPIO17 HIGH (IR-CUT filter active, day mode).
        """
        self.cap = None
        self.camera_index = camera_index
        self.night_vision = night_vision
        
        # Load the dlib face detector and landmark predictor if a model path is provided.
        if predictor_path:
            self.detector = dlib.get_frontal_face_detector()
            self.predictor = dlib.shape_predictor(predictor_path)
        else:
            self.detector = None
            self.predictor = None

        # Camera matrix is computed once on the first pose estimation call and cached.
        self.camera_matrix = None
        self.dist_coeffs = np.zeros((4, 1))
        # CLAHE for low-light / IR contrast enhancement.
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def setup_camera(self):
        """
        Opens the CSI camera via picamera2 (libcamera backend).

        Raises:
            IOError: If the camera cannot be opened.
        """
        import RPi.GPIO as GPIO
        from picamera2 import Picamera2
        print(f"[ImageProcessor] Connecting to CSI camera via picamera2...")

        # Drive GPIO17 to control the IR-CUT filter.
        # HIGH = normal color mode (IR-CUT filter active)
        # LOW  = night-vision mode (IR-CUT filter open, IR LEDs illuminate)
        self._ir_cut_pin = 17
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._ir_cut_pin, GPIO.OUT)
        gpio_state = GPIO.LOW if self.night_vision else GPIO.HIGH
        GPIO.output(self._ir_cut_pin, gpio_state)
        mode_label = "night-vision" if self.night_vision else "day"
        print(f"[ImageProcessor] IR-CUT filter: {mode_label} mode (GPIO17={'LOW' if self.night_vision else 'HIGH'})")

        self.cap = Picamera2(tuning=Picamera2.load_tuning_file("/usr/share/libcamera/ipa/rpi/vc4/ov5647_noir.json"))
        self.cap.configure(self.cap.create_preview_configuration(
            main={"format": "BGR888", "size": (1296, 972)}
        ))
        self.cap.start()
        return self.cap

    def get_frame(self):
        """Reads a single frame from the active camera capture device."""
        if not self.cap:
            return False, None
        frame = self.cap.capture_array()
        # picamera2 BGR888 outputs RGB order on this sensor — swap to BGR for OpenCV.
        return True, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def release_camera(self):
        """Releases the camera capture device and frees the associated resources."""
        if self.cap:
            self.cap.stop()
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup(self._ir_cut_pin)
        except Exception:
            pass

    @staticmethod
    def calculate_ear(eye_points):
        """
        Computes the Eye Aspect Ratio (EAR) for a single eye.

        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

        where p1..p6 are the six landmark points of the eye in order.
        A value below 0.18 (configurable via config.json) indicates a closed eye.

        Args:
            eye_points (np.ndarray): Array of 6 (x, y) landmark coordinates.

        Returns:
            float: The computed EAR value.
        """
        A = dist.euclidean(eye_points[1], eye_points[5])
        B = dist.euclidean(eye_points[2], eye_points[4])
        C = dist.euclidean(eye_points[0], eye_points[3])
        return (A + B) / (2.0 * C)

    def get_head_pose(self, shape, img_h, img_w):
        """
        Estimates head orientation (yaw, pitch) using the Perspective-n-Point
        (PnP) algorithm with a generic 3D face model.

        Maps 6 stable facial landmarks (nose tip, chin, eye corners, mouth
        corners) to their known 3D positions, then solves for the rotation
        vector via cv2.solvePnP. The rotation vector is decomposed into
        Euler angles using cv2.decomposeProjectionMatrix.

        Args:
            shape (np.ndarray): 68x2 array of facial landmark coordinates.
            img_h (int): Frame height in pixels.
            img_w (int): Frame width in pixels.

        Returns:
            tuple: (yaw, pitch) in degrees.
        """
        # Generic 3D face model reference points (in millimetres).
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ], dtype="double")

        # Corresponding 2D landmark indices from the 68-point model.
        image_points = np.array([
            shape[30], shape[8], shape[36], shape[45], shape[48], shape[54]
        ], dtype="double")

        # Build a pinhole camera matrix using focal_length ≈ image_width (approximation).
        if self.camera_matrix is None:
            focal_length = img_w
            center = (img_w / 2, img_h / 2)
            self.camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype="double")

        success, vector_rotation, vector_translation = cv2.solvePnP(
            model_points, image_points, self.camera_matrix, self.dist_coeffs
        )

        # Convert the rotation vector to a rotation matrix, then extract Euler angles.
        rotation_matrix, _ = cv2.Rodrigues(vector_rotation)
        projection_matrix = np.hstack((rotation_matrix, vector_translation))
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(projection_matrix)
        
        pitch, yaw, roll = [element.item() for element in euler_angles]
        # decomposeProjectionMatrix can return pitch near ±180° for a forward-facing head.
        # Normalize to the equivalent angle near 0°.
        if pitch > 90:
            pitch -= 180
        elif pitch < -90:
            pitch += 180
        pitch = -pitch  # Negate: looking down should be negative, straight ahead near 0.
        return yaw, pitch

    def draw_stats_overlay(self, frame, ear, perclos, yaw, pitch, fps, thresholds):
        """
        Renders a live stats legend in the top-left corner of the frame.
        Each stat is colored green (OK) or red (violation).
        """
        stats = [
            ("EAR",     f"{ear:.2f}",     ear >= thresholds['ear']),
            ("PERCLOS", f"{perclos:.1f}%", perclos <= thresholds['perclos_fatigue_limit']),
            ("Yaw",     f"{yaw:.1f}deg",  abs(yaw) <= thresholds['head_yaw']),
            ("Pitch",   f"{pitch:.1f}deg", pitch >= thresholds['head_pitch']),
            ("FPS",     f"{fps:.1f}",     True),
        ]
        for i, (name, value, ok) in enumerate(stats):
            color = (0, 255, 0) if ok else (0, 0, 255)
            cv2.putText(frame, f"{name}: {value}", (10, 25 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    def draw_feedback(self, frame, rect, color, label):
        """
        Renders a bounding box and status label over the detected face region.

        Args:
            frame (np.ndarray): The BGR video frame to annotate.
            rect (dlib.rectangle): The face bounding rectangle from the detector.
            color (tuple): BGR color for the box and label.
            label (str): Status text to display above the bounding box.

        Returns:
            np.ndarray: The annotated frame.
        """
        (x, y, w, h) = face_utils.rect_to_bb(rect)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame

# --- Standalone Live Test ---
if __name__ == "__main__":
    print("Starting Live Camera Test...")
    print("IMPORTANT: Click on the Video Window for 'q' to work!")
    print("Press 'q' to quit.")
    
    PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
    OUTPUT_FILE = "test_output.avi"
    
    if not os.path.exists(PREDICTOR_PATH):
        print(f"Error: {PREDICTOR_PATH} not found.")
        sys.exit(1)

    processor = ImageProcessor(PREDICTOR_PATH)
    try:
        processor.setup_camera()
    except Exception as e:
        print(f"Camera Error: {e}")
        sys.exit(1)
    
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out_writer = cv2.VideoWriter(OUTPUT_FILE, fourcc, 10.0, (1296, 972))
    print(f"Recording video to: {os.path.abspath(OUTPUT_FILE)}")

    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    frame_count = 0

    try:
        while True:
            ret, frame = processor.get_frame()
            if not ret: break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = processor.detector(gray, 0)

            for rect in rects:
                shape = face_utils.shape_to_np(processor.predictor(gray, rect))
                leftEAR = processor.calculate_ear(shape[lS:lE])
                rightEAR = processor.calculate_ear(shape[rS:rE])
                ear = (leftEAR + rightEAR) / 2.0
                yaw, pitch = processor.get_head_pose(shape, 972, 1296)

                if ear < 0.25:
                    color, status = (0, 0, 255), f"SLEEPING! ({ear:.2f})"
                elif abs(yaw) > 20:
                    color, status = (0, 255, 255), f"DISTRACTED ({yaw:.1f})"
                else:
                    color, status = (0, 255, 0), "FOCUSED"

                processor.draw_feedback(frame, rect, color, status)
            
            out_writer.write(frame)
            frame_count += 1
            if frame_count % 30 == 0:
                print(f"Recorded {frame_count} frames...", end='\r')

            cv2.imshow("Live Test", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n'q' pressed - Stopping safely...")
                break
                
    except KeyboardInterrupt:
        print("\nCtrl+C detected - Stopping safely...")
    finally:
        processor.release_camera()
        if out_writer:
            out_writer.release()
            print("Video writer released.")
            
        cv2.destroyAllWindows()
        
        if os.path.exists(OUTPUT_FILE):
            size = os.path.getsize(OUTPUT_FILE)
            print(f"Session ended. Video file size: {size} bytes")
