import logging
import sys
import os
from datetime import datetime

class ImmediateFlushHandler(logging.StreamHandler):
    """Handler that flushes immediately after each emit"""
    def emit(self, record):
        super().emit(record)
        self.flush()
        # Force flush underlying stream
        if hasattr(self.stream, 'flush'):
            self.stream.flush()

class ImmediateFlushFileHandler(logging.FileHandler):
    """File handler that flushes immediately after each emit"""
    def emit(self, record):
        super().emit(record)
        self.flush()
        # Force OS-level flush
        if hasattr(self.stream, 'fileno'):
            try:
                os.fsync(self.stream.fileno())
            except (OSError, AttributeError):
                pass

def setup_logging(log_dir=None):
    """
    Set up logging to both console and file with immediate flushing.
    Includes filename and line number in log format.
    """
    if log_dir is None:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(script_dir, '.cache', 'logs')
    
    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create log filename with timestamp
    log_filename = os.path.join(log_dir, f'domain_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Custom formatter with filename and line number
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with immediate flushing
    console_handler = ImmediateFlushHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with immediate flushing
    file_handler = ImmediateFlushFileHandler(log_filename, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Log initial message
    logger.info(f"Logging initialized. Log file: {log_filename}")
    
    return logger, log_filename

# Create a logger instance for this module
logger = logging.getLogger(__name__)

