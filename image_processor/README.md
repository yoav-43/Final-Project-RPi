# image_processor — Computer Vision Core

Provides all camera I/O and computer vision algorithms used by the monitor. Designed as a reusable class so the main loop stays clean.

## Files

| File | Description |
|------|-------------|
| `image_processor.py` | `ImageProcessor` class: camera management, EAR, head pose, visual feedback. Also contains a standalone live-test mode. |

## Class: `ImageProcessor`

### Constructor

```python
ImageProcessor(predictor_path=None, camera_index=0, night_vision=False)
```

| Parameter | Description |
|-----------|-------------|
| `predictor_path` | Path to `shape_predictor_68_face_landmarks.dat`. If `None`, the detector/predictor are not loaded (useful for unit testing). |
| `camera_index` | Unused (kept for API compatibility). The CSI camera is opened via picamera2. |
| `night_vision` | If `True`, drives GPIO17 LOW on `setup_camera()` — opens the IR-CUT filter for night-vision mode. If `False` (default), drives GPIO17 HIGH for normal color mode. |

Initializes:
- `dlib.get_frontal_face_detector()` — HOG-based frontal face detector.
- `dlib.shape_predictor(path)` — 68-point facial landmark predictor.
- A `camera_matrix` cache (populated lazily on first `get_head_pose` call).
- A `CLAHE` instance for low-light contrast enhancement.

### Camera Methods

| Method | Description |
|--------|-------------|
| `setup_camera()` | Opens the CSI camera via **picamera2** using the `ov5647_noir.json` tuning file for correct white balance. Captures `BGR888` frames at `1296×972`. Also controls the IR-CUT filter via **GPIO17**: HIGH = normal color mode, LOW = night-vision mode (IR LEDs illuminate, IR-CUT filter open). |
| `get_frame()` | Returns `(True, frame)` where `frame` is a BGR numpy array ready for OpenCV. Converts from `RGB888` picamera2 output to BGR. |
| `release_camera()` | Stops the picamera2 instance and cleans up the GPIO17 pin. |

> **Camera hardware:** Waveshare RPi IR-CUT Camera (OV5647 sensor, CSI interface). Uses `picamera2` + libcamera backend. The `ov5647_noir.json` tuning file is used (despite having an IR-CUT filter) because it produces correctly balanced white balance for this specific module.

> **IR-CUT filter control:** The EN pad on the back of the camera board is wired to **GPIO17 (BCM)**. `setup_camera()` drives this pin based on the `night_vision` flag passed to the constructor. See `docs/camera_reference.md` for full hardware details.

### Algorithm: EAR (Eye Aspect Ratio)

```python
@staticmethod
calculate_ear(eye_points) -> float
```

Computes the ratio of the vertical eye distances to the horizontal distance using the 6 landmark points of one eye:

```
EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
```

A value below `0.18` (configurable) indicates a closed eye. Called separately for left and right eyes; the average is used.

### Algorithm: Head Pose Estimation

```python
get_head_pose(shape, img_h, img_w) -> (yaw, pitch)
```

Uses OpenCV's `solvePnP` to solve the Perspective-n-Point problem:

1. Defines a generic 3D face model (6 key points: nose tip, chin, eye corners, mouth corners).
2. Maps them to the corresponding 2D landmark indices from the 68-point shape (`shape[30]`, `shape[8]`, etc.).
3. Builds a pinhole camera matrix using `focal_length = img_width` (approximation).
4. Calls `cv2.solvePnP` → rotation vector → `cv2.Rodrigues` → rotation matrix → `cv2.decomposeProjectionMatrix` → Euler angles.
5. Normalizes pitch: `cv2.decomposeProjectionMatrix` returns pitch near ±180° for a forward-facing head; values outside ±90° are shifted by 180° and negated so that:
   - `~0°` = looking straight ahead
   - `negative` = looking down
   - `positive` = looking up
6. Returns `(yaw, pitch)` in degrees. Yaw > ±45° or pitch < -15° triggers a distraction alert.

The camera matrix is computed once and cached in `self.camera_matrix`.

### Visual Feedback

```python
draw_feedback(frame, rect, color, label) -> frame
```

Draws a colored bounding box and status label over the detected face rectangle. Colors used by the main loop:

| State | Color | Label |
|-------|-------|-------|
| Focused | Green `(0,255,0)` | `FOCUSED` |
| Fatigued | Red `(0,0,255)` | `FATIGUE!` |
| Distracted | Yellow `(0,255,255)` | `DISTRACTED` |

```python
draw_stats_overlay(frame, ear, perclos, yaw, pitch, fps, thresholds) -> frame
```

Renders a live legend in the top-left corner of every frame. Each stat is colored **green** if within threshold or **red** if in violation.

## Standalone Test Mode

Run directly to test the camera and algorithms without the full system:

```bash
# From project root
python3 image_processor/image_processor.py
```

Opens the camera, runs face detection + EAR + pose on every frame, and saves output to `test_output.avi` at full `1296×972` resolution using the MJPG codec. Press `q` to stop.

> **Note:** The standalone test saves `.avi` at `1296×972` (full sensor resolution, MJPG codec). The main monitor loop records `.mp4` at `640×480` (resized, mp4v codec). These are different for performance reasons.

## Dependencies

```
opencv-python
dlib
imutils
scipy
numpy
picamera2
RPi.GPIO
```
