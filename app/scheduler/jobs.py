"""Scheduled jobs management"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from app.config import get_config
from app.core.scanner import get_scanner

logger = logging.getLogger(__name__)


class SchedulerManager:
    """
    Manages scheduled scanning jobs using APScheduler.
    
    Features:
    - Cron expression support
    - Manual trigger
    - Job history
    - Event callbacks
    """
    
    JOB_ID = "strm_scan"
    
    def __init__(self):
        """Initialize scheduler manager"""
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None
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
    
    async def _scan_job(self) -> None:
        """Execute scan job"""
        logger.info("Scheduled scan job started")
        self._last_run = datetime.now()
        
        try:
            scanner = get_scanner()
            results = await scanner.scan_all()
            
            # Summarize results
            total_created = sum(r.files_created for r in results)
            total_updated = sum(r.files_updated for r in results)
            total_deleted = sum(r.files_deleted for r in results)
            
            logger.info(
                f"Scheduled scan completed: "
                f"created={total_created}, updated={total_updated}, deleted={total_deleted}"
            )
            
            if self._on_scan_complete:
                await self._on_scan_complete(results)
                
        except Exception as e:
            logger.error(f"Scheduled scan failed: {e}")
            if self._on_scan_error:
                await self._on_scan_error(str(e))
            raise
    
    def _on_job_executed(self, event: JobExecutionEvent) -> None:
        """Handle job execution event"""
        if event.job_id == self.JOB_ID:
            self._update_next_run()
    
    def _on_job_error(self, event: JobExecutionEvent) -> None:
        """Handle job error event"""
        if event.job_id == self.JOB_ID:
            logger.error(f"Job error: {event.exception}")
            self._update_next_run()
    
    def _update_next_run(self) -> None:
        """Update next run time"""
        if self._scheduler:
            job = self._scheduler.get_job(self.JOB_ID)
            if job:
                self._next_run = job.next_run_time
    
    async def start(self) -> None:
        """Start the scheduler"""
        if self._running:
            return
        
        config = get_config()
        
        if not config.schedule.enabled:
            logger.info("Scheduler is disabled")
            return
        
        # Create scheduler
        self._scheduler = AsyncIOScheduler()
        
        # Add event listeners
        self._scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        
        # Parse cron expression
        try:
            cron_params = self._parse_cron(config.schedule.cron)
        except ValueError as e:
            logger.error(f"Invalid cron expression: {e}")
            return
        
        # Add job
        trigger = CronTrigger(**cron_params)
        self._scheduler.add_job(
            self._scan_job,
            trigger=trigger,
            id=self.JOB_ID,
            name="STRM Scan",
            replace_existing=True,
        )
        
        # Start scheduler
        self._scheduler.start()
        self._running = True
        self._update_next_run()
        
        logger.info(f"Scheduler started with cron: {config.schedule.cron}")
        logger.info(f"Next run: {self._next_run}")
        
        # Run on startup if configured
        if config.schedule.on_startup:
            logger.info("Running scan on startup...")
            asyncio.create_task(self._scan_job())
    
    async def stop(self) -> None:
        """Stop the scheduler"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._running = False
        logger.info("Scheduler stopped")
    
    async def trigger_now(self, folders: Optional[List[str]] = None, force: bool = False) -> dict:
        """
        Trigger scan immediately.
        
        Args:
            folders: Optional list of folders to scan (None for all)
            force: Force regenerate all STRM files
            
        Returns:
            Scan results summary
        """
        logger.info(f"Manual scan triggered: folders={folders}, force={force}")
        
        scanner = get_scanner()
        
        if folders:
            results = []
            for folder in folders:
                progress = await scanner.scan_folder(folder, force)
                results.append(progress)
        else:
            results = await scanner.scan_all(force)
        
        # Build summary
        summary = {
            "folders_scanned": len(results),
            "total_files_scanned": sum(r.files_scanned for r in results),
            "total_files_created": sum(r.files_created for r in results),
            "total_files_updated": sum(r.files_updated for r in results),
            "total_files_deleted": sum(r.files_deleted for r in results),
            "results": [r.to_dict() for r in results],
        }
        
        return summary
    
    def set_on_complete(self, callback: Callable) -> None:
        """Set callback for scan completion"""
        self._on_scan_complete = callback
    
    def set_on_error(self, callback: Callable) -> None:
        """Set callback for scan error"""
        self._on_scan_error = callback
    
    @property
    def status(self) -> dict:
        """Get scheduler status"""
        return {
            "enabled": get_config().schedule.enabled,
            "running": self._running,
            "cron": get_config().schedule.cron if self._running else None,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": self._next_run.isoformat() if self._next_run else None,
        }
    
    async def update_schedule(self, cron: str) -> bool:
        """
        Update the schedule cron expression.
        
        Args:
            cron: New cron expression
            
        Returns:
            True if updated successfully
        """
        if not self._scheduler:
            return False
        
        try:
            cron_params = self._parse_cron(cron)
            trigger = CronTrigger(**cron_params)
            
            self._scheduler.reschedule_job(
                self.JOB_ID,
                trigger=trigger,
            )
            
            self._update_next_run()
            logger.info(f"Schedule updated: {cron}, next run: {self._next_run}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update schedule: {e}")
            return False


# Global scheduler instance
_scheduler_manager: Optional[SchedulerManager] = None


def get_scheduler_manager() -> SchedulerManager:
    """Get the global scheduler manager instance"""
    global _scheduler_manager
    if _scheduler_manager is None:
        _scheduler_manager = SchedulerManager()
    return _scheduler_manager
