"""
DRIVER MONITORING SYSTEM WITH CLOUD VIDEO UPLOAD
------------------------------------------------
This script monitors driver alertness and records the session.
On termination, the video is uploaded to Cloudinary and the link is sent to the backend.
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
# GLOBAL CONFIGURATION
# =============================================================================
BASE_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api"
DEVICE_ID = "raspi_v1"
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
VIDEO_TEMP_FILE = "drive_video.avi"

# Cloudinary Credentials - REPLACE WITH YOUR KEYs
cloudinary.config( 
  cloud_name = "dei1fd8k6", 
  api_key = "545933773654545", 
  api_secret = "434wCTl3T4jlwQKpjiX8Rp2Bc6s" 
)

# Thresholds
EAR_THRESHOLD = 0.25
HEAD_YAW_LIMIT = 20
HEAD_PITCH_LIMIT = -15

# Global Session Objects
CURRENT_DRIVE_ID = None
video_out = None 

# =============================================================================
# CLOUD & SESSION LOGIC
# =============================================================================

def finalize_and_upload():
    """
    Finalizes the video file, uploads it to Cloudinary, and notifies the server.
    Registered via atexit to ensure execution on script exit.
    """
    global CURRENT_DRIVE_ID, video_out
    
    if video_out is not None:
        video_out.release()
        print("[INFO] Video file finalized locally.")

    if CURRENT_DRIVE_ID is None:
        return

    video_url = None
    try:
        if os.path.exists(VIDEO_TEMP_FILE):
            print("[UPLOAD] Uploading video to Cloudinary... (Do not disconnect)")
            # Uploading as a video resource to Cloudinary
            upload_result = cloudinary.uploader.upload(VIDEO_TEMP_FILE, resource_type="video")
            video_url = upload_result.get("secure_url")
            print(f"[SUCCESS] Cloud Video URL: {video_url}")
            os.remove(VIDEO_TEMP_FILE) # Cleanup local storage
    except Exception as e:
        print(f"[ERROR] Cloudinary Upload failed: {e}")

    try:
        print(f"[SERVER] Syncing end-of-session for ID #{CURRENT_DRIVE_ID}...")
        # Send final payload including the video URL
        requests.post(f"{BASE_URL}/end_drive", json={
            "drive_id": CURRENT_DRIVE_ID,
            "video_url": video_url
        }, timeout=30)
        print("[SUCCESS] Server updated. Session complete.")
    except Exception as e:
        print(f"[WARN] Failed to sync with server: {e}")

atexit.register(finalize_and_upload)

# =============================================================================
# COMPUTER VISION UTILITIES
# =============================================================================

def calculate_ear(eye):
    """ Calculates Eye Aspect Ratio to detect closure. """
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def get_head_pose(shape, img_h, img_w):
    """ Estimates head orientation using Perspective-n-Point. """
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
# MAIN MONITORING EXECUTION
# =============================================================================

def start_monitoring():
    global CURRENT_DRIVE_ID, video_out
    
    # Initialization
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    cap = cv2.VideoCapture(0)

    # 1. Standby Mode (Wait for driver)
    print("[WAIT] System Standby. Detecting face...")
    while True:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2GRAY)
        if len(detector(gray, 0)) > 0: break
        time.sleep(0.5)

    # 2. Start API Session
    try:
        resp = requests.post(f"{BASE_URL}/start_drive", json={"device_id": DEVICE_ID}, timeout=30)
        CURRENT_DRIVE_ID = resp.json().get("drive_id")
        print(f"[LIVE] Session Started: {CURRENT_DRIVE_ID}")
    except: sys.exit("[FATAL] Could not start session.")

    # 3. Setup Video Recorder
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    video_out = cv2.VideoWriter(VIDEO_TEMP_FILE, fourcc, 10.0, (640, 480))

    last_send = time.time()
    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            frame = cv2.resize(frame, (640, 480))
            video_out.write(frame) # Write current frame to disk
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = detector(gray, 0)
            is_distracted = len(rects) == 0
            ear = 0.0

            if not is_distracted:
                shape = face_utils.shape_to_np(predictor(gray, rects[0]))
                yaw, pitch = get_head_pose(shape, 480, 640)
                if abs(yaw) > HEAD_YAW_LIMIT or pitch < HEAD_PITCH_LIMIT:
                    is_distracted = True
                ear = (calculate_ear(shape[lS:lE]) + calculate_ear(shape[rS:rE])) / 2.0

            # Telemetry Transmission (1Hz)
            if time.time() - last_send > 1.0:
                payload = {"drive_id": CURRENT_DRIVE_ID, "ear": round(ear, 2), "is_distracted": is_distracted}
                threading.Thread(target=lambda: requests.post(f"{BASE_URL}/telemetry", json=payload)).start()
                last_send = time.time()
                print(f"[STATUS] EAR: {ear:.2f} | Distracted: {is_distracted}")

    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
    finally:
        cap.release()

if __name__ == "__main__":
    start_monitoring()