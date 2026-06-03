import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_file: str, level: str = "INFO") -> logging.Logger:
    """
    Generates a shared logger instance configured with rotating file handlers and console loggers.
    
    Args:
        name: Name of the logger.
        log_file: Path to write log files.
        level: Minimum level to log.
        
    Returns:
        Logger instance.
    """
    # Ensure target log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    # Prevent adding handlers multiple times if logger is already configured
    if logger.handlers:
        return logger

    # Resolve log level
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logger.setLevel(numeric_level)

    # Standard log format
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler (5MB = 5,242,880 bytes)
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5242880,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # Fallback for read-only filesystem (e.g. Vercel)
        logger.warning(f"Could not create file log handler ({log_file}): {str(e)}. Logging to file disabled.")

    # Register Tracker handler to intercept logs for the Web UI
    try:
        from app.utils.tracker import TrackerLoggingHandler
        tracker_handler = TrackerLoggingHandler()
        tracker_handler.setLevel(numeric_level)
        tracker_handler.setFormatter(formatter)
        logger.addHandler(tracker_handler)
    except ImportError:
        pass

    return logger
