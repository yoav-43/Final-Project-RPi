# gps — Location Services

Reads NMEA sentences from a serial GPS module in a background thread and exposes the latest coordinates to the main loop.

## Files

| File | Description |
|------|-------------|
| `gps_manager.py` | `GPSManager` class — background thread that parses GPS serial data. |

## Hardware

- Compatible with any NMEA-0183 GPS module (e.g., **u-blox NEO-6M**).
- Connected to the Raspberry Pi via UART: default port `/dev/ttyAMA0`, baud rate `38400`.
- Port and baud rate are configurable via `monitor/config.json` (`gps_port` key).

## Class: `GPSManager`

```python
GPSManager(port='/dev/ttyAMA0', baud_rate=38400)
```

### Lifecycle

| Method | Description |
|--------|-------------|
| `start()` | Spawns a daemon thread running `_read_gps_loop()`. Returns immediately. |
| `get_location()` | Returns `(latitude, longitude)` as decimal degrees. Thread-safe read. |
| `stop()` | Sets `self.running = False`, causing the background thread to exit on its next iteration. |

### Background Thread: `_read_gps_loop()`

Opens the serial port and reads lines continuously. For each line that starts with `$GPGGA` or `$GNGGA` (the standard fix data sentence), it calls `_parse_gpgqa()`.

If the serial port cannot be opened (hardware not connected), the thread logs a warning and sets coordinates to `(0.0, 0.0)`. The main application continues without GPS data.

### NMEA Parsing: `_parse_gpgqa(line)`

Parses the latitude and longitude fields from a `$GPGGA` sentence and converts them from **DDMM.MMMM** format to **decimal degrees**:

```
decimal_degrees = DD + (MM.MMMM / 60)
```

Example: `3157.3841` → `31 + (57.3841 / 60)` = `31.9564°`

> Note: The current implementation does not handle the N/S/E/W hemisphere indicators. For southern or western coordinates, the sign would need to be negated. This is sufficient for the project's geographic scope.

## Telemetry Integration

The main loop calls `gps.get_location()` once per second and includes `latitude` and `longitude` in the telemetry payload sent to the backend. If GPS is unavailable, both values are `0.0`.

## Standalone Test

```bash
python3 gps/gps_manager.py
```

Starts the GPS thread, waits 60 seconds, prints the last known location, then stops.

## Dependencies

```
pyserial
```
