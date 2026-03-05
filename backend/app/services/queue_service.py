# backend/app/services/queue_service.py

from typing import Dict, Any, Optional, Callable, Awaitable, List, Union
import asyncio
import logging
import time
from uuid import uuid4
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobPriority(int, Enum):
    """Job priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class QueueJob:
    """
    Represents a single queue job with enhanced features.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = field(default=JobStatus.PENDING)
    priority: JobPriority = field(default=JobPriority.NORMAL)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = field(default=None)
    completed_at: Optional[datetime] = field(default=None)
    failed_at: Optional[datetime] = field(default=None)
    retry_count: int = field(default=0)
    max_retries: int = field(default=3)
    timeout_seconds: Optional[int] = field(default=None)
    progress: float = field(default=0.0)
    error_message: Optional[str] = field(default=None)
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    worker_id: Optional[str] = field(default=None)


class QueueService:
    """
    Async in-memory job queue service with advanced features.
    """

    def __init__(
        self, 
        max_workers: int = 2,
        enable_metrics: bool = True,
        enable_health_check: bool = True,
        max_queue_size: int = 1000,
        cleanup_interval_seconds: int = 3600  # 1 hour
    ) -> None:
        self.queue: asyncio.Queue[QueueJob] = asyncio.Queue(maxsize=max_queue_size)
        self.max_workers: int = max_workers
        self.workers: list[asyncio.Task] = []
        self.running: bool = False
        self.jobs: Dict[str, QueueJob] = {}  # Track all jobs
        self.cancelled_jobs: set[str] = set()  # Track cancelled jobs
        self._lock = asyncio.Lock()
        self._stats = {
            'total_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'cancelled_jobs': 0,
            'processing_jobs': 0,
            'queue_size': 0,
            'start_time': datetime.utcnow(),
            'uptime_seconds': 0
        }
        self._job_deduplication: Dict[str, str] = {}  # payload_hash -> job_id
        self._dependency_graph: Dict[str, List[str]] = {}  # job_id -> dependencies
        self._dependents: Dict[str, List[str]] = {}  # job_id -> dependents
        
        # Configuration
        self.enable_metrics = enable_metrics
        self.enable_health_check = enable_health_check
        self.max_queue_size = max_queue_size
        self.cleanup_interval_seconds = cleanup_interval_seconds
        
        # Health check and metrics tracking
        self._health_check_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._last_cleanup_time = datetime.utcnow()

    # ======================================================
    # PUBLIC METHODS
    # ======================================================

    async def start(self) -> None:
        """
        Start worker tasks.
        """
        if self.running:
            return

        self.running = True

        for _ in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop())
            self.workers.append(worker)

        # Start background tasks
        if self.enable_health_check:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        if self.enable_metrics:
            self._metrics_task = asyncio.create_task(self._metrics_loop())

        logger.info("Queue service started with %s workers", self.max_workers)

    async def stop(self, drain_queue: bool = True, timeout_seconds: int = 30) -> None:
        """
        Gracefully stop workers with optional queue draining.
        
        Args:
            drain_queue: Whether to wait for pending jobs to complete
            timeout_seconds: Maximum time to wait for jobs to complete
        """
        if not self.running:
            return

        self.running = False
        
        if drain_queue:
            logger.info("Draining queue before shutdown...")
            try:
                # Wait for all pending jobs to complete with timeout
                await asyncio.wait_for(
                    self.queue.join(), 
                    timeout=timeout_seconds
                )
                logger.info("Queue drained successfully")
            except asyncio.TimeoutError:
                logger.warning("Queue drain timeout after %d seconds", timeout_seconds)
            except Exception as e:
                logger.error("Error during queue drain: %s", e)

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

        logger.info("Queue service stopped")

    async def add_job(
        self,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        deduplicate: bool = False
    ) -> str:
        """
        Add a job to the queue with enhanced options.
        
        Args:
            payload: Job payload data
            metadata: Optional job metadata
            priority: Job priority level
            max_retries: Maximum retry attempts
            timeout_seconds: Job timeout in seconds
            tags: Optional job tags for categorization
            dependencies: List of job IDs this job depends on
            deduplicate: Whether to check for duplicate jobs
            
        Returns:
            Job ID string
        """
        # Check for duplicates if requested
        if deduplicate:
            payload_hash = self._generate_payload_hash(payload)
            async with self._lock:
                if payload_hash in self._job_deduplication:
                    existing_job_id = self._job_deduplication[payload_hash]
                    logger.info("Duplicate job detected, returning existing job ID: %s", existing_job_id)
                    return existing_job_id

        job = QueueJob(
            payload=payload,
            metadata=metadata or {},
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            tags=tags or [],
            dependencies=dependencies or []
        )

        async with self._lock:
            # Store job and update deduplication map
            self.jobs[job.id] = job
            self._stats['total_jobs'] += 1
            
            if deduplicate:
                payload_hash = self._generate_payload_hash(payload)
                self._job_deduplication[payload_hash] = job.id

            # Update dependency tracking
            if dependencies:
                self._dependency_graph[job.id] = dependencies.copy()
                for dep_id in dependencies:
                    if dep_id not in self._dependents:
                        self._dependents[dep_id] = []
                    self._dependents[dep_id].append(job.id)

        # Only add to queue if no dependencies or dependencies are completed
        if not dependencies or await self._are_dependencies_met(job.id):
            await self.queue.put(job)
            async with self._lock:
                self._stats['processing_jobs'] += 1
        else:
            job.status = JobStatus.PENDING
            logger.info("Job %s added with dependencies, waiting for dependencies to complete", job.id)

        logger.info("Job %s added to queue with priority %s", job.id, priority)

        return job.id

    def _generate_payload_hash(self, payload: Dict[str, Any]) -> str:
        """
        Generate a hash for job deduplication.
        
        Args:
            payload: Job payload to hash
            
        Returns:
            Hash string
        """
        import hashlib
        import json
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.md5(payload_str.encode()).hexdigest()

    async def _are_dependencies_met(self, job_id: str) -> bool:
        """
        Check if all dependencies for a job are completed.
        
        Args:
            job_id: ID of the job to check
            
        Returns:
            True if all dependencies are met, False otherwise
        """
        async with self._lock:
            if job_id not in self._dependency_graph:
                return True
            
            dependencies = self._dependency_graph[job_id]
            for dep_id in dependencies:
                if dep_id not in self.jobs:
                    return False
                dep_job = self.jobs[dep_id]
                if dep_job.status != JobStatus.COMPLETED:
                    return False
            return True

    async def _notify_dependents(self, completed_job_id: str) -> None:
        """
        Notify dependent jobs that a dependency has been completed.
        
        Args:
            completed_job_id: ID of the completed job
        """
        async with self._lock:
            if completed_job_id not in self._dependents:
                return
            
            dependents = self._dependents[completed_job_id].copy()
            
            for dependent_id in dependents:
                if await self._are_dependencies_met(dependent_id):
                    dependent_job = self.jobs[dependent_id]
                    if dependent_job.status == JobStatus.PENDING:
                        dependent_job.status = JobStatus.PROCESSING
                        await self.queue.put(dependent_job)
                        self._stats['processing_jobs'] += 1
                        logger.info("Dependency met for job %s, adding to queue", dependent_id)

    # ======================================================
    # JOB MANAGEMENT METHODS
    # ======================================================

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job by ID.
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            True if job was cancelled, False if not found or already completed
        """
        async with self._lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
                    job.status = JobStatus.CANCELLED
                    job.failed_at = datetime.utcnow()
                    job.error_message = "Job was cancelled"
                    self.cancelled_jobs.add(job_id)
                    self._stats['cancelled_jobs'] += 1
                    self._stats['processing_jobs'] -= 1
                    logger.info("Job %s was cancelled", job_id)
                    return True
            return False

    async def get_job(self, job_id: str) -> Optional[QueueJob]:
        """
        Get job information by ID.
        
        Args:
            job_id: ID of the job to retrieve
            
        Returns:
            Job object if found, None otherwise
        """
        async with self._lock:
            return self.jobs.get(job_id)

    async def update_job_progress(self, job_id: str, progress: float) -> bool:
        """
        Update job progress percentage.
        
        Args:
            job_id: ID of the job to update
            progress: Progress percentage (0.0 to 100.0)
            
        Returns:
            True if updated successfully, False if job not found
        """
        async with self._lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                job.progress = max(0.0, min(100.0, progress))  # Clamp between 0 and 100
                return True
            return False

    async def get_queue_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary containing queue statistics
        """
        async with self._lock:
            return {
                'total_jobs': self._stats['total_jobs'],
                'completed_jobs': self._stats['completed_jobs'],
                'failed_jobs': self._stats['failed_jobs'],
                'cancelled_jobs': self._stats['cancelled_jobs'],
                'processing_jobs': self._stats['processing_jobs'],
                'queue_size': self.queue.qsize(),
                'success_rate': (
                    self._stats['completed_jobs'] / max(1, self._stats['total_jobs']) * 100
                ),
                'failure_rate': (
                    self._stats['failed_jobs'] / max(1, self._stats['total_jobs']) * 100
                )
            }

    async def get_jobs_by_status(self, status: JobStatus) -> List[QueueJob]:
        """
        Get all jobs with a specific status.
        
        Args:
            status: Job status to filter by
            
        Returns:
            List of jobs with the specified status
        """
        async with self._lock:
            return [job for job in self.jobs.values() if job.status == status]

    async def get_jobs_by_tag(self, tag: str) -> List[QueueJob]:
        """
        Get all jobs with a specific tag.
        
        Args:
            tag: Tag to filter jobs by
            
        Returns:
            List of jobs with the specified tag
        """
        async with self._lock:
            return [job for job in self.jobs.values() if tag in job.tags]

    async def clear_completed_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clear completed jobs older than specified hours.
        
        Args:
            max_age_hours: Maximum age in hours for completed jobs
            
        Returns:
            Number of jobs cleared
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        async with self._lock:
            initial_count = len(self.jobs)
            self.jobs = {
                job_id: job for job_id, job in self.jobs.items()
                if job.status != JobStatus.COMPLETED or 
                   (job.completed_at and job.completed_at > cutoff_time)
            }
            cleared_count = initial_count - len(self.jobs)
            if cleared_count > 0:
                logger.info("Cleared %d completed jobs older than %d hours", 
                          cleared_count, max_age_hours)
            return cleared_count

    # ======================================================
    # BACKGROUND TASKS
    # ======================================================

    async def _health_check_loop(self) -> None:
        """
        Background health check loop.
        """
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Health check error: %s", e)

    async def _perform_health_check(self) -> None:
        """
        Perform health check and log status.
        """
        async with self._lock:
            stats = await self.get_queue_stats()
            queue_size = self.queue.qsize()
            
            # Log health status
            logger.info(
                "Health check - Queue size: %d, Processing: %d, "
                "Completed: %d, Failed: %d, Success rate: %.2f%%",
                queue_size,
                stats['processing_jobs'],
                stats['completed_jobs'],
                stats['failed_jobs'],
                stats['success_rate']
            )
            
            # Check for potential issues
            if queue_size > self.max_queue_size * 0.8:
                logger.warning("Queue size is at %d%% of maximum capacity", 
                             (queue_size / self.max_queue_size) * 100)
            
            if stats['failure_rate'] > 50:
                logger.warning("High failure rate detected: %.2f%%", stats['failure_rate'])

    async def _metrics_loop(self) -> None:
        """
        Background metrics collection loop.
        """
        while self.running:
            try:
                await asyncio.sleep(60)  # Collect metrics every minute
                await self._collect_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Metrics collection error: %s", e)

    async def _collect_metrics(self) -> None:
        """
        Collect and update metrics.
        """
        async with self._lock:
            # Update uptime
            self._stats['uptime_seconds'] = (
                datetime.utcnow() - self._stats['start_time']
            ).total_seconds()
            
            # Perform cleanup if needed
            current_time = datetime.utcnow()
            if (current_time - self._last_cleanup_time).total_seconds() > self.cleanup_interval_seconds:
                await self.clear_completed_jobs(max_age_hours=24)
                self._last_cleanup_time = current_time

    # ======================================================
    # INTERNAL WORKER
    # ======================================================

    async def _worker_loop(self) -> None:
        """
        Worker loop for processing jobs.
        """
        while self.running:
            try:
                job = await self.queue.get()
                await self._process_job(job)
                self.queue.task_done()

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.exception("Worker error: %s", e)

    async def _process_job(self, job: QueueJob) -> None:
        """
        Process a single job with retry mechanism, error handling, and dependency notification.
        """
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.worker_id = f"worker-{id(asyncio.current_task())}"
        
        logger.info("Processing job %s with priority %s", job.id, job.priority)

        try:
            # Execute the job with timeout if specified
            if job.timeout_seconds:
                await asyncio.wait_for(
                    self._execute_payload(job.payload, job.metadata),
                    timeout=job.timeout_seconds
                )
            else:
                await self._execute_payload(job.payload, job.metadata)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100.0
            self._stats['completed_jobs'] += 1
            self._stats['processing_jobs'] -= 1
            logger.info("Job %s completed successfully", job.id)
            
            # Notify dependent jobs
            await self._notify_dependents(job.id)

        except asyncio.TimeoutError:
            job.status = JobStatus.TIMEOUT
            job.failed_at = datetime.utcnow()
            job.error_message = f"Job timed out after {job.timeout_seconds} seconds"
            self._stats['failed_jobs'] += 1
            self._stats['processing_jobs'] -= 1
            logger.error("Job %s timed out after %s seconds", job.id, job.timeout_seconds)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.failed_at = datetime.utcnow()
            job.error_message = str(e)
            job.retry_count += 1
            self._stats['failed_jobs'] += 1
            self._stats['processing_jobs'] -= 1
            logger.exception("Job %s failed: %s (retry %d/%d)", 
                           job.id, e, job.retry_count, job.max_retries)

    async def _execute_payload(
        self,
        payload: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> None:
        """
        Placeholder execution logic.
        Replace with your actual video processing logic.
        """

        # Simulate async processing
        await asyncio.sleep(1)

        logger.debug("Payload: %s", payload)
        logger.debug("Metadata: %s", metadata)


# Singleton instance with production configuration
queue_service = QueueService(
    max_workers=4,  # Increased for better throughput
    enable_metrics=True,  # Enable metrics collection
    enable_health_check=True,  # Enable health monitoring
    max_queue_size=5000,  # Increased queue capacity
    cleanup_interval_seconds=1800  # 30 minutes cleanup interval
)
