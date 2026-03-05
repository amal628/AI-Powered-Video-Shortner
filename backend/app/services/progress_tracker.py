import threading
import time
from typing import Dict, Optional


class ProcessingProgressTracker:
    """
    In-memory progress tracker keyed by file_id.
    Safe for concurrent access across request threads in a single process.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, Dict[str, object]] = {}
        self._ttl_seconds = 3600

    def start(self, file_id: str, status: str = "starting", progress: int = 0, message: str = "") -> None:
        now = time.time()
        with self._lock:
            self._tasks[file_id] = {
                "file_id": file_id,
                "status": status,
                "progress": max(0, min(100, int(progress))),
                "message": message or "Starting...",
                "error": "",
                "updated_at": now,
                "started_at": now,
                "completed_at": None,
            }

    def update(self, file_id: str, status: Optional[str] = None, progress: Optional[int] = None, message: Optional[str] = None) -> None:
        now = time.time()
        with self._lock:
            task = self._tasks.get(file_id)
            if not task:
                return

            if progress is not None:
                safe_progress = max(0, min(100, int(progress)))
                previous_value = task.get("progress", 0)
                previous = int(previous_value) if isinstance(previous_value, (int, float, str)) else 0
                task["progress"] = max(previous, safe_progress)

            if status is not None:
                task["status"] = status
            if message is not None:
                task["message"] = message

            task["updated_at"] = now

    def complete(self, file_id: str, message: str = "Completed") -> None:
        now = time.time()
        with self._lock:
            task = self._tasks.get(file_id)
            if not task:
                return
            task["status"] = "completed"
            task["progress"] = 100
            task["message"] = message
            task["error"] = ""
            task["updated_at"] = now
            task["completed_at"] = now

    def fail(self, file_id: str, message: str) -> None:
        now = time.time()
        with self._lock:
            task = self._tasks.get(file_id)
            if not task:
                self._tasks[file_id] = {
                    "file_id": file_id,
                    "status": "failed",
                    "progress": 100,
                    "message": "Processing failed",
                    "error": message or "Unknown error",
                    "updated_at": now,
                    "started_at": now,
                    "completed_at": now,
                }
                return
            task["status"] = "failed"
            progress_value = task.get("progress", 0)
            progress_int = int(progress_value) if isinstance(progress_value, (int, float, str)) else 0
            task["progress"] = max(progress_int, 100)
            task["message"] = "Processing failed"
            task["error"] = message or "Unknown error"
            task["updated_at"] = now
            task["completed_at"] = now

    def get(self, file_id: str) -> Optional[Dict[str, object]]:
        with self._lock:
            task = self._tasks.get(file_id)
            if not task:
                return None
            return dict(task)

    def cleanup(self) -> None:
        cutoff = time.time() - self._ttl_seconds
        with self._lock:
            stale_ids = []
            for file_id, task in self._tasks.items():
                updated_at_value = task.get("updated_at", 0)
                if isinstance(updated_at_value, (int, float, str)):
                    updated_at = float(updated_at_value)
                else:
                    updated_at = 0.0
                if updated_at < cutoff:
                    stale_ids.append(file_id)
            for file_id in stale_ids:
                self._tasks.pop(file_id, None)


progress_tracker = ProcessingProgressTracker()
