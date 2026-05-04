# buzzer — Hardware Alert System

Controls an Arduino-based buzzer that provides immediate auditory feedback to the driver. The Raspberry Pi sends single-character commands over a serial connection; the Arduino firmware translates them into distinct tones.

## Files

| File | Description |
|------|-------------|
| `buzzer.py` | `BuzzerController` class — Python serial interface running on the Raspberry Pi. |
| `buzzer.ino` | Arduino C++ firmware — reads serial commands and drives the buzzer. |

## Hardware Setup

- **Arduino** (Uno or compatible) connected to the Raspberry Pi via USB.
- **Passive buzzer** connected to **pin 6** on the Arduino (configurable via `BUZZER_PIN` in the `.ino`).
- Default serial port on Linux: `/dev/ttyACM0` (set in `monitor/config.json`).

## Protocol

The Raspberry Pi sends a single ASCII byte every frame:

| Byte | State | Arduino Response |
|------|-------|-----------------|
| `b'F'` | Fatigue detected | Continuous 1000 Hz tone |
| `b'D'` | Distraction detected | Double beep at 1500 Hz (150 ms on, 200 ms gap, repeated) |
| `b'O'` | Driver OK | `noTone()` — silence |

On startup, the Arduino plays a two-note melody (2000 Hz → 2500 Hz) to confirm the serial connection is live.

## Class: `BuzzerController`

```python
BuzzerController(port='/dev/ttyACM0', baud_rate=9600)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `port` | `/dev/ttyACM0` | Serial port of the Arduino. |
| `baud_rate` | `9600` | Must match `Serial.begin()` in the `.ino`. |

The constructor waits **2 seconds** after opening the port to allow the Arduino to complete its reset cycle before any commands are sent.

If the Arduino is not connected, the constructor logs an error and sets `self.arduino = None`. All subsequent `send_command` calls are silently skipped, so the rest of the system continues to function.

### Methods

| Method | Sends | Description |
|--------|-------|-------------|
| `alert_fatigue()` | `b'F'` | Triggers continuous high-priority alarm. |
| `alert_distraction()` | `b'D'` | Triggers intermittent medium-priority alarm. |
| `status_ok()` | `b'O'` | Silences the buzzer. |
| `close()` | — | Closes the serial port cleanly. |

## Arduino Firmware Notes

- `tone(pin, freq)` — starts a continuous tone (non-blocking).
- `tone(pin, freq, duration)` — plays a tone for a fixed duration.
- `noTone(pin)` — stops any active tone.
- The `loop()` function is purely reactive: it only acts when a byte is available on `Serial`.

## Standalone Test

```bash
python3 buzzer/buzzer.py
```

Sends a fatigue alert, waits 1 second, then sends OK. Requires a connected Arduino.

## Flashing the Firmware

Open `buzzer.ino` in the Arduino IDE, select the correct board and port, and click Upload. No external libraries are required.
