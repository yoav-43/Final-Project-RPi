import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time
from datetime import datetime

class SystemLogger:
    """
    Lightweight console logger with ANSI color-coded output.
    Each module instantiates its own logger with a descriptive name
    that appears in every log line for easy filtering.
    """
    
    # ANSI escape codes for terminal color output.
    COLORS = {
        "INFO": "\033[92m",    # Green
        "DEBUG": "\033[94m",   # Blue
        "WARNING": "\033[93m", # Yellow
        "ERROR": "\033[91m",   # Red
        "END": "\033[0m"       # Reset to default
    }

    def __init__(self, name="System", log_file=None):
        self.name = name
        self._file = open(log_file, "w") if log_file else None

    def log(self, level, message):
        """Prints a color-coded, timestamped log entry to stdout."""
        color = self.COLORS.get(level, self.COLORS["END"])
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f"[{level}] [{self.name}] {timestamp} - {message}"
        print(f"{color}{line}{self.COLORS['END']}")
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()

    def log_raw(self, level, message):
        """Like log(), but the message is printed as-is so callers can embed their own ANSI colors."""
        color = self.COLORS.get(level, self.COLORS["END"])
        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = f"[{level}] [{self.name}] {timestamp} -"
        print(f"{color}{prefix}{self.COLORS['END']} {message}")
        if self._file:
            # Strip ANSI codes for the file
            import re
            clean = re.sub(r'\033\[[0-9;]*m', '', message)
            self._file.write(f"{prefix} {clean}\n")
            self._file.flush()

# --- Standalone Test ---
if __name__ == "__main__":
    logger = SystemLogger("LoggerTest")
    logger.log("INFO", "This is an info message.")
    logger.log("WARNING", "This is a warning.")
    logger.log("ERROR", "This is an error.")
