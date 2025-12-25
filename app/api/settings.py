"""Settings API endpoints"""

import os
import json
import yaml
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_config, reload_config

router = APIRouter(prefix="/settings")


# ============ Request Models ============

class QoSSettings(BaseModel):
    """QoS settings model"""
    qps: Optional[float] = None
    max_concurrent: Optional[int] = None
    interval: Optional[int] = None
    threading_mode: Optional[str] = None
    thread_pool_size: Optional[int] = None
    rate_limit: Optional[int] = None


class OpenListTokenUpdate(BaseModel):
    """OpenList token update model"""
    token: str


class TelegramSettings(BaseModel):
    """Telegram settings model"""
    enabled: Optional[bool] = None
    token: Optional[str] = None
    chat_id: Optional[str] = None
    allowed_users: Optional[List[int]] = None
    notify_on_scan_start: Optional[bool] = None
    notify_on_scan_complete: Optional[bool] = None
    notify_on_error: Optional[bool] = None


class EmbySettings(BaseModel):
    """Emby settings model"""
    enabled: Optional[bool] = None
    host: Optional[str] = None
    api_key: Optional[str] = None
    library_id: Optional[str] = None
    notify_on_scan: Optional[bool] = None


class StrmSettings(BaseModel):
    """STRM generation settings model"""
    mode: Optional[str] = None  # "path" or "direct_link"
    url_encode: Optional[bool] = None
    output_path: Optional[str] = None
    keep_structure: Optional[bool] = None


class ScanSettings(BaseModel):
    """Scan mode settings model"""
    mode: Optional[str] = None  # "incremental" or "full"
    data_source: Optional[str] = None  # "cache" or "realtime"


# ============ General Settings ============

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
        "version": "1.1.0",
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
                if key in ['password', 'token', 'api_token', 'api_key']:
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


# ============ OpenList Settings ============

@router.put("/openlist/token")
async def update_openlist_token(data: OpenListTokenUpdate):
    """Update OpenList API token"""
    config = get_config()
    
    # Update current config object
    config.openlist.token = data.token
    
    # Save using robust logic
    if config.save():
        # Reload to ensure consistency (though Config.save normally handles it)
        reload_config()
        return {"message": "OpenList token updated", "success": True}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to save configuration. Please check if /config directory is writable and not mounted as Read-Only."
        )


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


# ============ Telegram Settings ============

@router.get("/telegram")
async def get_telegram_settings():
    """Get Telegram bot settings"""
    config = get_config()
    return {
        "enabled": config.telegram.enabled,
        "token": "***" if config.telegram.token else "",
        "chat_id": config.telegram.chat_id,
        "allowed_users": config.telegram.allowed_users,
        "notify": {
            "on_scan_start": config.telegram.notify.on_scan_start,
            "on_scan_complete": config.telegram.notify.on_scan_complete,
            "on_error": config.telegram.notify.on_error,
        },
    }


@router.put("/telegram")
async def update_telegram_settings(settings: TelegramSettings):
    """
    Update Telegram bot settings.
    
    - **enabled**: Enable/disable Telegram bot
    - **token**: Bot token from @BotFather
    - **chat_id**: Your Telegram user/chat ID for notifications
    - **allowed_users**: List of user IDs allowed to control the bot
    """
    config = get_config()
    
    if settings.enabled is not None:
        config.telegram.enabled = settings.enabled
    if settings.token is not None and settings.token != "***":
        config.telegram.token = settings.token
    if settings.chat_id is not None:
        config.telegram.chat_id = settings.chat_id
    if settings.allowed_users is not None:
        config.telegram.allowed_users = settings.allowed_users
    
    # Notify settings
    if settings.notify_on_scan_start is not None:
        config.telegram.notify.on_scan_start = settings.notify_on_scan_start
    if settings.notify_on_scan_complete is not None:
        config.telegram.notify.on_scan_complete = settings.notify_on_scan_complete
    if settings.notify_on_error is not None:
        config.telegram.notify.on_error = settings.notify_on_error
    
    if config.save():
        return {"message": "Telegram settings updated", "success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save Telegram settings. Check permissions.")


@router.post("/telegram/test")
async def test_telegram_connection():
    """Test Telegram bot connection"""
    import httpx
    
    config = get_config()
    
    if not config.telegram.token:
        return {
            "success": False,
            "error": "未配置 Telegram Bot Token",
        }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.telegram.org/bot{config.telegram.token}/getMe"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    return {
                        "success": True,
                        "bot_username": bot_info.get("username"),
                        "bot_name": bot_info.get("first_name"),
                    }
                else:
                    return {
                        "success": False,
                        "error": data.get("description", "Unknown error"),
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "连接超时",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============ Emby Settings ============

@router.get("/emby")
async def get_emby_settings():
    """Get Emby notification settings"""
    config = get_config()
    return {
        "enabled": config.emby.enabled,
        "host": config.emby.host,
        "api_key": "***" if config.emby.api_key else "",
        "library_id": config.emby.library_id,
        "notify_on_scan": config.emby.notify_on_scan,
        "tutorial": "获取 API Key: Emby 设置 → 高级 → API 密钥 → 新建应用程序",
    }


@router.put("/emby")
async def update_emby_settings(settings: EmbySettings):
    """
    Update Emby notification settings.
    """
    config = get_config()
    
    if settings.enabled is not None:
        config.emby.enabled = settings.enabled
    if settings.host is not None:
        config.emby.host = settings.host
    if settings.api_key is not None and settings.api_key != "***":
        config.emby.api_key = settings.api_key
    if settings.library_id is not None:
        config.emby.library_id = settings.library_id
    if settings.notify_on_scan is not None:
        config.emby.notify_on_scan = settings.notify_on_scan
    
    if config.save():
        return {"message": "Emby settings updated", "success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save Emby settings. Check permissions.")


@router.post("/emby/test")
async def test_emby_connection():
    """Test Emby connection"""
    from app.core.emby import get_emby_client
    
    client = get_emby_client()
    result = await client.test_connection()
    
    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Connection failed")
        )
    
    return result


@router.get("/emby/libraries")
async def get_emby_libraries():
    """Get list of Emby libraries"""
    from app.core.emby import get_emby_client
    
    client = get_emby_client()
    libraries = await client.get_libraries()
    
    return {"libraries": libraries}


# ============ STRM Settings ============

@router.get("/strm")
async def get_strm_settings():
    """Get STRM generation settings"""
    config = get_config()
    return {
        "mode": config.strm.mode,
        "url_encode": config.strm.url_encode,
        "output_path": config.strm.output_path,
        "keep_structure": config.strm.keep_structure,
        "extensions": config.strm.extensions,
        "modes": {
            "path": "使用相对路径 (适合本地WebDAV挂载)",
            "direct_link": "使用完整直链URL (适合远程访问)",
        },
    }


@router.put("/strm")
async def update_strm_settings(settings: StrmSettings):
    """
    Update STRM generation settings.
    """
    if settings.mode is not None and settings.mode not in ["path", "direct_link"]:
        raise HTTPException(status_code=400, detail="Mode must be 'path' or 'direct_link'")
    
    config = get_config()
    
    if settings.mode is not None:
        config.strm.mode = settings.mode
    if settings.url_encode is not None:
        config.strm.url_encode = settings.url_encode
    if settings.output_path is not None:
        config.strm.output_path = settings.output_path
    if settings.keep_structure is not None:
        config.strm.keep_structure = settings.keep_structure
    
    if config.save():
        return {"message": "STRM settings updated", "success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save STRM settings. Check permissions.")


# ============ Scan Settings ============

@router.get("/scan")
async def get_scan_settings():
    """Get scan mode settings"""
    config = get_config()
    return {
        "mode": config.scan.mode,
        "data_source": config.scan.data_source,
        "modes": {
            "incremental": "增量更新 - 仅处理新增/修改的文件",
            "full": "全量扫描 - 重新处理所有文件",
        },
        "data_sources": {
            "cache": "读取缓存 - 使用本地缓存的文件列表",
            "realtime": "实时读取 - 每次从网盘获取最新数据",
        },
    }


@router.put("/scan")
async def update_scan_settings(settings: ScanSettings):
    """
    Update scan mode settings.
    """
    if settings.mode is not None and settings.mode not in ["incremental", "full"]:
        raise HTTPException(status_code=400, detail="Mode must be 'incremental' or 'full'")
    if settings.data_source is not None and settings.data_source not in ["cache", "realtime"]:
        raise HTTPException(status_code=400, detail="Data source must be 'cache' or 'realtime'")
    
    config = get_config()
    
    if settings.mode is not None:
        config.scan.mode = settings.mode
    if settings.data_source is not None:
        config.scan.data_source = settings.data_source
    
    if config.save():
        return {"message": "Scan settings updated", "success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save scan settings. Check permissions.")


# ============ QoS Settings ============

@router.get("/qos")
async def get_qos_settings():
    """Get QoS settings"""
    from app.core.qos import get_qos_limiter
    
    limiter = get_qos_limiter()
    config = get_config()
    
    return {
        "stats": limiter.stats,
        "config": {
            "qps": config.qos.qps,
            "max_concurrent": config.qos.max_concurrent,
            "interval": config.qos.interval,
            "threading_mode": config.qos.threading_mode,
            "thread_pool_size": config.qos.thread_pool_size,
            "rate_limit": config.qos.rate_limit,
        },
    }


@router.put("/qos")
async def update_qos_settings(settings: QoSSettings):
    """
    Update QoS settings and persist to config.yml.
    """
    from app.core.qos import get_qos_limiter
    
    config = get_config()
    limiter = get_qos_limiter()
    
    # Update current config object
    if settings.qps is not None:
        config.qos.qps = settings.qps
    if settings.max_concurrent is not None:
        config.qos.max_concurrent = settings.max_concurrent
    if settings.interval is not None:
        config.qos.interval = settings.interval
    if settings.threading_mode is not None:
        config.qos.threading_mode = settings.threading_mode
    if settings.thread_pool_size is not None:
        config.qos.thread_pool_size = settings.thread_pool_size
    if settings.rate_limit is not None:
        config.qos.rate_limit = settings.rate_limit

    # Update limiter in memory
    limiter.update_limits(
        qps=config.qos.qps,
        max_concurrent=config.qos.max_concurrent,
        interval_ms=config.qos.interval,
    )
    
    # Persist to disk
    if config.save():
        return {
            "message": "QoS settings updated and persisted",
            "stats": limiter.stats,
            "success": True
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to persist QoS settings. Check permissions.")


# ============ Cache Settings ============

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
