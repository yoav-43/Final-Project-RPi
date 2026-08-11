# Waveshare RPi IR-CUT Camera — Project Reference

Sensor: **OV5647** (5MP)  
Interface: **CSI ribbon cable**  
IR LEDs: 850nm  
Driver: **libcamera** (rpicam-* tools)

---

## Hardware Modes

| Mode | IR-CUT filter | Image |
|------|--------------|-------|
| Normal (day) | Active (blocks IR) | Color |
| Night-vision | Open (passes IR) | B&W / IR-tinted |

### How to switch modes

**Method 1 — config.txt (static, requires reboot):**
```ini
# Night-vision ON:
disable_camera_led=1

# Normal mode (default — comment out or remove the line):
# disable_camera_led=1
```

**Method 2 — GPIO (runtime toggle):**  
Connect the EN pad on the back of the camera board to a GPIO pin.
- GPIO **HIGH** → Normal mode (IR-CUT filter active, color image)
- GPIO **LOW** → Night-vision mode (IR-CUT filter open, IR image)

**Current wiring: EN pad → GPIO17 (BCM)**

Example Python code to control via GPIO:
```python
import RPi.GPIO as GPIO

IR_CUT_PIN = 17  # wired to EN pad on camera board

GPIO.setmode(GPIO.BCM)
GPIO.setup(IR_CUT_PIN, GPIO.OUT)

GPIO.output(IR_CUT_PIN, GPIO.HIGH)  # Normal / color mode
GPIO.output(IR_CUT_PIN, GPIO.LOW)   # Night-vision mode
```

This is already implemented in `setup_camera()` in `image_processor.py` — GPIO17 is driven HIGH on startup (normal color mode) and cleaned up on `release_camera()`.

**Method 3 — hardwire to 3.3V:**  
Connect EN pad directly to Pi pin 1 (3.3V) for permanent Normal mode. No code needed.

---

## Sensor Modes (OV5647)

| Mode | Resolution | Aspect | FPS | FoV |
|------|-----------|--------|-----|-----|
| 0 | Auto | — | — | — |
| 1 | 1920×1080 | 16:9 | 1–30 | Partial |
| 2 | 2592×1944 | 4:3 | 1–15 | Full |
| 3 | 2592×1944 | 4:3 | 0.17–1 | Full |
| 4 | 1296×972 | 4:3 | 1–42 | Full |
| 5 | 1296×730 | 16:9 | 1–49 | Full |
| 6 | 640×480 | 4:3 | 42–60 | Full |
| 7 | 640×480 | 4:3 | 60–90 | Full |

**Currently used in project:** Mode 4 (1296×972, up to 42fps, full FoV)

---

## config.txt Settings (current project state)

```ini
camera_auto_detect=0       # Must be 0 for third-party modules
dtoverlay=ov5647           # Loads OV5647 kernel driver
start_x=1                  # Enables MMAL/V4L2 bridge (bcm2835_v4l2)
gpu_mem=128                # Minimum GPU RAM for camera firmware
# disable_camera_led=1     # COMMENTED OUT — keeps camera in normal color mode
```

---

## libcamera / rpicam Commands

```bash
# List detected cameras and supported modes
rpicam-hello --list-cameras

# 5-second preview test
rpicam-hello -t 5000

# Capture a still image
rpicam-still -o test.jpg -t 2000 --width 1296 --height 972

# Record 10s video
rpicam-vid -t 10000 -o test.mp4

# Use specific tuning file
rpicam-still -o test.jpg --tuning-file /usr/share/libcamera/ipa/rpi/vc4/ov5647_noir.json
```

---

## Tuning Files

Located at `/usr/share/libcamera/ipa/rpi/vc4/`:

| File | Use case |
|------|----------|
| `ov5647.json` | Default — standard color, normal AWB |
| `ov5647_noir.json` | No-IR-filter cameras — BUT also produces balanced AWB for this IR-CUT module |

**Currently used in project:** `ov5647_noir.json`  
Reason: default `ov5647.json` produces a purple tint on this specific Waveshare module. The noir tuning gives balanced channel means (~140/143/141 R/G/B).

---

## picamera2 Usage (current project implementation)

```python
from picamera2 import Picamera2
import cv2

picam2 = Picamera2(tuning=Picamera2.load_tuning_file(
    "/usr/share/libcamera/ipa/rpi/vc4/ov5647_noir.json"
))
picam2.configure(picam2.create_preview_configuration(
    main={"format": "BGR888", "size": (1296, 972)}
))
picam2.start()

# Capture frame — must convert BGR888 output to proper BGR for OpenCV
frame = picam2.capture_array()
frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # required for correct colors

picam2.stop()
```

> **Why RGB2BGR conversion?** Despite requesting `BGR888`, the OV5647 with noir tuning outputs channels in RGB order. The `cvtColor` swaps R and B to produce correct colors in OpenCV and saved video files.

---

## White Balance (AWB) Manual Override

If colors are off, force manual AWB gains via picamera2:
```python
from libcamera import controls
picam2.set_controls({"AwbEnable": False, "ColourGains": (1.8, 1.4)})  # (red_gain, blue_gain)
```

Or via rpicam command:
```bash
rpicam-still -o test.jpg --awbgains 1.8,1.4
```

---

## Known Issues on This Setup

| Issue | Cause | Fix |
|-------|-------|-----|
| Purple/IR-tinted image | `disable_camera_led=1` active, or EN pin floating low | Comment out the config line; reboot |
| Blue image | Wrong channel order (missing RGB→BGR conversion) | `cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)` |
| `cv2.VideoCapture(0)` returns frames but all black | `/dev/video0` is raw unicam device, not a usable V4L2 capture node | Use picamera2 instead |
| libcamera INFO spam in terminal | Normal libcamera startup output | Redirect stderr or ignore |

---

## IR LED Notes

- Wavelength: **850nm** (near-infrared, mostly invisible to human eye)
- Operating voltage: **3.3V**
- Peak current: **0.15A** (camera board total)
- Each LED: ~300mA–2A at 3V–5V
- To disable IR LEDs permanently: short the EN pad on the back of the board to GND
