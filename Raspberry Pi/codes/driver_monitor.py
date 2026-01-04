import cv2
import dlib
import numpy as np
from scipy.spatial import distance as dist
from imutils import face_utils
import requests
import time
import threading

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
SERVER_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api/telemetry"
DEVICE_ID = "raspi_v1"

# Scientific Thresholds (Based on research papers)
EAR_THRESHOLD = 0.25   # Eye Aspect Ratio < 0.25 implies closed eyes
MAR_THRESHOLD = 0.6    # Mouth Aspect Ratio > 0.6 implies yawning

# Path to Dlib's pre-trained model (Must be in the same folder)
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"

# -----------------------------------------------------------------------------
# 3D Model Points (Generic Human Face) for Head Pose Estimation (PnP)
# -----------------------------------------------------------------------------
model_points = np.array([
    (0.0, 0.0, 0.0),             # Nose tip
    (0.0, -330.0, -65.0),        # Chin
    (-225.0, 170.0, -135.0),     # Left eye left corner
    (225.0, 170.0, -135.0),      # Right eye right corner
    (-150.0, -150.0, -125.0),    # Left Mouth corner
    (150.0, -150.0, -125.0)      # Right mouth corner
], dtype="double")

# -----------------------------------------------------------------------------
# Mathematical Helper Functions
# -----------------------------------------------------------------------------

def calculate_ear(eye):
    """
    Calculates the Eye Aspect Ratio (EAR) to detect blinking/closed eyes.
    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
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
    Calculates the Mouth Aspect Ratio (MAR) to detect yawning.
    """
    # Vertical distances (inner lip)
    A = dist.euclidean(mouth[2], mouth[10]) # Points 51, 59
    B = dist.euclidean(mouth[4], mouth[8])  # Points 53, 57
    # Horizontal distance
    C = dist.euclidean(mouth[0], mouth[6])  # Points 49, 55
    
    mar = (A + B) / (2.0 * C)
    return mar

def get_head_pose(shape, img_h, img_w):
    """
    Calculates Head Pose (Yaw, Pitch, Roll) using solvePnP.
    Returns: yaw, pitch, roll angles and the nose endpoint for visualization.
    """
    # 2D image points from Dlib (Specific landmarks matching the 3D model)
    image_points = np.array([
        shape[30],     # Nose tip
        shape[8],      # Chin
        shape[36],     # Left eye left corner
        shape[45],     # Right eye right corner
        shape[48],     # Left Mouth corner
        shape[54]      # Right mouth corner
    ], dtype="double")

    # Camera internals approximation
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

    # Project a 3D point (nose direction) onto the 2D image for visualization
    (nose_end_point2D, jacobian) = cv2.projectPoints(
        np.array([(0.0, 0.0, 1000.0)]), 
        rotation_vector, translation_vector, camera_matrix, dist_coeffs
    )

    # Convert Rotation Vector to Rotation Matrix to getting Euler Angles
    rmat, jac = cv2.Rodrigues(rotation_vector)
    
    # Calculate Euler Angles (Yaw, Pitch, Roll)
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

    # Convert to degrees
    pitch = np.degrees(x)
    yaw = np.degrees(y)
    roll = np.degrees(z)

    return yaw, pitch, roll, nose_end_point2D

# -----------------------------------------------------------------------------
# Networking Function (Background Thread)
# -----------------------------------------------------------------------------
def send_data_thread(payload):
    """
    Sends data to the cloud server in a separate thread.
    This prevents the video feed from freezing while waiting for the server.
    """
    try:
        requests.post(SERVER_URL, json=payload, timeout=2)
        # print("[Network] Data sent successfully") # Uncomment for debug
    except requests.exceptions.RequestException:
        print("[Network] Error: Could not connect to server.")

# -----------------------------------------------------------------------------
# Main System Loop
# -----------------------------------------------------------------------------
def start_monitoring():
    print("[INFO] Loading facial landmark predictor...")
    # Initialize Dlib's face detector and shape predictor
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)

    print("[INFO] Starting video stream...")
    cap = cv2.VideoCapture(0) # 0 is usually the default USB webcam
    
    # Indices for eyes and mouth in the 68-point model
    (lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
    (mStart, mEnd) = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]

    # Variables for PERCLOS calculation
    frame_counter = 0
    closed_frames = 0
    perclos_score = 0
    last_send_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[Error] Failed to read from camera.")
            break
        
        # Get dimensions and resize
        img_h, img_w = frame.shape[:2]
        frame = cv2.resize(frame, (640, 480))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        rects = detector(gray, 0)
        
        # Initialize metrics for this frame
        is_distracted = False 
        ear = 0.0
        mar = 0.0
        yaw = 0.0
        pitch = 0.0
        
        # If no face is detected, we assume distraction (looking away completely)
        if len(rects) == 0:
            is_distracted = True
            cv2.putText(frame, "NO FACE / DISTRACTED", (10, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        for rect in rects:
            # Get landmarks
            shape = predictor(gray, rect)
            shape_np = face_utils.shape_to_np(shape) 
            
            # --- 1. Head Pose Estimation (Distraction) ---
            yaw, pitch, roll, nose_point = get_head_pose(shape_np, img_h, img_w)

            # Draw direction line (Visualizing gaze)
            p1 = (int(shape_np[30][0]), int(shape_np[30][1])) # Nose tip
            p2 = (int(nose_point[0][0][0]), int(nose_point[0][0][1])) # Projected point
            cv2.line(frame, p1, p2, (255, 0, 0), 2)

            # Distraction Logic: 
            # Yaw > 20 deg (Turning head L/R) OR Pitch < -15 deg (Looking down at phone)
            if abs(yaw) > 20 or pitch < -15:
                is_distracted = True
                cv2.putText(frame, "DISTRACTED!", (10, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
            # --- 2. Fatigue Logic (EAR/MAR/PERCLOS) ---
            leftEye = shape_np[lStart:lEnd]
            rightEye = shape_np[rStart:rEnd]
            mouth = shape_np[mStart:mEnd]
            
            leftEAR = calculate_ear(leftEye)
            rightEAR = calculate_ear(rightEye)
            ear = (leftEAR + rightEAR) / 2.0
            mar = calculate_mar(mouth)
            
            # Draw contours on eyes/mouth
            leftEyeHull = cv2.convexHull(leftEye)
            rightEyeHull = cv2.convexHull(rightEye)
            mouthHull = cv2.convexHull(mouth)
            cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [mouthHull], -1, (0, 255, 0), 1)
            
            # Instantaneous warnings
            if ear < EAR_THRESHOLD:
                closed_frames += 1
                cv2.putText(frame, "EYES CLOSED", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            if mar > MAR_THRESHOLD:
                cv2.putText(frame, "YAWNING", (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # --- Data Transmission Logic ---
        frame_counter += 1
        current_time = time.time()
        
        # Send data approximately every 1 second
        if current_time - last_send_time > 1.0:
            if frame_counter > 0:
                # Calculate PERCLOS: Percentage of frames where eyes were closed
                perclos_score = (closed_frames / frame_counter) * 100
            
            # Prepare JSON payload
            payload = {
                "device_id": DEVICE_ID,
                "ear": round(ear, 3),
                "mar": round(mar, 3),
                "perclos": round(perclos_score, 2),
                "is_distracted": is_distracted,
                "head_yaw": round(yaw, 2)
            }
            
            # Start a background thread to send data (non-blocking)
            threading.Thread(target=send_data_thread, args=(payload,)).start()
            
            # Reset counters for the next time window
            frame_counter = 0
            closed_frames = 0
            last_send_time = current_time

        # Display the video feed
        cv2.imshow("Driver Monitoring System", frame)
        
        # Press 'q' to exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_monitoring()