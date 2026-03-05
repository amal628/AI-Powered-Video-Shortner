# backend/app/services/metrics_service.py

import time
import logging
from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import asyncio
import json

logger = logging.getLogger(__name__)


@dataclass
class MetricRecord:
    """Individual metric record."""
    name: str
    value: float
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class MetricsService:
    """
    Service for recording and managing system metrics.
    Provides real-time monitoring and historical data storage.
    """

    def __init__(self, max_history_size: int = 10000):
        self.metrics_history: List[MetricRecord] = []
        self.metrics_summary: Dict[str, Dict[str, Union[float, None]]] = defaultdict(lambda: {
            "count": 0.0,
            "sum": 0.0,
            "min": float('inf'),
            "max": float('-inf'),
            "avg": 0.0
        })
        self.max_history_size = max_history_size
        self._lock = threading.Lock()
        self._cleanup_interval = 3600  # 1 hour in seconds
        self._last_cleanup = time.time()

    def record_metric(
        self,
        name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a metric with optional metadata.
        """
        try:
            with self._lock:
                record = MetricRecord(
                    name=name,
                    value=value,
                    timestamp=datetime.utcnow(),
                    metadata=metadata or {}
                )
                
                self.metrics_history.append(record)
                
                # Update summary statistics
                summary = self.metrics_summary[name]
                summary["count"] = (summary["count"] or 0.0) + 1.0
                summary["sum"] = (summary["sum"] or 0.0) + value
                summary["min"] = min((summary["min"] or float('inf')), value)
                summary["max"] = max((summary["max"] or float('-inf')), value)
                summary["avg"] = summary["sum"] / summary["count"]
                
                # Maintain history size limit
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                # Periodic cleanup
                current_time = time.time()
                if current_time - self._last_cleanup > self._cleanup_interval:
                    self._cleanup_old_metrics()
                    self._last_cleanup = current_time
                    
        except Exception as e:
            logger.error(f"Failed to record metric {name}: {e}")

    async def record_system_metric(
        self,
        name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Async wrapper for recording system metrics.
        """
        self.record_metric(name, value, metadata)

    def get_metric_summary(self, name: str) -> Optional[Dict[str, Union[float, None]]]:
        """
        Get summary statistics for a specific metric.
        """
        with self._lock:
            if name in self.metrics_summary:
                summary = dict(self.metrics_summary[name])
                # Convert inf values to None for JSON serialization
                if summary["min"] == float('inf'):
                    summary["min"] = None
                if summary["max"] == float('-inf'):
                    summary["max"] = None
                return summary
            return None

    def get_all_metrics_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get summary statistics for all metrics.
        """
        with self._lock:
            result = {}
            for name, summary in self.metrics_summary.items():
                summary_copy = dict(summary)
                # Convert inf values to None for JSON serialization
                if summary_copy["min"] == float('inf'):
                    summary_copy["min"] = None
                if summary_copy["max"] == float('-inf'):
                    summary_copy["max"] = None
                result[name] = summary_copy
            return result

    def get_metrics_history(
        self,
        name: Optional[str] = None,
        hours: float = 24,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical metric data.
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            if name:
                # Filter by metric name
                history = [
                    asdict(record) for record in self.metrics_history
                    if record.name == name and record.timestamp >= cutoff_time
                ]
            else:
                # Get all metrics
                history = [
                    asdict(record) for record in self.metrics_history
                    if record.timestamp >= cutoff_time
                ]
            
            # Apply limit if specified
            if limit and len(history) > limit:
                history = history[-limit:]
            
            return history

    def get_recent_metrics(
        self,
        name: Optional[str] = None,
        minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get recent metric data for quick monitoring.
        """
        return self.get_metrics_history(name, hours=minutes/60, limit=None)

    def get_metric_trends(
        self,
        name: str,
        hours: int = 24,
        interval_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get metric trends over time with specified interval.
        """
        history = self.get_metrics_history(name, hours)
        if not history:
            return []
        
        # Group by time intervals
        trends = []
        current_time = datetime.utcnow()
        interval_seconds = interval_minutes * 60
        
        # Create time buckets
        for i in range(0, hours * 60, interval_minutes):
            bucket_end = current_time - timedelta(minutes=i)
            bucket_start = bucket_end - timedelta(minutes=interval_minutes)
            
            # Filter records in this bucket
            bucket_records = [
                record for record in history
                if bucket_start <= datetime.fromisoformat(record["timestamp"]) <= bucket_end
            ]
            
            if bucket_records:
                values = [record["value"] for record in bucket_records]
                trends.append({
                    "timestamp": bucket_end.isoformat(),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                })
        
        return list(reversed(trends))

    def get_system_health_metrics(self) -> Dict[str, Any]:
        """
        Get key system health metrics.
        """
        health_metrics = {}
        
        # Get recent task submission rates
        task_submitted_trends = self.get_metric_trends("task_submitted", hours=1, interval_minutes=5)
        if task_submitted_trends:
            health_metrics["task_submission_rate"] = {
                "current": task_submitted_trends[-1]["avg"],
                "trend": "increasing" if len(task_submitted_trends) > 1 and 
                         task_submitted_trends[-1]["avg"] > task_submitted_trends[-2]["avg"] else "decreasing"
            }
        
        # Get task completion rates
        task_completed_trends = self.get_metric_trends("task_completed", hours=1, interval_minutes=5)
        if task_completed_trends:
            health_metrics["task_completion_rate"] = {
                "current": task_completed_trends[-1]["avg"],
                "trend": "increasing" if len(task_completed_trends) > 1 and 
                         task_completed_trends[-1]["avg"] > task_completed_trends[-2]["avg"] else "decreasing"
            }
        
        # Get error rates
        error_trends = self.get_metric_trends("task_error", hours=1, interval_minutes=5)
        if error_trends:
            health_metrics["error_rate"] = {
                "current": error_trends[-1]["avg"],
                "trend": "increasing" if len(error_trends) > 1 and 
                         error_trends[-1]["avg"] > error_trends[-2]["avg"] else "decreasing"
            }
        
        # Get queue size
        queue_size_summary = self.get_metric_summary("queue_size")
        if queue_size_summary:
            health_metrics["queue_size"] = {
                "current": queue_size_summary["avg"],
                "max": queue_size_summary["max"]
            }
        
        return health_metrics

    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than 7 days to prevent memory issues."""
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        with self._lock:
            self.metrics_history = [
                record for record in self.metrics_history
                if record.timestamp >= cutoff_time
            ]
            logger.info(f"Cleaned up old metrics, remaining: {len(self.metrics_history)}")

    def export_metrics(self, format: str = "json") -> str:
        """
        Export metrics data in specified format.
        """
        if format.lower() == "json":
            data = {
                "metrics_history": [
                    asdict(record) for record in self.metrics_history[-1000:]  # Last 1000 records
                ],
                "metrics_summary": self.get_all_metrics_summary(),
                "export_time": datetime.utcnow().isoformat()
            }
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def clear_metrics(self) -> None:
        """Clear all stored metrics (useful for testing)."""
        with self._lock:
            self.metrics_history.clear()
            self.metrics_summary.clear()
            logger.info("Cleared all metrics data")


# Global metrics service instance
metrics_service = MetricsService()

# Convenience functions for easy importing
def record_metric(name: str, value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Record a metric."""
    metrics_service.record_metric(name, value, metadata)

async def record_system_metric(name: str, value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Record a system metric."""
    await metrics_service.record_system_metric(name, value, metadata)

def get_metric_summary(name: str) -> Optional[Dict[str, Union[float, None]]]:
    """Get metric summary."""
    return metrics_service.get_metric_summary(name)

def get_all_metrics_summary() -> Dict[str, Dict[str, float]]:
    """Get all metrics summary."""
    return metrics_service.get_all_metrics_summary()

def get_metrics_history(name: Optional[str] = None, hours: int = 24, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get metrics history."""
    return metrics_service.get_metrics_history(name, hours, limit)

def get_system_health_metrics() -> Dict[str, Any]:
    """Get system health metrics."""
    return metrics_service.get_system_health_metrics()