# heroku_server_manager — Backend Communication

Handles all HTTP communication between the Raspberry Pi and the Flask backend hosted on Heroku. Telemetry is sent asynchronously to avoid blocking the video processing loop.

## Files

| File | Description |
|------|-------------|
| `heroku_server_manager.py` | `HerokuClient` class — manages drive sessions and telemetry uploads. |

## Class: `HerokuClient`

```python
HerokuClient(base_url, device_id)
```

| Parameter | Description |
|-----------|-------------|
| `base_url` | Root URL of the Heroku API (e.g., `https://your-app.herokuapp.com/api`). Loaded from `.env` as `HEROKU_API_URL`. |
| `device_id` | Unique identifier for this Raspberry Pi (set in `monitor/config.json` as `"raspi_v1"`). |

### Methods

#### `start_drive() → drive_id`

`POST /api/start_drive` with `{"device_id": ...}`.

On success (HTTP 200/201), stores the returned `drive_id` in `self.current_drive_id`. This ID is required for all subsequent telemetry and end-drive calls. Returns `None` on failure.

#### `send_telemetry(ear, perclos, is_distracted, yaw, pitch, lat, lon)`

Fires a background `threading.Thread` to `POST /api/telemetry` with:

```json
{
    "drive_id": 42,
    "ear": 0.31,
    "perclos": 12.5,
    "is_distracted": false,
    "head_yaw": 5.2,
    "head_pitch": -3.1,
    "latitude": 31.95,
    "longitude": 34.78
}
```

The thread is non-blocking — the main loop continues immediately. Failures are silently swallowed (`_post_telemetry` has a bare `except: pass`) to prevent log spam from transient network issues.

Called once per second from the main loop.

#### `end_drive(video_url=None)`

`POST /api/end_drive` with `{"drive_id": ..., "video_url": ...}`.

Called during `DriverMonitor.cleanup()` after the Cloudinary upload completes. The `video_url` is the Cloudinary CDN link to the session recording. Uses a 10-second timeout (longer than telemetry) to ensure the final record is written.

### Error Handling

All methods wrap their HTTP calls in `try/except`. Failures are logged via `SystemLogger` but never raise exceptions, so a network outage does not crash the monitoring system.

## API Endpoints (Backend Contract)

| Method | Endpoint | Request Body | Response |
|--------|----------|-------------|----------|
| `POST` | `/api/start_drive` | `{"device_id": str}` | `{"drive_id": int}` |
| `POST` | `/api/telemetry` | See above | `{"status": "success"}` |
| `POST` | `/api/end_drive` | `{"drive_id": int, "video_url": str}` | `{"status": "success"}` |

## Dependencies

```
requests
```
