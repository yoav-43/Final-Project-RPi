import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time
from datetime import datetime

class SystemLogger:
    """
    Handles system logging with color-coded output for console debugging.
    """
    
    # ANSI Color Codes
    COLORS = {
        "INFO": "\033[92m",    # Green
        "DEBUG": "\033[94m",   # Blue
        "WARNING": "\033[93m", # Yellow
        "ERROR": "\033[91m",   # Red
        "END": "\033[0m"       # Reset
    }

    def __init__(self, name="System"):
        """
        Initialize the logger instance.
        
        Args:
            name (str): The name of the module using the logger.
        """
        self.name = name

    def log(self, level, message):
        """
        Logs a message with a timestamp and color coding.

        Args:
            level (str): The severity level (INFO, DEBUG, WARNING, ERROR).
            message (str): The message content.
        """
        color = self.COLORS.get(level, self.COLORS["END"])
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{color}[{level}] [{self.name}] {timestamp} - {message}{self.COLORS['END']}")

# --- Main Execution for Testing ---
if __name__ == "__main__":
    # Test the logger
    logger = SystemLogger("LoggerTest")
    logger.log("INFO", "This is an info message.")
    logger.log("WARNING", "This is a warning.")
    logger.log("ERROR", "This is an error.")