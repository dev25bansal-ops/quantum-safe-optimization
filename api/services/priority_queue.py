"""Job Priority Queue Service.

Priority-based job scheduling where higher-priority jobs are processed
before lower-priority ones. Integrated with the job processing pipeline.

Priority levels:
  1 = Critical (highest)
  2-4 = High
  5-7 = Normal (default)
  8-9 = Low
  10 = Background (lowest)
"""

import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(order=True)
class PriorityJob:
    """A job in the priority queue."""

    sort_key: tuple[int, float] = field(compare=True)
    job_id: str = field(compare=False)
    user_id: str = field(compare=False)
    priority: int = field(compare=False)
    submitted_at: float = field(compare=False)
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)


class PriorityJobQueue:
    """Thread-safe priority job queue using a min-heap."""

    def __init__(self, max_size: int = 10000):
        self._heap: list[PriorityJob] = []
        self._job_index: dict[str, PriorityJob] = {}
        self._max_size = max_size

    def enqueue(self, job_id: str, user_id: str, priority: int = 5, metadata: dict | None = None) -> bool:
        """Add a job to the priority queue.

        Returns True if enqueued, False if full or already exists.
        """
        if job_id in self._job_index:
            logger.warning("job_already_queued", job_id=job_id)
            return False

        if len(self._heap) >= self._max_size:
            logger.error("queue_full", size=len(self._heap), max=self._max_size)
            return False

        priority = max(1, min(10, priority))
        job = PriorityJob(
            sort_key=(priority, time.monotonic()),
            job_id=job_id,
            user_id=user_id,
            priority=priority,
            submitted_at=time.time(),
            metadata=metadata or {},
        )

        heapq.heappush(self._heap, job)
        self._job_index[job_id] = job
        logger.info("job_enqueued", job_id=job_id, priority=priority, queue_size=len(self._heap))
        return True

    def dequeue(self) -> PriorityJob | None:
        """Remove and return the highest priority job."""
        while self._heap:
            job = heapq.heappop(self._heap)
            if job.job_id in self._job_index:
                del self._job_index[job.job_id]
                return job
        return None

    def peek(self) -> PriorityJob | None:
        """Return the next job without removing it."""
        while self._heap:
            job = self._heap[0]
            if job.job_id in self._job_index:
                return job
            heapq.heappop(self._heap)
        return None

    def remove(self, job_id: str) -> bool:
        """Remove a specific job from the queue."""
        if job_id not in self._job_index:
            return False
        del self._job_index[job_id]
        return True

    def reprioritize(self, job_id: str, new_priority: int) -> bool:
        """Change a job's priority."""
        if job_id not in self._job_index:
            return False

        old_job = self._job_index[job_id]
        new_priority = max(1, min(10, new_priority))
        del self._job_index[job_id]

        job = PriorityJob(
            sort_key=(new_priority, time.monotonic()),
            job_id=job_id,
            user_id=old_job.user_id,
            priority=new_priority,
            submitted_at=old_job.submitted_at,
            metadata=old_job.metadata,
        )
        heapq.heappush(self._heap, job)
        self._job_index[job_id] = job
        return True

    def size(self) -> int:
        return len(self._job_index)

    def get_stats(self) -> dict[str, Any]:
        priority_counts = {}
        for job in self._job_index.values():
            priority_counts[job.priority] = priority_counts.get(job.priority, 0) + 1

        return {
            "total_jobs": len(self._job_index),
            "max_size": self._max_size,
            "priority_distribution": priority_counts,
            "next_job": self.peek().job_id if self.peek() else None,
        }


# Global instance
_priority_queue: PriorityJobQueue | None = None


def get_priority_queue() -> PriorityJobQueue:
    """Get the global priority job queue."""
    global _priority_queue
    if _priority_queue is None:
        _priority_queue = PriorityJobQueue()
    return _priority_queue


def init_priority_queue(max_size: int = 10000) -> PriorityJobQueue:
    """Initialize the global priority job queue."""
    global _priority_queue
    _priority_queue = PriorityJobQueue(max_size=max_size)
    return _priority_queue
