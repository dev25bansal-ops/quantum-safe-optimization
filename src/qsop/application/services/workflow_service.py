"""
Workflow Service for QSOP.

Provides orchestration of optimization runs with async execution support,
progress tracking, and error recovery.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Workflow step status."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Represents a step in a workflow."""
    
    id: str
    name: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3


@dataclass
class WorkflowProgress:
    """Tracks workflow execution progress."""
    
    total_steps: int
    completed_steps: int
    current_step: Optional[str]
    progress_percent: float
    estimated_remaining_seconds: Optional[float] = None
    steps: List[WorkflowStep] = field(default_factory=list)


@dataclass
class WorkflowContext:
    """Context passed through workflow execution."""
    
    workflow_id: UUID
    tenant_id: str
    parameters: Dict[str, Any]
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult(Generic[R]):
    """Result of workflow execution."""
    
    success: bool
    value: Optional[R]
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    steps_completed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Checkpoint:
    """Workflow checkpoint for recovery."""
    
    workflow_id: UUID
    step_id: str
    state: Dict[str, Any]
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowExecutor(ABC, Generic[T, R]):
    """Abstract base for workflow executors."""
    
    @abstractmethod
    async def execute(self, input_data: T, context: WorkflowContext) -> R:
        """Execute the workflow."""
        ...
    
    @abstractmethod
    async def get_progress(self, workflow_id: UUID) -> WorkflowProgress:
        """Get current progress."""
        ...
    
    @abstractmethod
    async def pause(self, workflow_id: UUID) -> bool:
        """Pause workflow execution."""
        ...
    
    @abstractmethod
    async def resume(self, workflow_id: UUID) -> bool:
        """Resume paused workflow."""
        ...
    
    @abstractmethod
    async def cancel(self, workflow_id: UUID) -> bool:
        """Cancel workflow execution."""
        ...


class CheckpointStore:
    """In-memory checkpoint store."""
    
    def __init__(self) -> None:
        self._checkpoints: Dict[UUID, List[Checkpoint]] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, checkpoint: Checkpoint) -> None:
        async with self._lock:
            if checkpoint.workflow_id not in self._checkpoints:
                self._checkpoints[checkpoint.workflow_id] = []
            self._checkpoints[checkpoint.workflow_id].append(checkpoint)
    
    async def get_latest(self, workflow_id: UUID) -> Optional[Checkpoint]:
        checkpoints = self._checkpoints.get(workflow_id, [])
        return checkpoints[-1] if checkpoints else None
    
    async def get_all(self, workflow_id: UUID) -> List[Checkpoint]:
        return self._checkpoints.get(workflow_id, [])
    
    async def clear(self, workflow_id: UUID) -> None:
        async with self._lock:
            self._checkpoints.pop(workflow_id, None)


class ProgressTracker:
    """Tracks and reports workflow progress."""
    
    def __init__(self) -> None:
        self._workflows: Dict[UUID, WorkflowProgress] = {}
        self._callbacks: Dict[UUID, List[Callable[[WorkflowProgress], None]]] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self, workflow_id: UUID, steps: List[WorkflowStep]) -> None:
        async with self._lock:
            self._workflows[workflow_id] = WorkflowProgress(
                total_steps=len(steps),
                completed_steps=0,
                current_step=steps[0].name if steps else None,
                progress_percent=0.0,
                steps=steps,
            )
    
    async def update_step(
        self,
        workflow_id: UUID,
        step_id: str,
        status: StepStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        async with self._lock:
            progress = self._workflows.get(workflow_id)
            if progress is None:
                return
            
            for step in progress.steps:
                if step.id == step_id:
                    step.status = status
                    step.result = result
                    step.error = error
                    
                    if status == StepStatus.RUNNING:
                        step.started_at = datetime.now(timezone.utc)
                        progress.current_step = step.name
                    elif status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                        step.completed_at = datetime.now(timezone.utc)
                        if status == StepStatus.COMPLETED:
                            progress.completed_steps += 1
                    break
            
            progress.progress_percent = (
                progress.completed_steps / progress.total_steps * 100
                if progress.total_steps > 0 else 0.0
            )
        
        # Notify callbacks
        await self._notify(workflow_id)
    
    async def get_progress(self, workflow_id: UUID) -> Optional[WorkflowProgress]:
        return self._workflows.get(workflow_id)
    
    def subscribe(
        self,
        workflow_id: UUID,
        callback: Callable[[WorkflowProgress], None],
    ) -> None:
        if workflow_id not in self._callbacks:
            self._callbacks[workflow_id] = []
        self._callbacks[workflow_id].append(callback)
    
    def unsubscribe(
        self,
        workflow_id: UUID,
        callback: Callable[[WorkflowProgress], None],
    ) -> None:
        if workflow_id in self._callbacks:
            self._callbacks[workflow_id].remove(callback)
    
    async def _notify(self, workflow_id: UUID) -> None:
        progress = self._workflows.get(workflow_id)
        if progress is None:
            return
        
        for callback in self._callbacks.get(workflow_id, []):
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")


class ErrorRecoveryStrategy(ABC):
    """Abstract error recovery strategy."""
    
    @abstractmethod
    async def should_retry(self, step: WorkflowStep, error: Exception) -> bool:
        """Determine if step should be retried."""
        ...
    
    @abstractmethod
    async def get_retry_delay(self, step: WorkflowStep) -> float:
        """Get delay before retry in seconds."""
        ...
    
    @abstractmethod
    async def on_recovery_failed(
        self,
        step: WorkflowStep,
        error: Exception,
        context: WorkflowContext,
    ) -> None:
        """Handle unrecoverable failure."""
        ...


class ExponentialBackoffRecovery(ErrorRecoveryStrategy):
    """Exponential backoff retry strategy."""
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
    ) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
    
    async def should_retry(self, step: WorkflowStep, error: Exception) -> bool:
        return step.retries < step.max_retries
    
    async def get_retry_delay(self, step: WorkflowStep) -> float:
        delay = self.base_delay * (self.multiplier ** step.retries)
        return min(delay, self.max_delay)
    
    async def on_recovery_failed(
        self,
        step: WorkflowStep,
        error: Exception,
        context: WorkflowContext,
    ) -> None:
        logger.error(
            f"Workflow {context.workflow_id} step {step.id} failed "
            f"after {step.retries} retries: {error}"
        )


@dataclass
class WorkflowDefinition:
    """Defines a workflow structure."""
    
    id: str
    name: str
    steps: List[WorkflowStep]
    parameters_schema: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowService:
    """
    Service for orchestrating optimization workflow runs.
    
    Provides async execution, progress tracking, checkpointing,
    and error recovery for complex optimization workflows.
    """
    
    def __init__(
        self,
        checkpoint_store: Optional[CheckpointStore] = None,
        recovery_strategy: Optional[ErrorRecoveryStrategy] = None,
    ) -> None:
        self._checkpoint_store = checkpoint_store or CheckpointStore()
        self._recovery_strategy = recovery_strategy or ExponentialBackoffRecovery()
        self._progress_tracker = ProgressTracker()
        self._running_workflows: Dict[UUID, asyncio.Task[Any]] = {}
        self._workflow_status: Dict[UUID, WorkflowStatus] = {}
        self._pause_events: Dict[UUID, asyncio.Event] = {}
        self._cancel_flags: Dict[UUID, bool] = {}
    
    async def start_workflow(
        self,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        executor: WorkflowExecutor[Any, Any],
    ) -> UUID:
        """
        Start a new workflow execution.
        
        Args:
            definition: Workflow definition
            context: Execution context
            executor: Workflow executor
            
        Returns:
            Workflow ID
        """
        workflow_id = context.workflow_id
        
        logger.info(f"Starting workflow {workflow_id}: {definition.name}")
        
        # Initialize tracking
        await self._progress_tracker.initialize(workflow_id, definition.steps)
        self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
        self._pause_events[workflow_id] = asyncio.Event()
        self._pause_events[workflow_id].set()  # Not paused initially
        self._cancel_flags[workflow_id] = False
        
        # Start execution task
        task = asyncio.create_task(
            self._run_workflow(definition, context, executor)
        )
        self._running_workflows[workflow_id] = task
        
        return workflow_id
    
    async def _run_workflow(
        self,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        executor: WorkflowExecutor[Any, Any],
    ) -> WorkflowResult[Any]:
        """Run workflow with error handling and checkpointing."""
        workflow_id = context.workflow_id
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check for recovery from checkpoint
            checkpoint = await self._checkpoint_store.get_latest(workflow_id)
            if checkpoint:
                context.state = checkpoint.state
                logger.info(f"Recovered workflow {workflow_id} from checkpoint at step {checkpoint.step_id}")
            
            # Execute workflow
            result = await executor.execute(context.parameters, context)
            
            self._workflow_status[workflow_id] = WorkflowStatus.COMPLETED
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.info(f"Workflow {workflow_id} completed in {elapsed:.2f}s")
            
            return WorkflowResult(
                success=True,
                value=result,
                execution_time_seconds=elapsed,
                steps_completed=len(definition.steps),
            )
            
        except asyncio.CancelledError:
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            logger.info(f"Workflow {workflow_id} cancelled")
            raise
            
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.error(f"Workflow {workflow_id} failed: {e}")
            
            return WorkflowResult(
                success=False,
                value=None,
                error=str(e),
                execution_time_seconds=elapsed,
            )
            
        finally:
            # Cleanup
            self._running_workflows.pop(workflow_id, None)
            self._pause_events.pop(workflow_id, None)
            self._cancel_flags.pop(workflow_id, None)
    
    async def execute_step(
        self,
        workflow_id: UUID,
        step: WorkflowStep,
        step_fn: Callable[..., Any],
        context: WorkflowContext,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a workflow step with error handling and recovery.
        
        Args:
            workflow_id: Workflow identifier
            step: Step definition
            step_fn: Step function to execute
            context: Workflow context
            *args: Step arguments
            **kwargs: Step keyword arguments
            
        Returns:
            Step result
            
        Raises:
            Exception: If step fails after all retries
        """
        # Check for pause
        pause_event = self._pause_events.get(workflow_id)
        if pause_event:
            await pause_event.wait()
        
        # Check for cancellation
        if self._cancel_flags.get(workflow_id, False):
            raise asyncio.CancelledError()
        
        await self._progress_tracker.update_step(
            workflow_id, step.id, StepStatus.RUNNING
        )
        
        while True:
            try:
                result = await step_fn(*args, **kwargs)
                
                # Save checkpoint
                await self._checkpoint_store.save(Checkpoint(
                    workflow_id=workflow_id,
                    step_id=step.id,
                    state=context.state,
                    created_at=datetime.now(timezone.utc),
                ))
                
                await self._progress_tracker.update_step(
                    workflow_id, step.id, StepStatus.COMPLETED, result=result
                )
                
                return result
                
            except Exception as e:
                step.retries += 1
                
                if await self._recovery_strategy.should_retry(step, e):
                    delay = await self._recovery_strategy.get_retry_delay(step)
                    logger.warning(
                        f"Step {step.id} failed, retrying in {delay}s "
                        f"(attempt {step.retries}/{step.max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    await self._recovery_strategy.on_recovery_failed(step, e, context)
                    await self._progress_tracker.update_step(
                        workflow_id, step.id, StepStatus.FAILED, error=str(e)
                    )
                    raise
    
    async def get_progress(self, workflow_id: UUID) -> Optional[WorkflowProgress]:
        """Get workflow progress."""
        return await self._progress_tracker.get_progress(workflow_id)
    
    async def get_status(self, workflow_id: UUID) -> Optional[WorkflowStatus]:
        """Get workflow status."""
        return self._workflow_status.get(workflow_id)
    
    async def pause_workflow(self, workflow_id: UUID) -> bool:
        """
        Pause a running workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            True if paused, False otherwise
        """
        if workflow_id not in self._pause_events:
            return False
        
        if self._workflow_status.get(workflow_id) != WorkflowStatus.RUNNING:
            return False
        
        self._pause_events[workflow_id].clear()
        self._workflow_status[workflow_id] = WorkflowStatus.PAUSED
        
        logger.info(f"Workflow {workflow_id} paused")
        return True
    
    async def resume_workflow(self, workflow_id: UUID) -> bool:
        """
        Resume a paused workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            True if resumed, False otherwise
        """
        if workflow_id not in self._pause_events:
            return False
        
        if self._workflow_status.get(workflow_id) != WorkflowStatus.PAUSED:
            return False
        
        self._pause_events[workflow_id].set()
        self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
        
        logger.info(f"Workflow {workflow_id} resumed")
        return True
    
    async def cancel_workflow(self, workflow_id: UUID) -> bool:
        """
        Cancel a running or paused workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            True if cancelled, False otherwise
        """
        if workflow_id not in self._running_workflows:
            return False
        
        self._cancel_flags[workflow_id] = True
        
        # If paused, resume to allow cancellation
        if workflow_id in self._pause_events:
            self._pause_events[workflow_id].set()
        
        task = self._running_workflows[workflow_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"Workflow {workflow_id} cancelled")
        return True
    
    async def wait_for_completion(
        self,
        workflow_id: UUID,
        timeout: Optional[float] = None,
    ) -> Optional[WorkflowResult[Any]]:
        """
        Wait for workflow completion.
        
        Args:
            workflow_id: Workflow identifier
            timeout: Maximum wait time in seconds
            
        Returns:
            Workflow result or None if timeout
        """
        task = self._running_workflows.get(workflow_id)
        if task is None:
            return None
        
        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Workflow {workflow_id} timed out after {timeout}s")
            return None
    
    def subscribe_progress(
        self,
        workflow_id: UUID,
        callback: Callable[[WorkflowProgress], None],
    ) -> None:
        """Subscribe to progress updates."""
        self._progress_tracker.subscribe(workflow_id, callback)
    
    def unsubscribe_progress(
        self,
        workflow_id: UUID,
        callback: Callable[[WorkflowProgress], None],
    ) -> None:
        """Unsubscribe from progress updates."""
        self._progress_tracker.unsubscribe(workflow_id, callback)
    
    async def recover_from_checkpoint(
        self,
        workflow_id: UUID,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        executor: WorkflowExecutor[Any, Any],
    ) -> Optional[UUID]:
        """
        Recover a workflow from its last checkpoint.
        
        Args:
            workflow_id: Original workflow identifier
            definition: Workflow definition
            context: Execution context
            executor: Workflow executor
            
        Returns:
            New workflow ID if recovery started, None if no checkpoint found
        """
        checkpoint = await self._checkpoint_store.get_latest(workflow_id)
        if checkpoint is None:
            logger.warning(f"No checkpoint found for workflow {workflow_id}")
            return None
        
        # Create new context with recovered state
        new_context = WorkflowContext(
            workflow_id=uuid4(),
            tenant_id=context.tenant_id,
            parameters=context.parameters,
            state=checkpoint.state,
            metadata={
                **context.metadata,
                "recovered_from": str(workflow_id),
                "recovery_step": checkpoint.step_id,
            },
        )
        
        logger.info(
            f"Recovering workflow {workflow_id} from step {checkpoint.step_id} "
            f"as new workflow {new_context.workflow_id}"
        )
        
        return await self.start_workflow(definition, new_context, executor)
