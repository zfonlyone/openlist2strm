"""Settings API endpoints"""

import os
import json
import yaml
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_config, reload_config

router = APIRouter(prefix="/settings")


class QoSSettings(BaseModel):
    """QoS settings model"""
    qps: Optional[float] = None
    max_concurrent: Optional[int] = None
    interval: Optional[int] = None


class OpenListTokenUpdate(BaseModel):
    """OpenList token update model"""
    token: str


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


@router.get("/export")
async def export_config():
    """
    Export current configuration as JSON.
    Sensitive data (passwords, tokens) are masked.
    """
    config = get_config()
    config_dict = config.to_dict()
    
    # Add export metadata
    export_data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "config": config_dict,
    }
    
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=openlist2strm_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )


@router.get("/export/full")
async def export_config_full():
    """
    Export full configuration file (as YAML string).
    WARNING: Contains sensitive data!
    """
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yml")
    
    if not Path(config_path).exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return {
        "format": "yaml",
        "content": content,
        "path": config_path,
    }


@router.post("/import")
async def import_config(file: UploadFile = File(...)):
    """
    Import configuration from uploaded JSON file.
    Merges with existing config, won't overwrite passwords.
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files are supported")
    
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        # Validate structure
        if "config" not in data:
            raise HTTPException(status_code=400, detail="Invalid config format: missing 'config' key")
        
        imported_config = data["config"]
        
        # Load current config file
        config_path = os.environ.get("CONFIG_PATH", "/config/config.yml")
        
        if Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                current_config = yaml.safe_load(f) or {}
        else:
            current_config = {}
        
        # Merge configs (preserve passwords and tokens)
        def merge_config(current, imported):
            for key, value in imported.items():
                if key in ['password', 'token', 'api_token']:
                    # Don't overwrite sensitive fields with masked values
                    if value in ['***', '']:
                        continue
                if isinstance(value, dict) and key in current and isinstance(current[key], dict):
                    merge_config(current[key], value)
                else:
                    current[key] = value
        
        merge_config(current_config, imported_config)
        
        # Backup current config
        if Path(config_path).exists():
            backup_path = f"{config_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
            with open(backup_path, "w", encoding="utf-8") as f:
                yaml.dump(current_config, f, default_flow_style=False, allow_unicode=True)
        
        # Write merged config
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(current_config, f, default_flow_style=False, allow_unicode=True)
        
        # Reload config
        reload_config()
        
        return {"message": "Config imported successfully", "merged_keys": list(imported_config.keys())}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.put("/openlist/token")
async def update_openlist_token(data: OpenListTokenUpdate):
    """Update OpenList API token"""
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yml")
    
    if not Path(config_path).exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        
        # Update token
        if "openlist" not in config_data:
            config_data["openlist"] = {}
        config_data["openlist"]["token"] = data.token
        
        # Write back
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # Reload
        reload_config()
        
        return {"message": "OpenList token updated", "success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update token: {str(e)}")


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
    from pathlib import Path
    
    # Close current connection
    await close_cache_manager()
    
    # Delete database file
    db_path = Path("/data/cache.db")
    if db_path.exists():
        os.remove(db_path)
    
    return {"message": "Cache cleared"}

