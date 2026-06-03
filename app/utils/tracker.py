import logging
from collections import deque
from typing import Dict, Any, List

class PipelineTracker:
    """
    In-memory state tracker to monitor pipeline progress and log buffer.
    """
    def __init__(self) -> None:
        self.status: str = "idle"  # idle, ingesting, news, youtube, screening, rebalancing, recommending, uploading, done, failed
        self.progress: int = 0
        self.current_step: str = "System ready"
        self.error: Any = None
        self.logs: deque = deque(maxlen=200)  # Stores last 200 lines

    def update(self, status: str, progress: int, current_step: str, error: Any = None) -> None:
        self.status = status
        self.progress = progress
        self.current_step = current_step
        if error is not None:
            self.error = error

    def add_log(self, message: str) -> None:
        self.logs.append(message)

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "progress": self.progress,
            "current_step": self.current_step,
            "error": self.error,
            "logs": list(self.logs)
        }

    def reset(self) -> None:
        self.status = "idle"
        self.progress = 0
        self.current_step = "System ready"
        self.error = None

# Global tracker singleton
tracker = PipelineTracker()

class TrackerLoggingHandler(logging.Handler):
    """
    Custom logging handler that intercepts log records and appends them
    to the global tracker's memory buffer.
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            tracker.add_log(msg)
        except Exception:
            self.handleError(record)
