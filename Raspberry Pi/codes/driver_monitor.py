"""
---------------------------------------------------------------------------------------
DRIVER MONITORING SYSTEM (CLIENT SIDE) - VERSION 2.0
---------------------------------------------------------------------------------------
Core Features:
    - Real-time Face Detection with visual Bounding Box.
    - Drowsiness (EAR) and Distraction (Head Pose) analysis.
    - Local MP4 Video Recording (Browser Compatible).
    - Automated Cloudinary Video Upload on session termination.
    - Non-blocking Telemetry Transmission via Threading.
    - Integrated Debugging and Information Logger.

Hardware: Raspberry Pi 4 + Camera Module
Backend: Flask (Heroku) + PostgreSQL
Cloud Storage: Cloudinary
---------------------------------------------------------------------------------------
"""

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
import cloudinary
import cloudinary.uploader
import os

# =============================================================================
# SYSTEM CONFIGURATION & CLOUDINARY SETUP
# =============================================================================

# API Endpoints
BASE_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api"
DEVICE_ID = "raspi_v1"

# Facial Landmark Model Path
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"

# Temporary Local Storage (MP4 for cross-browser support)
VIDEO_TEMP_FILE = "drive_video.mp4" 

# Cloudinary Credentials (REQUIRED: Replace with your keys)
cloudinary.config( 
  cloud_name = "dei1fd8k6", 
  api_key = "545933773654545", 
  api_secret = "434wCTl3T4jlwQKpjiX8Rp2Bc6s" 
)

# Detection Thresholds
EAR_THRESHOLD = 0.25
HEAD_YAW_LIMIT = 20
HEAD_PITCH_LIMIT = -15

# Global Session Objects
CURRENT_DRIVE_ID = None
video_out = None 

# =============================================================================
# LOGGING & DEBUGGING UTILITIES
# =============================================================================

def log_info(message):
    print(f"[INFO] {time.strftime('%H:%M:%S')} - {message}")

def log_debug(message):
    print(f"[DEBUG] {message}")

def log_error(message):
    print(f"[ERROR] !!! {message} !!!")

def log_success(message):
    print(f"[SUCCESS] {message}")

# =============================================================================
# NETWORK & CLOUD SYNCHRONIZATION
# =============================================================================

def finalize_and_upload():
    """
    [CLEANUP TASK]
    1. Stops the local video recording.
    2. Uploads the MP4 file to Cloudinary.
    3. Notifies the backend of the session end with the video URL.
    """
    global CURRENT_DRIVE_ID, video_out
    
    log_info("Termination signal received. Starting cleanup...")
    
    if video_out is not None:
        video_out.release()
        log_info("Local VideoWriter released.")

    if CURRENT_DRIVE_ID is None:
        log_error("No active session found. Skipping upload.")
        return

    video_url = None
    try:
        if os.path.exists(VIDEO_TEMP_FILE):
            log_info(f"Uploading {VIDEO_TEMP_FILE} to Cloudinary... (This may take a minute)")
            upload_result = cloudinary.uploader.upload(VIDEO_TEMP_FILE, resource_type="video")
            video_url = upload_result.get("secure_url")
            log_success(f"Video uploaded successfully. URL: {video_url}")
            
            # Remove temp file to free up RPi storage
            os.remove(VIDEO_TEMP_FILE)
            log_debug("Local temporary video file deleted.")
    except Exception as e:
        log_error(f"Cloudinary upload failed: {str(e)}")

    try:
        log_info(f"Closing session #{CURRENT_DRIVE_ID} on Heroku server...")
        payload = {"drive_id": CURRENT_DRIVE_ID, "video_url": video_url}
        response = requests.post(f"{BASE_URL}/end_drive", json=payload, timeout=20)
        
        if response.status_code == 200:
            log_success("Backend updated. Drive session successfully finalized.")
        else:
            log_error(f"Backend refused session end. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_error(f"Failed to communicate with backend: {str(e)}")

# Ensure cleanup runs on script exit (Ctrl+C or crash)
atexit.register(finalize_and_upload)

def send_telemetry_async(payload):
    """ Sends sensor data in a separate thread to avoid loop lag. """
    try:
        requests.post(f"{BASE_URL}/telemetry", json=payload, timeout=5)
    except:
        pass # Silently fail to keep the main monitoring loop smooth

# =============================================================================
# COMPUTER VISION HELPERS
# =============================================================================

def calculate_ear(eye):
    """ Computes EAR to detect eyelid closure. """
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def get_head_pose(shape, img_h, img_w):
    """ Estimates Yaw and Pitch using OpenCV's SolvePnP. """
    model_points = np.array([(0.0, 0.0, 0.0), (0.0, -330.0, -65.0), (-225.0, 170.0, -135.0),
                             (225.0, 170.0, -135.0), (-150.0, -150.0, -125.0), (150.0, -150.0, -125.0)], dtype="double")
    image_points = np.array([shape[30], shape[8], shape[36], shape[45], shape[48], shape[54]], dtype="double")
    camera_matrix = np.array([[img_w, 0, img_w/2], [0, img_w, img_h/2], [0, 0, 1]], dtype="double")
    _, rv, _ = cv2.solvePnP(model_points, image_points, camera_matrix, np.zeros((4, 1)))
    rmat, _ = cv2.Rodrigues(rv)
    yaw = np.degrees(np.arctan2(-rmat[2, 0], np.sqrt(rmat[0, 0]**2 + rmat[1, 0]**2)))
    pitch = np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2]))
    return yaw, pitch

# =============================================================================
# MAIN MONITORING APPLICATION
# =============================================================================

def start_monitoring():
    global CURRENT_DRIVE_ID, video_out
    
    log_info("Initializing Computer Vision models...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    
    # Open camera with V4L2 backend to prevent GStreamer warnings
    log_info("Opening Camera stream (V4L2 backend)...")
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    
    if not cap.isOpened():
        log_error("Could not open video device.")
        sys.exit(1)

    # --- PHASE 1: STANDBY ---
    log_info("Standby Mode: Waiting for driver to be detected...")
    while True:
        ret, frame = cap.read()
        if not ret: continue
        
        # Performance optimization
        temp_gray = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2GRAY)
        rects = detector(temp_gray, 0)
        
        if len(rects) > 0:
            log_success("Driver detected. Initializing session...")
            break
        time.sleep(0.5)

    # --- PHASE 2: SESSION INITIALIZATION ---
    try:
        log_info("Contacting Heroku backend to start drive...")
        resp = requests.post(f"{BASE_URL}/start_drive", json={"device_id": DEVICE_ID}, timeout=30)
        CURRENT_DRIVE_ID = resp.json().get("drive_id")
        log_success(f"Session Active. Drive ID: {CURRENT_DRIVE_ID}")
    except Exception as e:
        log_error(f"Failed to start session: {str(e)}")
        sys.exit(1)

    # Initialize MP4 Video Writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    video_out = cv2.VideoWriter(VIDEO_TEMP_FILE, fourcc, 10.0, (640, 480))
    log_debug(f"Local recording started: {VIDEO_TEMP_FILE}")

    last_send = time.time()
    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    # --- PHASE 3: MONITORING LOOP ---
    try:
        log_info("Monitoring in progress. Press Ctrl+C to stop.")
        while True:
            ret, frame = cap.read()
            if not ret: 
                log_error("Video stream interrupted.")
                break

            frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = detector(gray, 0)
            
            is_distracted = len(rects) == 0
            ear = 0.0
            yaw, pitch = 0.0, 0.0

            if not is_distracted:
                # DRAW BOUNDARY BOX ON FACE
                for rect in rects:
                    (x, y, w, h) = face_utils.rect_to_bb(rect)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "DRIVER", (x, y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # Landmarks extraction
                shape = face_utils.shape_to_np(predictor(gray, rects[0]))
                
                # Fatigue Analysis (EAR)
                ear = (calculate_ear(shape[lS:lE]) + calculate_ear(shape[rS:rE])) / 2.0
                
                # Distraction Analysis (Pose)
                yaw, pitch = get_head_pose(shape, 480, 640)
                if abs(yaw) > HEAD_YAW_LIMIT or pitch < HEAD_PITCH_LIMIT:
                    is_distracted = True

            # Write the processed frame (with box) to video
            video_out.write(frame)

            # TELEMETRY TRANSMISSION (1Hz Heartbeat)
            if time.time() - last_send > 1.0:
                payload = {
                    "drive_id": CURRENT_DRIVE_ID, 
                    "ear": round(ear, 2), 
                    "is_distracted": is_distracted,
                    "head_yaw": round(yaw, 2),
                    "head_pitch": round(pitch, 2)
                }
                # Background thread to maintain 10+ FPS in main loop
                threading.Thread(target=send_telemetry_async, args=(payload,)).start()
                
                log_debug(f"Telemetry Sent - EAR: {ear:.2f} | Distracted: {is_distracted}")
                last_send = time.time()

    except KeyboardInterrupt:
        log_info("User interrupted monitoring.")
    finally:
        cap.release()
        # finalize_and_upload() will be triggered by atexit automatically

if __name__ == "__main__":
    start_monitoring()