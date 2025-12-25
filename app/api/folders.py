"""Folders API endpoints"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_config
from app.core.cache import get_cache_manager

router = APIRouter(prefix="/folders")


class FolderInfo(BaseModel):
    """Folder information model"""
    path: str
    enabled: bool = True
    last_scan: Optional[str] = None
    file_count: Optional[int] = None


class AddFolderRequest(BaseModel):
    """Add folder request model"""
    path: str
    enabled: bool = True


class UpdateFolderRequest(BaseModel):
    """Update folder request model"""
    enabled: Optional[bool] = None


@router.get("")
async def list_folders():
    """List all monitored folders"""
    config = get_config()
    cache = get_cache_manager()
    
    # Get configured folders from config
    configured_folders = set(config.paths.source)
    
    # Get folders from database
    db_folders = await cache.get_folders()
    db_folder_map = {f["path"]: f for f in db_folders}
    
    folders = []
    for path in configured_folders:
        db_info = db_folder_map.get(path, {})
        
        # Get file count for this folder
        files = await cache.get_all_files(path)
        
        folders.append({
            "path": path,
            "enabled": db_info.get("enabled", True) if db_info else True,
            "last_scan": db_info.get("last_scan"),
            "file_count": len(files),
            "from_config": True,
        })
    
    # Add any database-only folders
    for path, db_info in db_folder_map.items():
        if path not in configured_folders:
            files = await cache.get_all_files(path)
            folders.append({
                "path": path,
                "enabled": db_info.get("enabled", True),
                "last_scan": db_info.get("last_scan"),
                "file_count": len(files),
                "from_config": False,
            })
    
    return {"folders": folders}


@router.post("")
async def add_folder(request: AddFolderRequest):
    """
    Add a new folder to monitor.
    
    Persistence: Automatically updates config.yml and database.
    """
    cache = get_cache_manager()
    config = get_config()
    
    # Add to database
    await cache.add_folder(request.path, request.enabled)
    
    # Sync to config.yml if not already there
    if request.path not in config.paths.source:
        config.paths.source.append(request.path)
        if not config.save():
            # Still proceed as it's saved in DB, but warn or log?
            # For now, we return success but the error handling in config.save() prints to log
            pass
            
    return {
        "message": f"Folder added: {request.path}",
        "path": request.path,
        "enabled": request.enabled,
        "persistent": request.path in config.paths.source
    }


@router.put("/{folder_path:path}")
async def update_folder(folder_path: str, request: UpdateFolderRequest):
    """Update folder settings"""
    cache = get_cache_manager()
    
    # Normalize path
    folder_path = "/" + folder_path.lstrip("/")
    
    if request.enabled is not None:
        # Use add_folder which handles upsert
        await cache.add_folder(folder_path, request.enabled)
    
    return {
        "message": f"Folder updated: {folder_path}",
        "path": folder_path,
        "enabled": request.enabled,
    }


@router.delete("/{folder_path:path}")
async def remove_folder(folder_path: str):
    """
    Remove a folder from monitoring.
    
    Persistence: Removes from both database and config.yml.
    """
    cache = get_cache_manager()
    config = get_config()
    
    # Normalize path
    folder_path = "/" + folder_path.lstrip("/")
    
    # Remove from config if present
    if folder_path in config.paths.source:
        config.paths.source.remove(folder_path)
        config.save()
    
    # Remove from database
    await cache.remove_folder(folder_path)
    
    return {
        "message": f"Folder removed: {folder_path}",
        "path": folder_path,
    }


@router.get("/{folder_path:path}/files")
async def list_folder_files(folder_path: str, limit: int = 100, offset: int = 0):
    """
    List files in a folder from cache.
    
    - **limit**: Maximum number of files to return
    - **offset**: Number of files to skip
    """
    cache = get_cache_manager()
    
    # Normalize path
    folder_path = "/" + folder_path.lstrip("/")
    
    # Get all files for the folder
    all_files = await cache.get_all_files(folder_path)
    
    # Apply pagination
    total = len(all_files)
    files = all_files[offset:offset + limit]
    
    return {
        "folder": folder_path,
        "total": total,
        "offset": offset,
        "limit": limit,
        "files": files,
    }


@router.get("/browse")
async def browse_openlist(path: str = "/"):
    """
    Browse OpenList directory structure.
    
    - **path**: Directory path in OpenList to browse
    """
    from app.core.openlist import get_openlist_client
    
    client = get_openlist_client()
    
    try:
        items = await client.list_all_files(path)
        
        # Separate directories and files
        dirs = [item for item in items if item.get("is_dir")]
        files = [item for item in items if not item.get("is_dir")]
        
        return {
            "path": path,
            "directories": dirs,
            "files": files,
            "total_dirs": len(dirs),
            "total_files": len(files),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to browse path: {str(e)}"
        )
