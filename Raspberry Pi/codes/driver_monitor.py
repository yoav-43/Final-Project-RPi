import cv2
import dlib
import numpy as np
from scipy.spatial import distance as dist
from imutils import face_utils
import requests
import time
import threading
import sys
import atexit

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# Base URL for the Heroku Server
BASE_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api"
DEVICE_ID = "raspi_v1"

# Thresholds
EAR_THRESHOLD = 0.25   # Eye Aspect Ratio threshold (Closing eyes)
MAR_THRESHOLD = 0.6    # Mouth Aspect Ratio threshold (Yawning)
HEAD_YAW_LIMIT = 20    # Degrees for head turning (Distraction)
HEAD_PITCH_LIMIT = -15 # Degrees for head nodding (Sleepiness)

# Dlib Model Path
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"

# Global Session ID
CURRENT_DRIVE_ID = None

# -----------------------------------------------------------------------------
# SESSION MANAGEMENT
# -----------------------------------------------------------------------------

def start_new_drive_session():
    """
    Contacts the server to create a new drive session in the database.
    Returns: The drive_id (int) or None on failure.
    """
    try:
        print("[INFO] Contacting server to initiate drive session...")
        payload = {"device_id": DEVICE_ID}
        response = requests.post(f"{BASE_URL}/start_drive", json=payload, timeout=5)
        
        if response.status_code == 201:
            data = response.json()
            drive_id = data.get("drive_id")
            print(f"[SUCCESS] Session Started. Drive ID: {drive_id}")
            return drive_id
        else:
            print(f"[ERROR] Server refused session start. Code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network error starting session: {e}")
        return None

def close_drive_session():
    """
    Sends a signal to the server to mark the session as finished (sets end_time).
    Registered with atexit to run when the script stops.
    """
    global CURRENT_DRIVE_ID
    if CURRENT_DRIVE_ID is not None:
        print(f"[INFO] Closing Drive Session #{CURRENT_DRIVE_ID}...")
        try:
            requests.post(f"{BASE_URL}/end_drive", json={"drive_id": CURRENT_DRIVE_ID}, timeout=2)
            print("[SUCCESS] Session Closed.")
        except:
            print("[WARN] Failed to close session cleanly (Network issue).")

# Register cleanup function to run on exit
atexit.register(close_drive_session)

# -----------------------------------------------------------------------------
# MATH & GEOMETRY FUNCTIONS
# -----------------------------------------------------------------------------

model_points = np.array([
    (0.0, 0.0, 0.0),             # Nose tip
    (0.0, -330.0, -65.0),        # Chin
    (-225.0, 170.0, -135.0),     # Left eye left corner
    (225.0, 170.0, -135.0),      # Right eye right corner
    (-150.0, -150.0, -125.0),    # Left Mouth corner
    (150.0, -150.0, -125.0)      # Right mouth corner
], dtype="double")

def calculate_ear(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def calculate_mar(mouth):
    A = dist.euclidean(mouth[2], mouth[10])
    B = dist.euclidean(mouth[4], mouth[8])
    C = dist.euclidean(mouth[0], mouth[6])
    return (A + B) / (2.0 * C)

def get_head_pose(shape, img_h, img_w):
    image_points = np.array([
        shape[30], shape[8], shape[36], shape[45], shape[48], shape[54]
    ], dtype="double")

    focal_length = img_w
    center = (img_w / 2, img_h / 2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype="double")
    dist_coeffs = np.zeros((4, 1))

    (success, rotation_vector, translation_vector) = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
    )

    rmat, _ = cv2.Rodrigues(rotation_vector)
    sy = np.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
    
    if sy < 1e-6:
        x = np.arctan2(-rmat[1, 2], rmat[1, 1])
        y = np.arctan2(-rmat[2, 0], sy)
        z = 0
    else:
        x = np.arctan2(rmat[2, 1], rmat[2, 2])
        y = np.arctan2(-rmat[2, 0], sy)
        z = np.arctan2(rmat[1, 0], rmat[0, 0])

    return np.degrees(y), np.degrees(x), np.degrees(z) # Yaw, Pitch, Roll

# -----------------------------------------------------------------------------
# TELEMETRY UPLOAD
# -----------------------------------------------------------------------------
def send_data_thread(payload):
    try:
        requests.post(f"{BASE_URL}/telemetry", json=payload, timeout=2)
    except requests.exceptions.RequestException:
        pass

# -----------------------------------------------------------------------------
# MAIN MONITORING LOOP
# -----------------------------------------------------------------------------
def start_monitoring():
    global CURRENT_DRIVE_ID
    
    # 1. Initialize Drive Session
    CURRENT_DRIVE_ID = start_new_drive_session()
    if CURRENT_DRIVE_ID is None:
        print("[CRITICAL] Could not start session. Exiting.")
        sys.exit(1)

    print("[INFO] Loading Dlib predictor...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)

    print("[INFO] Starting Camera...")
    cap = cv2.VideoCapture(0)
    
    (lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
    (mStart, mEnd) = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]

    frame_counter = 0
    closed_frames = 0
    last_send_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame = cv2.resize(frame, (640, 480))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        img_h, img_w = frame.shape[:2]

        rects = detector(gray, 0)
        
        # Telemetry variables
        is_distracted = False
        ear = 0.0
        mar = 0.0
        yaw, pitch, roll = 0.0, 0.0, 0.0

        if len(rects) == 0:
            is_distracted = True
            cv2.putText(frame, "NO FACE", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        else:
            for rect in rects:
                shape = predictor(gray, rect)
                shape_np = face_utils.shape_to_np(shape)
                
                # Head Pose
                yaw, pitch, roll = get_head_pose(shape_np, img_h, img_w)
                if abs(yaw) > HEAD_YAW_LIMIT or pitch < HEAD_PITCH_LIMIT:
                    is_distracted = True
                    cv2.putText(frame, "DISTRACTED", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

                # Eye/Mouth Metrics
                leftEye = shape_np[lStart:lEnd]
                rightEye = shape_np[rStart:rEnd]
                mouth = shape_np[mStart:mEnd]
                
                ear = (calculate_ear(leftEye) + calculate_ear(rightEye)) / 2.0
                mar = calculate_mar(mouth)

                if ear < EAR_THRESHOLD:
                    closed_frames += 1
                    cv2.putText(frame, "DROWSY", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        # Transmission Logic
        frame_counter += 1
        current_time = time.time()
        
        if current_time - last_send_time > 1.0:
            perclos_score = (closed_frames / frame_counter) * 100 if frame_counter > 0 else 0
            
            payload = {
                "drive_id": CURRENT_DRIVE_ID,
                "device_id": DEVICE_ID,
                "ear": round(ear, 3),
                "mar": round(mar, 3),
                "perclos": round(perclos_score, 2),
                "is_distracted": is_distracted,
                "head_yaw": round(yaw, 2),
                "head_pitch": round(pitch, 2),
                "head_roll": round(roll, 2)
            }
            
            threading.Thread(target=send_data_thread, args=(payload,)).start()
            
            frame_counter = 0
            closed_frames = 0
            last_send_time = current_time

        cv2.imshow("Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_monitoring()