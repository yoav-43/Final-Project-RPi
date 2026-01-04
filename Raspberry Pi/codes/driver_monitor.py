"""
DRIVER MONITORING SYSTEM (CLIENT SIDE) - FULL ANALYTICS VERSION
---------------------------------------------------------------------------------------
Features: Visual face box, EAR, PERCLOS, Head Pose (Yaw/Pitch), and Cloud Sync.
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
# SYSTEM CONFIGURATION
# =============================================================================
BASE_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api"
DEVICE_ID = "raspi_v1"
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
VIDEO_TEMP_FILE = "drive_video.mp4" 

cloudinary.config( 
  cloud_name = "dei1fd8k6", 
  api_key = "545933773654545", 
  api_secret = "434wCTl3T4jlwQKpjiX8Rp2Bc6s" 
)

# Thresholds for analytics
EAR_THRESHOLD = 0.25
HEAD_YAW_LIMIT = 22
HEAD_PITCH_LIMIT = -15

# Global session variables
CURRENT_DRIVE_ID = None
video_out = None
eye_closed_frames = 0
total_frames_in_minute = 0

# =============================================================================
# LOGGING & CLOUD SYNC
# =============================================================================

def log_event(level, message):
    print(f"[{level}] {time.strftime('%H:%M:%S')} - {message}")

def finalize_session():
    """ Finalizes local video and pushes everything to the cloud. """
    global CURRENT_DRIVE_ID, video_out
    log_event("INFO", "Starting termination cleanup...")
    
    if video_out is not None:
        video_out.release()
    
    if CURRENT_DRIVE_ID is None: return

    video_url = None
    try:
        if os.path.exists(VIDEO_TEMP_FILE):
            log_event("UPLOAD", "Uploading MP4 to Cloudinary...")
            # Use 'video' resource type for browser streaming support
            res = cloudinary.uploader.upload(VIDEO_TEMP_FILE, resource_type="video")
            video_url = res.get("secure_url")
            os.remove(VIDEO_TEMP_FILE)
            log_event("SUCCESS", f"Video available at: {video_url}")
    except Exception as e:
        log_event("ERROR", f"Cloudinary failed: {e}")

    try:
        requests.post(f"{BASE_URL}/end_drive", json={
            "drive_id": CURRENT_DRIVE_ID,
            "video_url": video_url
        }, timeout=20)
        log_event("SUCCESS", "Backend session closed.")
    except:
        log_event("ERROR", "Backend sync failed.")

atexit.register(finalize_session)

# =============================================================================
# ANALYTICS HELPERS
# =============================================================================

def get_ear(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def get_head_pose(shape, img_h, img_w):
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
# MAIN LOOP
# =============================================================================

def start_monitoring():
    global CURRENT_DRIVE_ID, video_out, eye_closed_frames, total_frames_in_minute
    
    log_event("INFO", "Loading AI Models...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

    log_event("INFO", "Waiting for Driver...")
    while True:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2GRAY)
        if len(detector(gray, 0)) > 0: break
        time.sleep(0.5)

    # API Start
    log_event("INFO", "Opening Session on Heroku...")
    resp = requests.post(f"{BASE_URL}/start_drive", json={"device_id": DEVICE_ID})
    CURRENT_DRIVE_ID = resp.json().get("drive_id")
    log_event("SUCCESS", f"Drive #{CURRENT_DRIVE_ID} is LIVE.")

    # Video setup - Use avc1 codec for best web compatibility
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    video_out = cv2.VideoWriter(VIDEO_TEMP_FILE, fourcc, 10.0, (640, 480))

    last_send = time.time()
    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = detector(gray, 0)
            
            is_distracted = len(rects) == 0
            ear, yaw, pitch = 0.0, 0.0, 0.0
            total_frames_in_minute += 1

            if not is_distracted:
                for rect in rects:
                    # DRAW FACE BOX
                    (x, y, w, h) = face_utils.rect_to_bb(rect)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "DRIVER DETECTED", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                shape = face_utils.shape_to_np(predictor(gray, rects[0]))
                ear = (get_ear(shape[lS:lE]) + get_ear(shape[rS:rE])) / 2.0
                yaw, pitch = get_head_pose(shape, 480, 640)
                
                if ear < EAR_THRESHOLD: eye_closed_frames += 1
                if abs(yaw) > HEAD_YAW_LIMIT or pitch < HEAD_PITCH_LIMIT: is_distracted = True

            video_out.write(frame)

            # Heartbeat - Send data every 1 second
            if time.time() - last_send > 1.0:
                perclos = (eye_closed_frames / total_frames_in_minute) * 100 if total_frames_in_minute > 0 else 0
                payload = {
                    "drive_id": CURRENT_DRIVE_ID, 
                    "ear": round(ear, 2), 
                    "perclos": round(perclos, 2),
                    "is_distracted": is_distracted,
                    "head_yaw": round(yaw, 2),
                    "head_pitch": round(pitch, 2)
                }
                threading.Thread(target=lambda p: requests.post(f"{BASE_URL}/telemetry", json=p), args=(payload,)).start()
                log_event("DEBUG", f"Syncing Telemetry: EAR={ear:.2f}, Distracted={is_distracted}")
                last_send = time.time()

    except KeyboardInterrupt:
        log_event("INFO", "Monitoring Stopped by User.")
    finally:
        cap.release()

if __name__ == "__main__":
    start_monitoring()