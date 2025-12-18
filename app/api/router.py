"""API router configuration"""

from fastapi import APIRouter

from .scan import router as scan_router
from .folders import router as folders_router
from .tasks import router as tasks_router
from .settings import router as settings_router

api_router = APIRouter(prefix="/api")

# Include sub-routers
api_router.include_router(scan_router, tags=["scan"])
api_router.include_router(folders_router, tags=["folders"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(settings_router, tags=["settings"])


@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "openlist2strm"}


@api_router.get("/status")
async def get_status():
    """Get overall system status"""
    from app.core.cache import get_cache_manager
    from app.core.scanner import get_scanner
    from app.scheduler import get_scheduler_manager
    
    cache = get_cache_manager()
    scanner = get_scanner()
    scheduler = get_scheduler_manager()
    
    # Get cache stats
    stats = await cache.get_stats()
    last_scan = await cache.get_last_scan()
    
    return {
        "scanner": {
            "running": scanner.is_running,
            "progress": scanner.progress.to_dict() if scanner.is_running else None,
        },
        "scheduler": scheduler.status,
        "cache": stats,
        "last_scan": last_scan,
    }
