# logger — System Logging Utility

Provides color-coded, timestamped console output used by every module in the project.

## Files

| File | Description |
|------|-------------|
| `logger.py` | `SystemLogger` class — ANSI-colored log output with module name and timestamp. |

## Class: `SystemLogger`

```python
SystemLogger(name="System")
```

Each module instantiates its own logger with a descriptive name (e.g., `"GPS"`, `"Buzzer"`, `"MainMonitor"`). The name appears in every log line for easy filtering.

### `log(level, message)`

Prints a formatted line to stdout:

```
[LEVEL] [ModuleName] HH:MM:SS - message
```

| Level | Color | Typical Use |
|-------|-------|-------------|
| `INFO` | Green | Normal operational events (startup, connection confirmed, upload success). |
| `DEBUG` | Blue | Per-second telemetry values (EAR, PERCLOS, yaw). |
| `WARNING` | Yellow | Non-fatal issues (GPS unavailable, serial write failed). |
| `ERROR` | Red | Fatal or significant failures (camera not found, API key missing). |

The main loop selects the log level dynamically based on driver state:
- `ERROR` when fatigue is detected.
- `WARNING` when distraction is detected.
- `DEBUG` when the driver is focused.

## Usage

```python
from logger.logger import SystemLogger

logger = SystemLogger("MyModule")
logger.log("INFO", "Module started.")
logger.log("WARNING", "Something unexpected happened.")
```

## Standalone Test

```bash
python3 logger/logger.py
```

Prints one line at each level to verify ANSI colors render correctly in your terminal.
