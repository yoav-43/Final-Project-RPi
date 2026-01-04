import cv2
import dlib
import numpy as np
from scipy.spatial import distance as dist
from imutils import face_utils
import requests
import time
import threading

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# !!! REPLACE WITH YOUR ACTUAL HEROKU URL !!!
SERVER_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api/telemetry"
DEVICE_ID = "raspi_v1"

# Scientific Thresholds (Derived from Research)
EAR_THRESHOLD = 0.25   # Eyes considered closed below this ratio
MAR_THRESHOLD = 0.6    # Mouth considered open (yawning) above this ratio

# Path to the Dlib Shape Predictor (Must exist in the same folder)
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"

# -----------------------------------------------------------------------------
# 3D MODEL POINTS (For Head Pose Estimation)
# -----------------------------------------------------------------------------
# Generic 3D coordinates of facial features
model_points = np.array([
    (0.0, 0.0, 0.0),             # Nose tip
    (0.0, -330.0, -65.0),        # Chin
    (-225.0, 170.0, -135.0),     # Left eye left corner
    (225.0, 170.0, -135.0),      # Right eye right corner
    (-150.0, -150.0, -125.0),    # Left Mouth corner
    (150.0, -150.0, -125.0)      # Right mouth corner
], dtype="double")

# -----------------------------------------------------------------------------
# MATH HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def calculate_ear(eye):
    """
    Computes Eye Aspect Ratio (EAR) to detect blinking.
    """
    # Vertical distances
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    # Horizontal distance
    C = dist.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C)
    return ear

def calculate_mar(mouth):
    """
    Computes Mouth Aspect Ratio (MAR) to detect yawning.
    """
    # Vertical distances
    A = dist.euclidean(mouth[2], mouth[10]) 
    B = dist.euclidean(mouth[4], mouth[8])  
    # Horizontal distance
    C = dist.euclidean(mouth[0], mouth[6])  
    mar = (A + B) / (2.0 * C)
    return mar

def get_head_pose(shape, img_h, img_w):
    """
    Solves the Perspective-n-Point (PnP) problem to find head orientation.
    Returns: Yaw, Pitch, Roll (in degrees) and the nose tip coordinate.
    """
    # 2D image points from Dlib (Specific landmarks matching 3D model)
    image_points = np.array([
        shape[30],     # Nose tip
        shape[8],      # Chin
        shape[36],     # Left eye left corner
        shape[45],     # Right eye right corner
        shape[48],     # Left Mouth corner
        shape[54]      # Right mouth corner
    ], dtype="double")

    # Camera internals (Approximation based on image size)
    focal_length = img_w
    center = (img_w / 2, img_h / 2)
    camera_matrix = np.array(
        [[focal_length, 0, center[0]],
         [0, focal_length, center[1]],
         [0, 0, 1]], dtype="double"
    )
    dist_coeffs = np.zeros((4, 1)) # Assuming no lens distortion

    # Solve PnP
    (success, rotation_vector, translation_vector) = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
    )

    # Project a 3D point (forward from nose) for visualization
    (nose_end_point2D, jacobian) = cv2.projectPoints(
        np.array([(0.0, 0.0, 1000.0)]), 
        rotation_vector, translation_vector, camera_matrix, dist_coeffs
    )

    # Convert Rotation Vector to Rotation Matrix
    rmat, jac = cv2.Rodrigues(rotation_vector)
    
    # Decompose Projection Matrix to Euler Angles
    sy = np.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
    singular = sy < 1e-6

    if not singular:
        x = np.arctan2(rmat[2, 1], rmat[2, 2])
        y = np.arctan2(-rmat[2, 0], sy)
        z = np.arctan2(rmat[1, 0], rmat[0, 0])
    else:
        x = np.arctan2(-rmat[1, 2], rmat[1, 1])
        y = np.arctan2(-rmat[2, 0], sy)
        z = 0

    # Convert radians to degrees
    pitch = np.degrees(x)
    yaw = np.degrees(y)
    roll = np.degrees(z)

    return yaw, pitch, roll, nose_end_point2D

# -----------------------------------------------------------------------------
# NETWORK THREAD
# -----------------------------------------------------------------------------
def send_data_thread(payload):
    """
    Transmits JSON payload to server in a background thread to avoid lag.
    """
    try:
        requests.post(SERVER_URL, json=payload, timeout=2)
    except requests.exceptions.RequestException:
        pass # Ignore network errors to keep video smooth

# -----------------------------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------------------------
def start_monitoring():
    print("[INFO] Loading facial landmark predictor...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)

    print("[INFO] Starting video stream...")
    cap = cv2.VideoCapture(0)
    
    # Landmark indices
    (lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
    (mStart, mEnd) = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]

    # Metrics Accumulators
    frame_counter = 0
    closed_frames = 0
    perclos_score = 0
    last_send_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[Error] Camera failure.")
            break
        
        # Preprocessing
        img_h, img_w = frame.shape[:2]
        frame = cv2.resize(frame, (640, 480))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        rects = detector(gray, 0)
        
        # Default Values (if no face detected)
        is_distracted = False 
        ear = 0.0
        mar = 0.0
        yaw = 0.0
        pitch = 0.0
        roll = 0.0
        
        # Check for Face Presence (Distraction Level 1)
        if len(rects) == 0:
            is_distracted = True
            cv2.putText(frame, "NO FACE DETECTED", (10, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        for rect in rects:
            shape = predictor(gray, rect)
            shape_np = face_utils.shape_to_np(shape)
            
            # --- 1. HEAD POSE ESTIMATION ---
            yaw, pitch, roll, nose_point = get_head_pose(shape_np, img_h, img_w)

            # Draw visual gaze vector
            p1 = (int(shape_np[30][0]), int(shape_np[30][1]))
            p2 = (int(nose_point[0][0][0]), int(nose_point[0][0][1]))
            cv2.line(frame, p1, p2, (255, 0, 0), 2)

            # Distraction Logic (Thresholds: Yaw > 20, Pitch < -15)
            if abs(yaw) > 20 or pitch < -15:
                is_distracted = True
                cv2.putText(frame, "DISTRACTED!", (10, 120), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
            # --- 2. FATIGUE METRICS ---
            leftEye = shape_np[lStart:lEnd]
            rightEye = shape_np[rStart:rEnd]
            mouth = shape_np[mStart:mEnd]
            
            leftEAR = calculate_ear(leftEye)
            rightEAR = calculate_ear(rightEye)
            ear = (leftEAR + rightEAR) / 2.0
            mar = calculate_mar(mouth)
            
            # Visual Feedback
            leftEyeHull = cv2.convexHull(leftEye)
            rightEyeHull = cv2.convexHull(rightEye)
            mouthHull = cv2.convexHull(mouth)
            cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [mouthHull], -1, (0, 255, 0), 1)
            
            if ear < EAR_THRESHOLD:
                closed_frames += 1
                cv2.putText(frame, "EYES CLOSED", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            if mar > MAR_THRESHOLD:
                cv2.putText(frame, "YAWNING", (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # --- DATA TRANSMISSION ---
        frame_counter += 1
        current_time = time.time()
        
        # Send telemetry every ~1.0 second
        if current_time - last_send_time > 1.0:
            if frame_counter > 0:
                perclos_score = (closed_frames / frame_counter) * 100
            
            # Construct Payload with all metrics
            payload = {
                "device_id": DEVICE_ID,
                "ear": round(ear, 3),
                "mar": round(mar, 3),
                "perclos": round(perclos_score, 2),
                "is_distracted": is_distracted,
                "head_yaw": round(yaw, 2),
                "head_pitch": round(pitch, 2),
                "head_roll": round(roll, 2)
            }
            
            # Send to cloud in background
            threading.Thread(target=send_data_thread, args=(payload,)).start()
            
            # Reset counters
            frame_counter = 0
            closed_frames = 0
            last_send_time = current_time

        cv2.imshow("Driver Monitoring System", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_monitoring()