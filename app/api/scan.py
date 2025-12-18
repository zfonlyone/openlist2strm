"""Scan API endpoints"""

from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.scanner import get_scanner
from app.scheduler import get_scheduler_manager

router = APIRouter(prefix="/scan")


class ScanRequest(BaseModel):
    """Scan request model"""
    folders: Optional[List[str]] = None
    force: bool = False


class ScanResponse(BaseModel):
    """Scan response model"""
    message: str
    task_id: Optional[str] = None
    immediate: bool = False
    result: Optional[dict] = None


@router.post("", response_model=ScanResponse)
async def trigger_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger a scan operation.
    
    - **folders**: Optional list of folders to scan (default: all configured folders)
    - **force**: Force regenerate all STRM files (default: false for incremental)
    """
    scanner = get_scanner()
    
    if scanner.is_running:
        raise HTTPException(
            status_code=409,
            detail="A scan is already in progress"
        )
    
    scheduler = get_scheduler_manager()
    
    # Execute scan
    result = await scheduler.trigger_now(
        folders=request.folders,
        force=request.force,
    )
    
    return ScanResponse(
        message="Scan completed",
        immediate=True,
        result=result,
    )


@router.get("/progress")
async def get_scan_progress():
    """Get current scan progress"""
    scanner = get_scanner()
    
    return {
        "running": scanner.is_running,
        "progress": scanner.progress.to_dict(),
    }


@router.post("/cancel")
async def cancel_scan():
    """Cancel the current scan"""
    scanner = get_scanner()
    
    if not scanner.is_running:
        raise HTTPException(
            status_code=400,
            detail="No scan is currently running"
        )
    
    scanner.cancel()
    
    return {"message": "Scan cancellation requested"}


@router.get("/history")
async def get_scan_history(limit: int = 20):
    """
    Get scan history.
    
    - **limit**: Maximum number of records to return (default: 20)
    """
    from app.core.cache import get_cache_manager
    
    cache = get_cache_manager()
    history = await cache.get_scan_history(limit)
    
    return {"history": history}
