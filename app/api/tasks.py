"""Tasks API endpoints with multi-task management"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.scheduler import get_scheduler_manager

router = APIRouter(prefix="/tasks")


class CreateTaskRequest(BaseModel):
    """Create task request model"""
    name: str
    folder: str
    cron: str
    enabled: bool = True
    one_time: bool = False


class UpdateTaskRequest(BaseModel):
    """Update task request model"""
    name: Optional[str] = None
    folder: Optional[str] = None
    cron: Optional[str] = None
    one_time: Optional[bool] = None


class UpdateScheduleRequest(BaseModel):
    """Update schedule request model (legacy)"""
    cron: str
    enabled: Optional[bool] = None


# ============ Multi-Task Management ============

@router.get("")
async def list_tasks():
    """
    List all scheduled tasks.
    
    Returns all tasks with their current status, next run time, etc.
    """
    scheduler = get_scheduler_manager()
    return {
        "tasks": scheduler.get_all_tasks(),
        "status": scheduler.status,
    }


@router.post("")
async def create_task(request: CreateTaskRequest):
    """
    Create a new scheduled task.
    
    - **name**: Display name for the task
    - **folder**: OpenList folder path to monitor
    - **cron**: Cron expression (5 or 6 fields)
    - **enabled**: Whether to enable immediately
    - **one_time**: If true, task runs once then disables
    """
    # Validate cron expression
    try:
        parts = request.cron.strip().split()
        if len(parts) not in (5, 6):
            raise ValueError("Cron expression must have 5 or 6 fields")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cron expression: {str(e)}"
        )
    
    scheduler = get_scheduler_manager()
    task = await scheduler.create_task(
        name=request.name,
        folder=request.folder,
        cron=request.cron,
        enabled=request.enabled,
        one_time=request.one_time,
    )
    
    return {
        "message": "Task created",
        "task": task.to_dict(),
    }


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID"""
    scheduler = get_scheduler_manager()
    task = scheduler.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"task": task.to_dict()}


@router.put("/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest):
    """
    Update task settings.
    
    Only provided fields will be updated.
    """
    # Validate cron if provided
    if request.cron:
        try:
            parts = request.cron.strip().split()
            if len(parts) not in (5, 6):
                raise ValueError("Cron expression must have 5 or 6 fields")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cron expression: {str(e)}"
            )
    
    scheduler = get_scheduler_manager()
    task = await scheduler.update_task(
        task_id=task_id,
        name=request.name,
        folder=request.folder,
        cron=request.cron,
        one_time=request.one_time,
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "message": "Task updated",
        "task": task.to_dict(),
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a scheduled task"""
    scheduler = get_scheduler_manager()
    success = await scheduler.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted", "task_id": task_id}


@router.post("/{task_id}/enable")
async def enable_task(task_id: str):
    """Enable a task"""
    scheduler = get_scheduler_manager()
    success = await scheduler.enable_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = scheduler.get_task(task_id)
    return {
        "message": "Task enabled",
        "task": task.to_dict() if task else None,
    }


@router.post("/{task_id}/disable")
async def disable_task(task_id: str):
    """Disable a task"""
    scheduler = get_scheduler_manager()
    success = await scheduler.disable_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = scheduler.get_task(task_id)
    return {
        "message": "Task disabled",
        "task": task.to_dict() if task else None,
    }


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    """Pause a task (keeps enabled but skips execution)"""
    scheduler = get_scheduler_manager()
    success = await scheduler.pause_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = scheduler.get_task(task_id)
    return {
        "message": "Task paused",
        "task": task.to_dict() if task else None,
    }


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    """Resume a paused task"""
    scheduler = get_scheduler_manager()
    success = await scheduler.resume_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = scheduler.get_task(task_id)
    return {
        "message": "Task resumed",
        "task": task.to_dict() if task else None,
    }


@router.post("/{task_id}/run")
async def run_task_now(task_id: str):
    """Trigger immediate execution of a task"""
    scheduler = get_scheduler_manager()
    result = await scheduler.run_task_now(task_id)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400 if "not found" in result.get("error", "").lower() else 500,
            detail=result.get("error", "Unknown error")
        )
    
    return {
        "message": "Task execution started",
        "task_id": task_id,
    }


# ============ Legacy Schedule Endpoints (backward compatibility) ============

@router.get("/schedule")
async def get_schedule():
    """Get current schedule status (legacy)"""
    scheduler = get_scheduler_manager()
    return scheduler.status


@router.put("/schedule")
async def update_schedule(request: UpdateScheduleRequest):
    """
    Update the default scan schedule (legacy).
    Creates/updates a 'default' task.
    """
    scheduler = get_scheduler_manager()
    
    # Find or create default task
    task = scheduler.get_task("default")
    if task:
        await scheduler.update_task("default", cron=request.cron)
    else:
        await scheduler.create_task(
            name="Default Scan",
            folder="",
            cron=request.cron,
            enabled=request.enabled if request.enabled is not None else True,
        )
    
    return {
        "message": "Schedule updated",
        "cron": request.cron,
        "status": scheduler.status,
    }


@router.post("/schedule/pause")
async def pause_schedule():
    """Pause the scheduler (legacy - pauses all tasks)"""
    scheduler = get_scheduler_manager()
    
    if not scheduler._running:
        raise HTTPException(
            status_code=400,
            detail="Scheduler is not running"
        )
    
    # Pause all active tasks
    for task in scheduler.get_all_tasks():
        if task.get("enabled"):
            await scheduler.pause_task(task["id"])
    
    return {"message": "All tasks paused"}


@router.post("/schedule/resume")
async def resume_schedule():
    """Resume the scheduler (legacy - resumes all tasks)"""
    scheduler = get_scheduler_manager()
    
    # Resume all paused tasks
    for task in scheduler.get_all_tasks():
        if task.get("paused"):
            await scheduler.resume_task(task["id"])
    
    return {
        "message": "All tasks resumed",
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


# ============ Cron Helper ============

@router.get("/cron/examples")
async def get_cron_examples():
    """
    Get common cron expression examples.
    
    Returns examples for common scheduling patterns.
    """
    return {
        "examples": [
            {
                "expression": "*/30 * * * *",
                "description": "每 30 分钟",
                "description_en": "Every 30 minutes",
            },
            {
                "expression": "0 * * * *",
                "description": "每小时整点",
                "description_en": "Every hour",
            },
            {
                "expression": "0 2 * * *",
                "description": "每天凌晨 2 点",
                "description_en": "Daily at 2 AM",
            },
            {
                "expression": "0 2 * * 0",
                "description": "每周日凌晨 2 点",
                "description_en": "Every Sunday at 2 AM",
            },
            {
                "expression": "0 2 1 * *",
                "description": "每月 1 号凌晨 2 点",
                "description_en": "Monthly on 1st at 2 AM",
            },
            {
                "expression": "0 4 * * 1-5",
                "description": "工作日凌晨 4 点",
                "description_en": "Weekdays at 4 AM",
            },
        ],
        "format": "分 时 日 月 周 (minute hour day month weekday)",
        "fields": {
            "minute": "0-59",
            "hour": "0-23",
            "day": "1-31",
            "month": "1-12",
            "weekday": "0-6 (0=周日)",
        },
        "special": {
            "*": "任意值",
            "*/n": "每隔n",
            "a-b": "范围a到b",
            "a,b": "列表a和b",
        },
    }
