# image_processor — Computer Vision Core

Provides all camera I/O and computer vision algorithms used by the monitor. Designed as a reusable class so the main loop stays clean.

## Files

| File | Description |
|------|-------------|
| `image_processor.py` | `ImageProcessor` class: camera management, EAR, head pose, visual feedback. Also contains a standalone live-test mode. |

## Class: `ImageProcessor`

### Constructor

```python
ImageProcessor(predictor_path=None, camera_index=0)
```

| Parameter | Description |
|-----------|-------------|
| `predictor_path` | Path to `shape_predictor_68_face_landmarks.dat`. If `None`, the detector/predictor are not loaded (useful for unit testing). |
| `camera_index` | OpenCV camera index (default `0`). |

Initializes:
- `dlib.get_frontal_face_detector()` — HOG-based frontal face detector.
- `dlib.shape_predictor(path)` — 68-point facial landmark predictor.
- A `camera_matrix` cache (populated lazily on first `get_head_pose` call).

### Camera Methods

| Method | Description |
|--------|-------------|
| `setup_camera()` | Opens the camera. Tries `cv2.CAP_V4L2` first (Linux/RPi), falls back to the default backend. Raises `IOError` if the camera cannot be opened. |
| `get_frame()` | Returns `(ret, frame)` from `cap.read()`. |
| `release_camera()` | Releases the `VideoCapture` object. |

### Algorithm: EAR (Eye Aspect Ratio)

```python
@staticmethod
calculate_ear(eye_points) -> float
```

Computes the ratio of the vertical eye distances to the horizontal distance using the 6 landmark points of one eye:

```
EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
```

A value below `0.25` (configurable) indicates a closed eye. Called separately for left and right eyes; the average is used.

### Algorithm: Head Pose Estimation

```python
get_head_pose(shape, img_h, img_w) -> (yaw, pitch)
```

Uses OpenCV's `solvePnP` to solve the Perspective-n-Point problem:

1. Defines a generic 3D face model (6 key points: nose tip, chin, eye corners, mouth corners).
2. Maps them to the corresponding 2D landmark indices from the 68-point shape (`shape[30]`, `shape[8]`, etc.).
3. Builds a pinhole camera matrix using `focal_length = img_width` (approximation).
4. Calls `cv2.solvePnP` → rotation vector → `cv2.Rodrigues` → rotation matrix → `cv2.decomposeProjectionMatrix` → Euler angles.
5. Returns `(yaw, pitch)` in degrees. Yaw > ±22° or pitch < -15° triggers a distraction alert.

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

Renders a live legend in the top-left corner of every frame (including frames with no face detected). Each stat value is colored **green** if within threshold or **red** if in violation:

| Stat | Violation condition |
|------|-------------------|
| EAR | < `thresholds['ear']` |
| PERCLOS | > `thresholds['perclos_fatigue_limit']` |
| Yaw | `abs(yaw)` > `thresholds['head_yaw']` |
| Pitch | < `thresholds['head_pitch']` |
| FPS | always green (informational) |

## Standalone Test Mode

Run directly to test the camera and algorithms without the full system:

```bash
# From project root
python3 image_processor/image_processor.py
```

Opens the camera, runs face detection + EAR + pose on every frame, displays a live window, and saves output to `test_output.avi`. Press `q` in the video window to stop.

## Dependencies

```
opencv-python
dlib
imutils
scipy
numpy
```
