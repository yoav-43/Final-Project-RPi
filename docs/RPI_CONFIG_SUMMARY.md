# Raspberry Pi Configuration Summary — WakeUp Project

A reference document tracking all custom changes made to the Raspberry Pi for this project.
Last updated: 2026-06-21 (post-picamera2 migration)

---

## Hardware

| Component | Details | Connection | Device Node |
|-----------|---------|------------|-------------|
| Raspberry Pi 4 Model B Rev 1.4 | BCM2711, 64-bit, kernel 6.12 | — | — |
| Waveshare RPi IR-CUT Camera | Sensor: **OV5647** (5MP), IR-CUT filter, 850nm IR LEDs | CSI ribbon-cable | `/dev/video0` |
| Arduino (buzzer controller) | Renesas-based (vendor 0x2341) | USB | `/dev/ttyACM0` |
| GPS module (NEO-6M) | NMEA over serial | UART (`ttyAMA0`) | `/dev/ttyAMA0` |

---

## File: `/boot/firmware/config.txt`

Hardware configuration loaded by the firmware at boot. Changes here affect the kernel overlays,
device drivers, and hardware interfaces that are available to the OS.

### Camera

```ini
# Disabled automatic CSI camera detection.
# Default is 1 (auto-detect). Changed to 0 because the Waveshare IR-CUT OV5647 is a
# third-party module — auto-detect would either fail or load the wrong driver overlay.
# When set to 0, the correct sensor overlay MUST be added manually (see dtoverlay=ov5647).
camera_auto_detect=0

# Loads the kernel driver for the OV5647 image sensor (Waveshare RPi IR-CUT Camera).
# REQUIRED whenever camera_auto_detect=0. Without this line the kernel loads no camera
# driver and the device is invisible to both libcamera and the MMAL/V4L2 bridge.
dtoverlay=ov5647

# Enables the MMAL → V4L2 bridge firmware stack.
# This makes the CSI camera appear as /dev/video0, which OpenCV opens with
# cv2.VideoCapture(0, cv2.CAP_V4L2) in image_processor/image_processor.py.
start_x=1

# Reserves 128 MB of system RAM for the GPU / camera firmware.
# This is the minimum required when start_x=1 is active. Reducing it below 128
# will cause the camera firmware to fail to initialise.
gpu_mem=128

# Commented out — leaving this enabled forces night-vision mode (IR-CUT filter open),
# causing a purple/IR tint in video. Default (commented out) keeps the camera in
# normal day mode with the IR-CUT filter active.
# disable_camera_led=1
```

### GPU / Display

```ini
# The KMS/DRM GPU overlay is intentionally disabled (left commented out).
# Enabling vc4-kms-v3d while running headless (no display) can cause the
# boot process to stall waiting for a display that is not present, and also
# interferes with the MMAL camera firmware stack on RPi 4.
# dtoverlay=vc4-kms-v3d   ← keep disabled
```

### UART / Serial

```ini
# Enables the hardware UART controller.
# Required for serial communication with both the Arduino (/dev/ttyACM0)
# and the GPS module (/dev/ttyAMA0 via the primary UART).
enable_uart=1

# Disables the on-board Bluetooth module and releases UART0 (ttyAMA0).
# By default on RPi 4, Bluetooth claims the full-speed hardware UART (ttyAMA0),
# leaving only the mini-UART (ttyS0) for general use. Disabling BT gives the
# GPS module exclusive access to the reliable hardware UART.
dtoverlay=disable-bt

# Explicitly enables UART0 (the primary hardware UART, now freed from Bluetooth).
# Ensures ttyAMA0 is active and available for the GPS module.
dtparam=uart0=on

# Enables additional hardware UART interfaces on GPIO pins.
# uart2 and uart3 are available for future sensor or peripheral connections.
dtoverlay=uart2
dtoverlay=uart3
# NOTE: the line below is a TYPO — "dyoverlay" is not a valid directive.
# It should be "dtoverlay=uart4". uart4 is currently NOT enabled as a result.
dyoverlay=uart4
```

### Other Interfaces

```ini
# Enables the I2C bus on GPIO2 (SDA) and GPIO3 (SCL).
# Not used by the current project but enabled for future sensor expansion
# (e.g. temperature sensors, IMU).
dtparam=i2c_arm=on

# Enables the SPI bus on GPIO8–11.
# Not used by the current project but enabled for future expansion.
dtparam=spi=on

# Enables the 1-Wire protocol on GPIO4 (default data pin).
# Not actively used; added for potential DS18B20 temperature sensor support.
dtoverlay=w1-gpio

# Runs the ARM CPU at its maximum boost frequency.
# The RPi 4 boosts from 1.5 GHz to 1.8 GHz. Helps sustain the real-time
# dlib face-detection loop at ~10 fps without throttling.
arm_boost=1
```

---

## File: `/boot/firmware/cmdline.txt`

Kernel command-line parameters passed to the Linux kernel at boot.
This is a single line — all parameters are space-separated.

```
cfg80211.ieee80211_regdom=IL
```

Sets the Wi-Fi regulatory domain to **Israel (IL)**. Without this, the kernel
defaults to the conservative worldwide (00) domain which restricts available
channels and maximum transmission power. Setting IL unlocks the correct local
channel set and power limits.

---

## File: `/etc/NetworkManager/system-connections/<HOTSPOT_NAME>.nmconnection`

NetworkManager connection profile for the Wi-Fi hotspot used in the vehicle.
The filename contains the personal hotspot SSID (redacted from this document).

| Setting | Value |
|---------|-------|
| Manager | NetworkManager |
| Interface | `wlan0` |
| Connection | iPhone personal hotspot (SSID redacted — personal device name) |
| IP assignment | DHCP (automatic) |
| Autoconnect priority | 100 (highest) |

- No `wpa_supplicant.conf` is used — NetworkManager handles Wi-Fi exclusively.
- The file exists on the device at the path above with the real SSID in the filename.

---

## File: `/etc/udev/rules.d/60-arduino-renesas.rules`

udev rule that runs when a USB device is plugged in. Matches on Arduino's USB
vendor ID and grants open read/write permissions so the Python `pyserial` library
can open `/dev/ttyACM0` without requiring `sudo`.

```udev
SUBSYSTEMS=="usb", ATTRS{idVendor}=="2341", MODE:="0666"
```

---

## File: `/etc/passwd` / group membership

User `yoavroy` was added to hardware access groups. Without these, Python scripts
cannot open serial ports or video devices without `sudo`.

| Group | Device accessed | Why needed |
|-------|----------------|------------|
| `dialout` | `/dev/ttyACM0`, `/dev/ttyAMA0` | Serial ports (Arduino + GPS) |
| `video` | `/dev/video0` | CSI camera |
| `gpio` | GPIO pins | Direct GPIO control |
| `spi` | SPI bus | SPI peripherals |
| `i2c` | I2C bus | I2C peripherals |
| `input` | Input devices | General input |

```bash
sudo usermod -aG dialout,video,gpio,spi,i2c yoavroy
# Requires logout/login to take effect
```

---

## Camera Access — How It Works in Code

**File:** `image_processor/image_processor.py`

```python
# Opens the CSI camera via picamera2 (libcamera backend).
# Uses ov5647_noir.json tuning file — despite having an IR-CUT filter, this module
# requires the noir tuning for correct white balance on this specific hardware revision.
# BGR888 format outputs balanced RGB channels; converted to BGR for OpenCV compatibility.
from picamera2 import Picamera2
self.cap = Picamera2(tuning=Picamera2.load_tuning_file(
    "/usr/share/libcamera/ipa/rpi/vc4/ov5647_noir.json"
))
self.cap.configure(self.cap.create_preview_configuration(
    main={"format": "BGR888", "size": (1296, 972)}
))
self.cap.start()

# Frame capture — converts BGR888 output to BGR for OpenCV:
frame = self.cap.capture_array()
return True, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
```

The camera is accessed via the libcamera stack (`rpicam-*` tools), enabled by
`camera_auto_detect=0` + `dtoverlay=ov5647` in `config.txt`.
Frames are captured at `1296×972` and resized to **640×480** in the monitor loop.

> **Note:** `start_x=1` and `bcm2835_v4l2` (MMAL→V4L2 bridge) are loaded but not used
> by the application. Direct `cv2.VideoCapture` on `/dev/video0` was attempted but failed
> — the unicam device does not expose usable V4L2 capture frames on this OS version.

---

## System Info

| Property | Value |
|----------|-------|
| OS | Raspberry Pi OS Bookworm (64-bit) |
| Python | 3.13.5 |
| Timezone | Asia/Jerusalem (IDT, UTC+3) |
| Locale | en_GB.UTF-8 |
| Remote access | WayVNC (enabled, auto-start) |

### Key Python Packages Installed

```
opencv-python    4.12.0.88
dlib             20.0.0
imutils          0.5.4
scipy            1.15.3
pyserial         3.5
cloudinary       1.44.1
requests         2.32.3
python-dotenv    1.0.1
Flask            3.1.1
```

---

## Known Issues / Notes

- **`dyoverlay=uart4`** in `config.txt` is a typo — should be `dtoverlay=uart4`. uart4 is currently not enabled.
- `camera_auto_detect=0` must stay disabled; re-enabling it removes the `dtoverlay=ov5647` effect and the camera disappears.
- The `vc4-kms-v3d` overlay must stay commented out when running headless.
- GPS requires up to 60 seconds outdoors to acquire a fix. The system runs normally with `(0.0, 0.0)` until then.
- After any change to `config.txt` or `cmdline.txt`, a full reboot is required: `sudo reboot`
