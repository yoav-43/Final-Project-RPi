# logger — System Logging Utility

Provides color-coded, timestamped console output used by every module in the project. Also writes a clean (no ANSI codes) log to a file when configured.

## Files

| File | Description |
|------|-------------|
| `logger.py` | `SystemLogger` class — ANSI-colored terminal output + optional file logging. |

## Class: `SystemLogger`

```python
SystemLogger(name="System", log_file=None)
```

| Parameter | Description |
|-----------|-------------|
| `name` | Display name of the module (e.g. `"GPS"`, `"MainMonitor"`). Appears in every log line. |
| `log_file` | Optional path to a log file. If provided, each log line is also written there (ANSI codes stripped). File is opened in **write** mode — each run overwrites the previous log. |

The `MainMonitor` logger writes to `latest.log` in the project root.

### `log(level, message)`

Prints a formatted, fully-colored line to stdout and writes a clean version to the log file:

```
[LEVEL] [ModuleName] HH:MM:SS - message
```

### `log_raw(level, message)`

Like `log()`, but only the prefix (`[LEVEL] [ModuleName] HH:MM:SS -`) is colored. The message is printed as-is, allowing callers to embed their own per-word ANSI colors. Used by the main monitor to color individual stats red/green based on threshold violations.

| Level | Color | Typical Use |
|-------|-------|-------------|
| `INFO` | Green | Normal operational events (startup, connection confirmed, upload success). |
| `DEBUG` | Blue | Per-second telemetry values (EAR, PERCLOS, yaw) — driver is focused. |
| `WARNING` | Yellow | Distraction detected or non-fatal issues. |
| `ERROR` | Red | Fatigue detected or significant failures. |

## Usage

```python
from logger.logger import SystemLogger

logger = SystemLogger("MyModule", log_file="latest.log")
logger.log("INFO", "Module started.")
logger.log_raw("DEBUG", "\033[92mEAR:0.31\033[0m | \033[91mPERCLOS:30%\033[0m")
```

## Standalone Test

```bash
python3 logger/logger.py
```

Prints one line at each level to verify ANSI colors render correctly in your terminal.
