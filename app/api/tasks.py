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
    schedule_type: str = "cron"
    schedule_value: str = ""
    cron: Optional[str] = None
    enabled: bool = True
    one_time: bool = False


class UpdateTaskRequest(BaseModel):
    """Update task request model"""
    name: Optional[str] = None
    folder: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_value: Optional[str] = None
    cron: Optional[str] = None
    enabled: Optional[bool] = None
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
    try:
        scheduler = get_scheduler_manager()
        tasks = scheduler.get_all_tasks()
        return {
            "tasks": tasks if tasks else [],
            "status": scheduler.status,
        }
    except Exception as e:
        # Return empty tasks list on error to prevent UI crash
        return {
            "tasks": [],
            "status": {"running": False, "error": str(e)},
        }


@router.post("")
async def create_task(request: CreateTaskRequest):
    """
    Create a new scheduled task.
    """
    try:
        scheduler = get_scheduler_manager()
        task = await scheduler.create_task(
            name=request.name,
            folder=request.folder,
            schedule_type=request.schedule_type,
            schedule_value=request.schedule_value,
            cron=request.cron,
            enabled=request.enabled,
            one_time=request.one_time,
        )
        
        # Save config for persistence
        from app.config import get_config
        config = get_config()
        config.schedule.tasks.append(task)
        config.save()
        
        return {
            "message": f"Task created: {task.name}",
            "task": task.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """
    try:
        scheduler = get_scheduler_manager()
        task = await scheduler.update_task(
            task_id=task_id,
            name=request.name,
            folder=request.folder,
            schedule_type=request.schedule_type,
            schedule_value=request.schedule_value,
            cron=request.cron,
            one_time=request.one_time,
        )
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Update config for persistence
        from app.config import get_config
        config = get_config()
        for i, t in enumerate(config.schedule.tasks):
            if t.id == task_id:
                config.schedule.tasks[i] = task
                break
        config.save()
        
        return {
            "message": "Task updated",
            "task": task.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a scheduled task"""
    scheduler = get_scheduler_manager()
    
    # Remove from config first
    from app.config import get_config
    config = get_config()
    config.schedule.tasks = [t for t in config.schedule.tasks if t.id != task_id]
    config.save()
    
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
