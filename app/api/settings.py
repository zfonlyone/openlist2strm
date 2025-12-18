"""Settings API endpoints"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_config, reload_config

router = APIRouter(prefix="/settings")


class QoSSettings(BaseModel):
    """QoS settings model"""
    qps: Optional[float] = None
    max_concurrent: Optional[int] = None
    interval: Optional[int] = None


@router.get("")
async def get_settings():
    """Get current settings"""
    config = get_config()
    return config.to_dict()


@router.post("/reload")
async def reload_settings():
    """Reload settings from config file"""
    try:
        config = reload_config()
        return {
            "message": "Settings reloaded",
            "settings": config.to_dict(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload settings: {str(e)}"
        )


@router.get("/qos")
async def get_qos_settings():
    """Get QoS settings"""
    from app.core.qos import get_qos_limiter
    
    limiter = get_qos_limiter()
    return limiter.stats


@router.put("/qos")
async def update_qos_settings(settings: QoSSettings):
    """
    Update QoS settings dynamically.
    
    Note: These changes are temporary and will be reset on restart.
    To persist, update config.yml.
    """
    from app.core.qos import get_qos_limiter
    
    limiter = get_qos_limiter()
    
    limiter.update_limits(
        qps=settings.qps,
        max_concurrent=settings.max_concurrent,
        interval_ms=settings.interval,
    )
    
    return {
        "message": "QoS settings updated",
        "stats": limiter.stats,
    }


@router.get("/openlist/test")
async def test_openlist_connection():
    """Test OpenList connection"""
    from app.core.openlist import get_openlist_client
    
    client = get_openlist_client()
    
    try:
        # Try to list root directory
        result = await client.list_files("/")
        
        return {
            "status": "connected",
            "message": "Successfully connected to OpenList",
            "provider": result.get("provider"),
            "items": len(result.get("content", [])),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to OpenList: {str(e)}"
        )


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    from app.core.cache import get_cache_manager
    
    cache = get_cache_manager()
    stats = await cache.get_stats()
    
    return stats


@router.post("/cache/clear")
async def clear_cache():
    """Clear all cache data"""
    from app.core.cache import get_cache_manager, close_cache_manager
    import os
    from pathlib import Path
    
    # Close current connection
    await close_cache_manager()
    
    # Delete database file
    db_path = Path("/data/cache.db")
    if db_path.exists():
        os.remove(db_path)
    
    return {"message": "Cache cleared"}
