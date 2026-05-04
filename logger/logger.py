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

    def __init__(self, name="System"):
        """
        Args:
            name (str): Display name of the module using this logger instance.
        """
        self.name = name

    def log(self, level, message):
        """
        Prints a color-coded, timestamped log entry to stdout.

        Output format: [LEVEL] [ModuleName] HH:MM:SS - message

        Args:
            level (str): Severity level — one of INFO, DEBUG, WARNING, ERROR.
            message (str): The log message content.
        """
        color = self.COLORS.get(level, self.COLORS["END"])
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{color}[{level}] [{self.name}] {timestamp} - {message}{self.COLORS['END']}")

# --- Standalone Test ---
if __name__ == "__main__":
    logger = SystemLogger("LoggerTest")
    logger.log("INFO", "This is an info message.")
    logger.log("WARNING", "This is a warning.")
    logger.log("ERROR", "This is an error.")
