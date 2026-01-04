"""
DRIVER MONITORING SYSTEM (CLIENT SIDE) - UPDATED WITH FACE BOX & MP4
---------------------------------------------------------------------------------------
Description:
    Analyzes driver alertness and head pose. Now includes a visual bounding box 
    around the detected face and records in MP4 format for web compatibility.
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
# CONFIGURATION
# =============================================================================
BASE_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api"
DEVICE_ID = "raspi_v1"
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
# Changed extension to .mp4 for better browser support
VIDEO_TEMP_FILE = "drive_video.mp4" 

cloudinary.config( 
  cloud_name = "dei1fd8k6", 
  api_key = "545933773654545", 
  api_secret = "434wCTl3T4jlwQKpjiX8Rp2Bc6s" 
)

EAR_THRESHOLD = 0.25
HEAD_YAW_LIMIT = 20
HEAD_PITCH_LIMIT = -15

CURRENT_DRIVE_ID = None
video_out = None 

# =============================================================================
# UTILITIES & UPLOAD
# =============================================================================

def finalize_and_upload():
    """ Finalizes MP4 recording and uploads to Cloudinary. """
    global CURRENT_DRIVE_ID, video_out
    if video_out is not None:
        video_out.release()
    
    if CURRENT_DRIVE_ID is None: return

    video_url = None
    try:
        if os.path.exists(VIDEO_TEMP_FILE):
            print("[UPLOAD] Transmitting MP4 to Cloudinary...")
            upload_result = cloudinary.uploader.upload(VIDEO_TEMP_FILE, resource_type="video")
            video_url = upload_result.get("secure_url")
            os.remove(VIDEO_TEMP_FILE)
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")

    try:
        requests.post(f"{BASE_URL}/end_drive", json={
            "drive_id": CURRENT_DRIVE_ID,
            "video_url": video_url
        }, timeout=30)
    except: pass

atexit.register(finalize_and_upload)

def calculate_ear(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# =============================================================================
# MAIN MONITORING
# =============================================================================

def start_monitoring():
    global CURRENT_DRIVE_ID, video_out
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    cap = cv2.VideoCapture(0)

    # Standby Phase
    while True:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2GRAY)
        if len(detector(gray, 0)) > 0: break
        time.sleep(0.5)

    # Session Start
    resp = requests.post(f"{BASE_URL}/start_drive", json={"device_id": DEVICE_ID})
    CURRENT_DRIVE_ID = resp.json().get("drive_id")

    # Video Writer - Set to MP4V for .mp4 compatibility
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
            ear = 0.0

            if not is_distracted:
                # NEW: Draw a boundary square around the detected face
                for rect in rects:
                    (x, y, w, h) = face_utils.rect_to_bb(rect)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "Driver Detected", (x, y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                shape = face_utils.shape_to_np(predictor(gray, rects[0]))
                ear = (calculate_ear(shape[lS:lE]) + calculate_ear(shape[rS:rE])) / 2.0

            # Write the frame (now with the box) to the video file
            video_out.write(frame) 

            if time.time() - last_send > 1.0:
                payload = {"drive_id": CURRENT_DRIVE_ID, "ear": round(ear, 2), "is_distracted": is_distracted}
                threading.Thread(target=lambda: requests.post(f"{BASE_URL}/telemetry", json=payload)).start()
                last_send = time.time()
                print(f"[LIVE] Driving... EAR: {ear:.2f}")

    except KeyboardInterrupt: pass
    finally: cap.release()

if __name__ == "__main__":
    start_monitoring()