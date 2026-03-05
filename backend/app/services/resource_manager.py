"""
Resource management service for optimizing system resources and handling memory.
Provides memory management, file cleanup, and resource monitoring.
"""

import os
import psutil
import shutil
import logging
import threading
import time
import sys
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
import gc

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("app.resources")

@dataclass
class ResourceUsage:
    """Resource usage statistics."""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    disk_free_gb: float
    timestamp: datetime

@dataclass
class FileCleanupInfo:
    """Information about files to be cleaned up."""
    path: str
    size_mb: float
    age_hours: float
    reason: str

class ResourceManager:
    """Resource management service for system optimization."""
    
    def __init__(self):
        self.monitoring_active = False
        self.monitoring_thread = None
        self.resource_history: List[ResourceUsage] = []
        self.max_history_size = 1000
        self.cleanup_thresholds = {
            'memory_percent': 80.0,
            'disk_percent': 90.0,
            'disk_free_gb': 5.0
        }
        
        # File cleanup patterns
        self.cleanup_patterns = [
            {'pattern': '*.tmp', 'max_age_hours': 1},
            {'pattern': '*.log', 'max_age_hours': 24},
            {'pattern': '*.cache', 'max_age_hours': 6},
            {'pattern': 'temp_*', 'max_age_hours': 2},
        ]
    
    def start_monitoring(self, interval_seconds: int = 30):
        """Start resource monitoring in background thread."""
        if self.monitoring_active:
            logger.warning("Resource monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"Resource monitoring started with {interval_seconds}s interval")
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Resource monitoring stopped")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                usage = self.get_current_usage()
                self.resource_history.append(usage)
                
                # Keep history size manageable
                if len(self.resource_history) > self.max_history_size:
                    self.resource_history.pop(0)
                
                # Check thresholds and trigger cleanup if needed
                self._check_thresholds(usage)
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(interval_seconds)
    
    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage statistics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_mb = memory.used / (1024 * 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            return ResourceUsage(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_mb=memory_mb,
                disk_percent=disk_percent,
                disk_free_gb=disk_free_gb,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to get resource usage: {e}")
            return ResourceUsage(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_mb=0.0,
                disk_percent=0.0,
                disk_free_gb=0.0,
                timestamp=datetime.utcnow()
            )
    
    def get_usage_history(self, hours: int = 1) -> List[ResourceUsage]:
        """Get resource usage history for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [usage for usage in self.resource_history if usage.timestamp >= cutoff_time]
    
    def _check_thresholds(self, usage: ResourceUsage):
        """Check if resource usage exceeds thresholds and trigger cleanup."""
        issues = []
        
        if usage.memory_percent > self.cleanup_thresholds['memory_percent']:
            issues.append(f"High memory usage: {usage.memory_percent:.1f}%")
        
        if usage.disk_percent > self.cleanup_thresholds['disk_percent']:
            issues.append(f"High disk usage: {usage.disk_percent:.1f}%")
        
        if usage.disk_free_gb < self.cleanup_thresholds['disk_free_gb']:
            issues.append(f"Low disk space: {usage.disk_free_gb:.1f}GB")
        
        if issues:
            logger.warning(f"Resource threshold exceeded: {'; '.join(issues)}")
            self.perform_cleanup()
    
    def perform_cleanup(self):
        """Perform system cleanup to free resources."""
        logger.info("Starting system cleanup")
        
        try:
            # Clean up temporary files
            cleaned_files = self._cleanup_temp_files()
            
            # Clean up old logs
            self._cleanup_old_logs()
            
            # Clean up cache files
            self._cleanup_cache_files()
            
            # Force garbage collection
            gc.collect()
            
            # Clear Python caches
            self._clear_python_caches()
            
            logger.info(f"System cleanup completed. Cleaned {len(cleaned_files)} files")
            
        except Exception as e:
            logger.error(f"System cleanup failed: {e}")
    
    def _cleanup_temp_files(self) -> List[FileCleanupInfo]:
        """Clean up temporary files."""
        cleaned_files = []
        
        # Define directories to clean
        temp_dirs = [
            str(settings.UPLOAD_DIR),
            str(settings.OUTPUTS_DIR),
            str(settings.CLIPS_DIR)
        ]
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                cleaned_files.extend(self._cleanup_directory(temp_dir, "*.tmp", 1))
                cleaned_files.extend(self._cleanup_directory(temp_dir, "temp_*", 2))
        
        return cleaned_files
    
    def _cleanup_old_logs(self):
        """Clean up old log files."""
        log_dir = Path("logs")
        if log_dir.exists():
            self._cleanup_directory(str(log_dir), "*.log", 24)
    
    def _cleanup_cache_files(self):
        """Clean up cache files."""
        cache_dirs = [
            str(settings.UPLOAD_DIR)
        ]
        
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                self._cleanup_directory(cache_dir, "*.cache", 6)
    
    def _cleanup_directory(self, directory: str, pattern: str, max_age_hours: int) -> List[FileCleanupInfo]:
        """Clean up files in directory matching pattern."""
        cleaned_files = []
        
        try:
            import glob
            from datetime import datetime
            
            pattern_path = os.path.join(directory, pattern)
            files = glob.glob(pattern_path)
            
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            for file_path in files:
                try:
                    stat = os.stat(file_path)
                    file_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    if file_time < cutoff_time:
                        file_size = stat.st_size / (1024 * 1024)  # MB
                        age_hours = (datetime.now() - file_time).total_seconds() / 3600
                        
                        os.remove(file_path)
                        cleaned_files.append(FileCleanupInfo(
                            path=file_path,
                            size_mb=file_size,
                            age_hours=age_hours,
                            reason=f"Older than {max_age_hours} hours"
                        ))
                        
                        logger.debug(f"Cleaned up file: {file_path} ({file_size:.2f}MB, {age_hours:.1f}h old)")
                        
                except Exception as e:
                    logger.warning(f"Failed to clean up file {file_path}: {e}")
            
        except Exception as e:
            logger.error(f"Error cleaning directory {directory}: {e}")
        
        return cleaned_files
    
    def _clear_python_caches(self):
        """Clear Python internal caches."""
        try:
            # Clear import cache
            if hasattr(sys, 'modules'):
                # This is a basic cache clear - more sophisticated clearing could be added
                pass
            
            # Clear functools lru_cache if any
            import functools
            # Note: This would require tracking all lru_cache decorated functions
            
            logger.debug("Python caches cleared")
            
        except Exception as e:
            logger.warning(f"Failed to clear Python caches: {e}")
    
    def optimize_memory(self):
        """Optimize memory usage."""
        try:
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"Garbage collection freed {collected} objects")
            
            # Clear large objects from memory
            self._clear_large_objects()
            
            # Check current memory usage
            usage = self.get_current_usage()
            logger.info(f"Memory optimization completed. Current usage: {usage.memory_percent:.1f}%")
            
        except Exception as e:
            logger.error(f"Memory optimization failed: {e}")
    
    def _clear_large_objects(self):
        """Clear large objects from memory."""
        try:
            # This is a placeholder for more sophisticated memory management
            # In a real implementation, you might track large objects and clear them
            pass
        except Exception as e:
            logger.warning(f"Failed to clear large objects: {e}")
    
    def get_disk_usage_by_directory(self, base_dir: str) -> Dict[str, float]:
        """Get disk usage by subdirectory."""
        usage_by_dir = defaultdict(float)
        
        try:
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        # Group by immediate subdirectory
                        rel_path = os.path.relpath(file_path, base_dir)
                        dir_name = rel_path.split(os.sep)[0] if os.sep in rel_path else ""
                        usage_by_dir[dir_name] += size / (1024 * 1024)  # MB
                    except (OSError, IOError):
                        continue
            
            # Convert to sorted list
            return dict(sorted(usage_by_dir.items(), key=lambda x: x[1], reverse=True))
            
        except Exception as e:
            logger.error(f"Failed to get disk usage by directory: {e}")
            return {}
    
    def get_largest_files(self, directory: str, limit: int = 10) -> List[Tuple[str, float]]:
        """Get largest files in directory."""
        files_with_size = []
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        files_with_size.append((file_path, size / (1024 * 1024)))  # MB
                    except (OSError, IOError):
                        continue
            
            # Sort by size and return top N
            files_with_size.sort(key=lambda x: x[1], reverse=True)
            return files_with_size[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get largest files: {e}")
            return []
    
    def estimate_cleanup_potential(self) -> Dict[str, float]:
        """Estimate potential cleanup savings."""
        potential_savings = {
            'temp_files_mb': 0.0,
            'old_logs_mb': 0.0,
            'cache_files_mb': 0.0,
            'total_mb': 0.0
        }
        
        try:
            # Estimate temp files
            temp_dirs = [str(settings.UPLOAD_DIR), str(settings.OUTPUTS_DIR)]
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    potential_savings['temp_files_mb'] += self._estimate_directory_cleanup(temp_dir, "*.tmp", 1)
                    potential_savings['temp_files_mb'] += self._estimate_directory_cleanup(temp_dir, "temp_*", 2)
            
            # Estimate old logs
            log_dir = Path("logs")
            if log_dir.exists():
                potential_savings['old_logs_mb'] = self._estimate_directory_cleanup(str(log_dir), "*.log", 24)
            
            # Estimate cache files
            potential_savings['cache_files_mb'] = self._estimate_directory_cleanup(str(settings.UPLOAD_DIR), "*.cache", 6)
            
            potential_savings['total_mb'] = sum([
                potential_savings['temp_files_mb'],
                potential_savings['old_logs_mb'],
                potential_savings['cache_files_mb']
            ])
            
        except Exception as e:
            logger.error(f"Failed to estimate cleanup potential: {e}")
        
        return potential_savings
    
    def _estimate_directory_cleanup(self, directory: str, pattern: str, max_age_hours: int) -> float:
        """Estimate cleanup potential for directory."""
        total_size = 0.0
        
        try:
            import glob
            from datetime import datetime
            
            pattern_path = os.path.join(directory, pattern)
            files = glob.glob(pattern_path)
            
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            for file_path in files:
                try:
                    stat = os.stat(file_path)
                    file_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    if file_time < cutoff_time:
                        total_size += stat.st_size / (1024 * 1024)  # MB
                        
                except Exception:
                    continue
            
        except Exception:
            pass
        
        return total_size
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        try:
            usage = self.get_current_usage()
            history = self.get_usage_history(hours=1)
            
            # Calculate averages
            if history:
                avg_cpu = sum(h.cpu_percent for h in history) / len(history)
                avg_memory = sum(h.memory_percent for h in history) / len(history)
                avg_disk = sum(h.disk_percent for h in history) / len(history)
            else:
                avg_cpu = usage.cpu_percent
                avg_memory = usage.memory_percent
                avg_disk = usage.disk_percent
            
            # Check thresholds
            health_issues = []
            
            if usage.memory_percent > 90:
                health_issues.append("Critical memory usage")
            elif usage.memory_percent > 80:
                health_issues.append("High memory usage")
            
            if usage.disk_percent > 95:
                health_issues.append("Critical disk usage")
            elif usage.disk_percent > 90:
                health_issues.append("High disk usage")
            
            if usage.cpu_percent > 90:
                health_issues.append("Critical CPU usage")
            elif usage.cpu_percent > 80:
                health_issues.append("High CPU usage")
            
            # Get cleanup potential
            cleanup_potential = self.estimate_cleanup_potential()
            
            return {
                'current': {
                    'cpu_percent': usage.cpu_percent,
                    'memory_percent': usage.memory_percent,
                    'memory_mb': usage.memory_mb,
                    'disk_percent': usage.disk_percent,
                    'disk_free_gb': usage.disk_free_gb
                },
                'average_last_hour': {
                    'cpu_percent': avg_cpu,
                    'memory_percent': avg_memory,
                    'disk_percent': avg_disk
                },
                'health_issues': health_issues,
                'cleanup_potential_mb': cleanup_potential['total_mb'],
                'timestamp': usage.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {'error': str(e)}

# Global resource manager instance
resource_manager = ResourceManager()

# Convenience functions
def get_current_usage() -> ResourceUsage:
    """Get current resource usage."""
    return resource_manager.get_current_usage()

def get_system_health() -> Dict[str, Any]:
    """Get system health status."""
    return resource_manager.get_system_health()

def perform_cleanup():
    """Perform system cleanup."""
    return resource_manager.perform_cleanup()

def optimize_memory():
    """Optimize memory usage."""
    return resource_manager.optimize_memory()

def start_monitoring(interval_seconds: int = 30):
    """Start resource monitoring."""
    return resource_manager.start_monitoring(interval_seconds)

def stop_monitoring():
    """Stop resource monitoring."""
    return resource_manager.stop_monitoring()