"""Scheduled jobs management with multi-task support"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from app.config import get_config, TaskConfig

logger = logging.getLogger(__name__)


class SchedulerManager:
    """
    Manages scheduled scanning jobs using APScheduler.
    
    Features:
    - Multi-task support with unique IDs
    - Cron expression support
    - Task lifecycle: create, delete, enable, disable, pause, resume
    - One-time task support
    - Event callbacks
    """
    
    JOB_PREFIX = "strm_task_"
    
    def __init__(self):
        """Initialize scheduler manager"""
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
        self._tasks: Dict[str, TaskConfig] = {}
        self._on_scan_complete: Optional[Callable] = None
        self._on_scan_error: Optional[Callable] = None
    
    def _parse_cron(self, cron_expr: str) -> dict:
        """
        Parse cron expression to APScheduler format.
        
        Supports 5-field format: minute hour day month day_of_week
        """
        parts = cron_expr.strip().split()
        
        if len(parts) == 5:
            return {
                "minute": parts[0],
                "hour": parts[1],
                "day": parts[2],
                "month": parts[3],
                "day_of_week": parts[4],
            }
        elif len(parts) == 6:
            # With seconds
            return {
                "second": parts[0],
                "minute": parts[1],
                "hour": parts[2],
                "day": parts[3],
                "month": parts[4],
                "day_of_week": parts[5],
            }
        else:
            raise ValueError(f"Invalid cron expression: {cron_expr}")
    
    def _get_job_id(self, task_id: str) -> str:
        """Get APScheduler job ID from task ID"""
        return f"{self.JOB_PREFIX}{task_id}"
    
    async def _execute_task(self, task_id: str) -> None:
        """Execute a scheduled task"""
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return
        
        if task.paused:
            logger.info(f"Task {task_id} is paused, skipping")
            return
        
        logger.info(f"Executing scheduled task: {task.name} ({task_id})")
        task.last_run = datetime.now().isoformat()
        
        try:
            from app.core.scanner import get_scanner
            from app.core.emby import get_emby_client
            
            scanner = get_scanner()
            
            # Scan the task's folder
            if task.folder:
                result = await scanner.scan_folder(task.folder)
                results = [result]
            else:
                results = await scanner.scan_all()
            
            # Summarize results
            total_created = sum(r.files_created for r in results)
            total_updated = sum(r.files_updated for r in results)
            total_deleted = sum(r.files_deleted for r in results)
            
            logger.info(
                f"Task {task.name} completed: "
                f"created={total_created}, updated={total_updated}, deleted={total_deleted}"
            )
            
            # Trigger Emby refresh
            emby = get_emby_client()
            await emby.notify_scan_complete({
                "task_id": task_id,
                "task_name": task.name,
                "created": total_created,
                "updated": total_updated,
            })
            
            # Handle one-time task
            if task.one_time:
                logger.info(f"One-time task {task_id} completed, disabling")
                task.enabled = False
                await self._remove_job(task_id)
            
            if self._on_scan_complete:
                await self._on_scan_complete(results)
                
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            if self._on_scan_error:
                await self._on_scan_error(str(e))
            raise
    
    def _on_job_executed(self, event: JobExecutionEvent) -> None:
        """Handle job execution event"""
        if event.job_id.startswith(self.JOB_PREFIX):
            task_id = event.job_id[len(self.JOB_PREFIX):]
            self._update_next_run(task_id)
    
    def _on_job_error(self, event: JobExecutionEvent) -> None:
        """Handle job error event"""
        if event.job_id.startswith(self.JOB_PREFIX):
            task_id = event.job_id[len(self.JOB_PREFIX):]
            logger.error(f"Task {task_id} error: {event.exception}")
            self._update_next_run(task_id)
    
    def _update_next_run(self, task_id: str) -> None:
        """Update next run time for a task"""
        if self._scheduler and task_id in self._tasks:
            job = self._scheduler.get_job(self._get_job_id(task_id))
            if job:
                self._tasks[task_id].next_run = (
                    job.next_run_time.isoformat() if job.next_run_time else None
                )
    
    async def _add_job(self, task: TaskConfig) -> bool:
        """Add a job to the scheduler"""
        if not self._scheduler:
            return False
        
        try:
            cron_params = self._parse_cron(task.cron)
            trigger = CronTrigger(**cron_params)
            
            self._scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                args=[task.id],
                id=self._get_job_id(task.id),
                name=task.name,
                replace_existing=True,
            )
            
            self._update_next_run(task.id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job for task {task.id}: {e}")
            return False
    
    async def _remove_job(self, task_id: str) -> bool:
        """Remove a job from the scheduler"""
        if not self._scheduler:
            return False
        
        try:
            job_id = self._get_job_id(task_id)
            job = self._scheduler.get_job(job_id)
            if job:
                self._scheduler.remove_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {task_id}: {e}")
            return False
    
    async def start(self) -> None:
        """Start the scheduler"""
        if self._running:
            return
        
        config = get_config()
        
        # Create scheduler
        self._scheduler = AsyncIOScheduler()
        
        # Add event listeners
        self._scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        
        # Load tasks from config
        for task_config in config.schedule.tasks:
            self._tasks[task_config.id] = task_config
            if task_config.enabled and not task_config.paused:
                await self._add_job(task_config)
        
        # Legacy single-task support (migrate to multi-task)
        if config.schedule.enabled and not config.schedule.tasks:
            # Create default task from legacy config
            default_task = TaskConfig(
                id="default",
                name="Default Scan",
                folder="",  # All folders
                cron=config.schedule.cron,
                enabled=True,
            )
            self._tasks["default"] = default_task
            await self._add_job(default_task)
        
        # Start scheduler
        self._scheduler.start()
        self._running = True
        
        task_count = len([t for t in self._tasks.values() if t.enabled])
        logger.info(f"Scheduler started with {task_count} active tasks")
        
        # Run on startup tasks if configured
        if config.schedule.on_startup:
            for task_id, task in self._tasks.items():
                if task.enabled:
                    logger.info(f"Running task {task.name} on startup...")
                    asyncio.create_task(self._execute_task(task_id))
    
    async def stop(self) -> None:
        """Stop the scheduler"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._running = False
        logger.info("Scheduler stopped")
    
    # ============ Task Management API ============
    
    async def create_task(
        self,
        name: str,
        folder: str,
        cron: str,
        enabled: bool = True,
        one_time: bool = False,
    ) -> TaskConfig:
        """
        Create and schedule a new task.
        
        Args:
            name: Display name
            folder: Folder path to scan
            cron: Cron expression
            enabled: Whether to enable immediately
            one_time: Run once then disable
            
        Returns:
            Created TaskConfig
        """
        task = TaskConfig(
            id=f"task_{uuid.uuid4().hex[:8]}",
            name=name,
            folder=folder,
            cron=cron,
            enabled=enabled,
            one_time=one_time,
        )
        
        self._tasks[task.id] = task
        
        if enabled and self._scheduler:
            await self._add_job(task)
        
        logger.info(f"Created task: {task.name} ({task.id})")
        return task
    
    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a scheduled task.
        
        Args:
            task_id: Task ID to delete
            
        Returns:
            True if deleted
        """
        if task_id not in self._tasks:
            return False
        
        await self._remove_job(task_id)
        del self._tasks[task_id]
        
        logger.info(f"Deleted task: {task_id}")
        return True
    
    async def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        folder: Optional[str] = None,
        cron: Optional[str] = None,
        one_time: Optional[bool] = None,
    ) -> Optional[TaskConfig]:
        """
        Update task settings.
        
        Args:
            task_id: Task ID
            name: New name (optional)
            folder: New folder (optional)
            cron: New cron expression (optional)
            one_time: New one-time flag (optional)
            
        Returns:
            Updated TaskConfig or None if not found
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        if name is not None:
            task.name = name
        if folder is not None:
            task.folder = folder
        if one_time is not None:
            task.one_time = one_time
        
        # Update cron and reschedule if changed
        if cron is not None and cron != task.cron:
            task.cron = cron
            if task.enabled and not task.paused:
                await self._remove_job(task_id)
                await self._add_job(task)
        
        logger.info(f"Updated task: {task.name} ({task_id})")
        return task
    
    async def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.enabled = True
        if not task.paused:
            await self._add_job(task)
        
        logger.info(f"Enabled task: {task.name}")
        return True
    
    async def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.enabled = False
        await self._remove_job(task_id)
        
        logger.info(f"Disabled task: {task.name}")
        return True
    
    async def pause_task(self, task_id: str) -> bool:
        """Pause a task (keeps enabled but skips execution)"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.paused = True
        await self._remove_job(task_id)
        
        logger.info(f"Paused task: {task.name}")
        return True
    
    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.paused = False
        if task.enabled:
            await self._add_job(task)
        
        logger.info(f"Resumed task: {task.name}")
        return True
    
    async def run_task_now(self, task_id: str) -> dict:
        """
        Trigger immediate execution of a task.
        
        Args:
            task_id: Task ID to run
            
        Returns:
            Execution result
        """
        task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        try:
            await self._execute_task(task_id)
            return {"success": True, "task_id": task_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        """Get a task by ID"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[dict]:
        """Get all tasks with their current status"""
        tasks = []
        for task in self._tasks.values():
            tasks.append(task.to_dict())
        return tasks
    
    def set_on_complete(self, callback: Callable) -> None:
        """Set callback for scan completion"""
        self._on_scan_complete = callback
    
    def set_on_error(self, callback: Callable) -> None:
        """Set callback for scan error"""
        self._on_scan_error = callback
    
    @property
    def status(self) -> dict:
        """Get scheduler status"""
        active_tasks = [t for t in self._tasks.values() if t.enabled and not t.paused]
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "active_tasks": len(active_tasks),
            "tasks": self.get_all_tasks(),
        }


# Global scheduler instance
_scheduler_manager: Optional[SchedulerManager] = None


def get_scheduler_manager() -> SchedulerManager:
    """Get the global scheduler manager instance"""
    global _scheduler_manager
    if _scheduler_manager is None:
        _scheduler_manager = SchedulerManager()
    return _scheduler_manager
