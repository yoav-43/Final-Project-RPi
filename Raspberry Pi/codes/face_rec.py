import cv2
from picamera2 import Picamera2

print("Initializing NoIR Face Recognition...")
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()

# We force the camera to use the values that remove the orange tint
picam2.set_controls({"AwbMode": 0, "ColourGains": (0.5, 1.7)})

# Load Face Detection
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

print("Running... Press 'q' to quit.")

while True:
    frame = picam2.capture_array()

    # 1. Color Conversion (RGB -> BGR)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # 2. Rotation 180
    frame = cv2.rotate(frame, cv2.ROTATE_180)

    # 3. Detect Faces
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))

    # 4. Draw Green Box around Face
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, "Target", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    cv2.imshow("Face Rec (NoIR Corrected)", frame)

    if cv2.waitKey(1) == ord('q'):
        break

picam2.stop()
cv2.destroyAllWindows()