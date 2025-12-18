"""Tasks API endpoints"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.scheduler import get_scheduler_manager

router = APIRouter(prefix="/tasks")


class UpdateScheduleRequest(BaseModel):
    """Update schedule request model"""
    cron: str
    enabled: Optional[bool] = None


@router.get("/schedule")
async def get_schedule():
    """Get current schedule status"""
    scheduler = get_scheduler_manager()
    return scheduler.status


@router.put("/schedule")
async def update_schedule(request: UpdateScheduleRequest):
    """
    Update the scan schedule.
    
    - **cron**: Cron expression (5 or 6 fields)
    - **enabled**: Optional. Enable/disable the schedule
    """
    scheduler = get_scheduler_manager()
    
    # Validate cron expression
    try:
        # Simple validation by parsing
        parts = request.cron.strip().split()
        if len(parts) not in (5, 6):
            raise ValueError("Cron expression must have 5 or 6 fields")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cron expression: {str(e)}"
        )
    
    # Update schedule
    success = await scheduler.update_schedule(request.cron)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to update schedule. Scheduler may not be running."
        )
    
    return {
        "message": "Schedule updated",
        "cron": request.cron,
        "status": scheduler.status,
    }


@router.post("/schedule/pause")
async def pause_schedule():
    """Pause the scheduler"""
    scheduler = get_scheduler_manager()
    
    if not scheduler._running:
        raise HTTPException(
            status_code=400,
            detail="Scheduler is not running"
        )
    
    await scheduler.stop()
    
    return {"message": "Scheduler paused"}


@router.post("/schedule/resume")
async def resume_schedule():
    """Resume the scheduler"""
    scheduler = get_scheduler_manager()
    
    if scheduler._running:
        raise HTTPException(
            status_code=400,
            detail="Scheduler is already running"
        )
    
    await scheduler.start()
    
    return {
        "message": "Scheduler resumed",
        "status": scheduler.status,
    }


@router.get("/running")
async def get_running_tasks():
    """Get currently running tasks"""
    from app.core.scanner import get_scanner
    
    scanner = get_scanner()
    
    tasks = []
    if scanner.is_running:
        tasks.append({
            "type": "scan",
            "progress": scanner.progress.to_dict(),
        })
    
    return {"tasks": tasks}
