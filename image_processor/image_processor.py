import sys
import os
import numpy as np
import cv2
import dlib
from scipy.spatial import distance as dist
from imutils import face_utils

# Fix import path for running standalone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class ImageProcessor:
    """
    Handles Camera IO, Computer Vision algorithms (EAR, Pose), and Visual Feedback.
    """

    def __init__(self, predictor_path=None, camera_index=0):
        """
        Args:
            predictor_path (str): Path to the dlib shape predictor file.
            camera_index (int): Camera device index (usually 0).
        """
        self.cap = None
        self.camera_index = camera_index
        
        # Initialize AI Models if path is provided
        if predictor_path:
            self.detector = dlib.get_frontal_face_detector()
            self.predictor = dlib.shape_predictor(predictor_path)
        else:
            self.detector = None
            self.predictor = None

        # Camera Matrix Cache
        self.camera_matrix = None
        self.dist_coeffs = np.zeros((4, 1))

    def setup_camera(self):
        """Initializes the camera connection."""
        print(f"[ImageProcessor] Connecting to camera {self.camera_index}...")
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2) # Try V4L2 for Linux
        
        # Fallback if V4L2 fails
        if not self.cap.isOpened():
             self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            raise IOError("Cannot open webcam")
        
        return self.cap

    def get_frame(self):
        """Reads a single frame from the camera."""
        if not self.cap:
            return False, None
        return self.cap.read()

    def release_camera(self):
        """Releases the camera resource."""
        if self.cap:
            self.cap.release()

    @staticmethod
    def calculate_ear(eye_points):
        """Calculates Eye Aspect Ratio (EAR)."""
        A = dist.euclidean(eye_points[1], eye_points[5])
        B = dist.euclidean(eye_points[2], eye_points[4])
        C = dist.euclidean(eye_points[0], eye_points[3])
        return (A + B) / (2.0 * C)

    def get_head_pose(self, shape, img_h, img_w):
        """Estimates Head Pose (Yaw, Pitch) using SolvePnP."""
        # 3D Model Points
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left Mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ], dtype="double")

        # 2D Image Points
        image_points = np.array([
            shape[30], shape[8], shape[36], shape[45], shape[48], shape[54]
        ], dtype="double")

        # Initialize Camera Matrix once
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

        rotation_matrix, _ = cv2.Rodrigues(vector_rotation)
        projection_matrix = np.hstack((rotation_matrix, vector_translation))
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(projection_matrix)
        
        pitch, yaw, roll = [element.item() for element in euler_angles]
        return yaw, pitch

    def draw_feedback(self, frame, rect, color, label):
        """Draws the bounding box and status label on the frame."""
        (x, y, w, h) = face_utils.rect_to_bb(rect)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame

# --- LIVE TEST MODE ---
if __name__ == "__main__":
    print("Starting Live Camera Test...")
    print("IMPORTANT: Click on the Video Window for 'q' to work!") # Added tip
    print("Press 'q' to quit.")
    
    PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
    OUTPUT_FILE = "test_output.avi" # <--- Change to .avi
    
    if not os.path.exists(PREDICTOR_PATH):
        print(f"Error: {PREDICTOR_PATH} not found.")
        sys.exit(1)

    processor = ImageProcessor(PREDICTOR_PATH)
    try:
        processor.setup_camera()
    except Exception as e:
        print(f"Camera Error: {e}")
        sys.exit(1)
    
    # --- CHANGE TO MJPG (Robust & Safe) ---
    fourcc = cv2.VideoWriter_fourcc(*'MJPG') 
    out_writer = cv2.VideoWriter(OUTPUT_FILE, fourcc, 10.0, (640, 480))
    print(f"Recording video to: {os.path.abspath(OUTPUT_FILE)}")

    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    frame_count = 0

    try:
        while True:
            ret, frame = processor.get_frame()
            if not ret: break

            # Force resize
            frame = cv2.resize(frame, (640, 480))
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = processor.detector(gray, 0)

            for rect in rects:
                shape = face_utils.shape_to_np(processor.predictor(gray, rect))
                leftEAR = processor.calculate_ear(shape[lS:lE])
                rightEAR = processor.calculate_ear(shape[rS:rE])
                ear = (leftEAR + rightEAR) / 2.0
                yaw, pitch = processor.get_head_pose(shape, 480, 640)

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
            
            # Check for 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n'q' pressed - Stopping safely...")
                break
                
    except KeyboardInterrupt:
        print("\nCtrl+C detected - Stopping safely...")
    finally:
        processor.release_camera()
        if out_writer:
            out_writer.release() # This writes the file footer
            print("Video writer released.")
            
        cv2.destroyAllWindows()
        
        if os.path.exists(OUTPUT_FILE):
            size = os.path.getsize(OUTPUT_FILE)
            print(f"Session ended. Video file size: {size} bytes")