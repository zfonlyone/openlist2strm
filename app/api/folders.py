"""Folders API endpoints"""

from typing import Optional
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_config
from app.core.cache import get_cache_manager

router = APIRouter(prefix="/folders")


class FolderInfo(BaseModel):
    """Folder information model"""

    id: str
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


def _encode_folder_id(path: str, db_id: Optional[int] = None) -> str:
    if db_id is not None:
        return f"db:{db_id}"
    token = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")
    return f"cfg:{token}"


def _decode_cfg_id(folder_id: str) -> Optional[str]:
    if not folder_id.startswith("cfg:"):
        return None
    token = folder_id[4:]
    if not token:
        return None
    token += "=" * ((4 - len(token) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
    except Exception:
        return None


@router.get("")
async def list_folders():
    """List all monitored folders"""
    config = get_config()
    cache = get_cache_manager()

    configured_folders = list(dict.fromkeys(config.paths.source))

    db_folders = await cache.get_folders()
    db_folder_map = {f["path"]: f for f in db_folders}

    folders = []
    for path in configured_folders:
        db_info = db_folder_map.get(path, {})
        files = await cache.get_all_files(path)
        folders.append(
            {
                "id": _encode_folder_id(path, db_info.get("id")),
                "path": path,
                "enabled": db_info.get("enabled", True) if db_info else True,
                "last_scan": db_info.get("last_scan"),
                "file_count": len(files),
                "from_config": True,
            }
        )

    for path, db_info in db_folder_map.items():
        if path not in configured_folders:
            files = await cache.get_all_files(path)
            folders.append(
                {
                    "id": _encode_folder_id(path, db_info.get("id")),
                    "path": path,
                    "enabled": db_info.get("enabled", True),
                    "last_scan": db_info.get("last_scan"),
                    "file_count": len(files),
                    "from_config": False,
                }
            )

    return {"folders": folders}


@router.post("")
async def add_folder(request: AddFolderRequest):
    """Add a new folder to monitor. Persistence: updates config + database."""
    cache = get_cache_manager()
    config = get_config()

    await cache.add_folder(request.path, request.enabled)

    if request.path not in config.paths.source:
        config.paths.source.append(request.path)
        config.save()

    return {
        "message": f"Folder added: {request.path}",
        "path": request.path,
        "enabled": request.enabled,
        "persistent": request.path in config.paths.source,
    }


# NOTE: Define /by-id routes BEFORE /{folder_path:path} so they are reachable.
@router.put("/by-id/{folder_id}")
async def update_folder_by_id(folder_id: str, request: UpdateFolderRequest):
    """Update folder by logical ID, then resolve to path."""
    cache = get_cache_manager()

    path = None
    if folder_id.startswith("db:"):
        db_id = folder_id[3:]
        db_folders = await cache.get_folders()
        for f in db_folders:
            if str(f.get("id")) == str(db_id):
                path = f.get("path")
                break
    elif folder_id.startswith("cfg:"):
        path = _decode_cfg_id(folder_id)

    if not path:
        raise HTTPException(status_code=404, detail="Folder ID not found")

    path = "/" + str(path).lstrip("/")
    if request.enabled is not None:
        await cache.add_folder(path, request.enabled)

    return {
        "message": f"Folder updated by id: {folder_id}",
        "path": path,
        "id": folder_id,
        "enabled": request.enabled,
    }


@router.delete("/by-id/{folder_id}")
async def remove_folder_by_id(folder_id: str):
    """Remove folder by logical ID, then resolve to path."""
    cache = get_cache_manager()
    config = get_config()

    path = None
    if folder_id.startswith("db:"):
        db_id = folder_id[3:]
        db_folders = await cache.get_folders()
        for f in db_folders:
            if str(f.get("id")) == str(db_id):
                path = f.get("path")
                break
    elif folder_id.startswith("cfg:"):
        path = _decode_cfg_id(folder_id)

    if not path:
        raise HTTPException(status_code=404, detail="Folder ID not found")

    path = "/" + str(path).lstrip("/")
    if path in config.paths.source:
        config.paths.source.remove(path)
        config.save()

    await cache.remove_folder(path)

    return {"message": f"Folder removed by id: {folder_id}", "path": path, "id": folder_id}


@router.put("/{folder_path:path}")
async def update_folder(folder_path: str, request: UpdateFolderRequest):
    """Update folder settings"""
    cache = get_cache_manager()

    folder_path = "/" + folder_path.lstrip("/")

    if request.enabled is not None:
        await cache.add_folder(folder_path, request.enabled)

    return {
        "message": f"Folder updated: {folder_path}",
        "path": folder_path,
        "enabled": request.enabled,
    }


@router.delete("/{folder_path:path}")
async def remove_folder(folder_path: str):
    """Remove a folder from monitoring. Persistence: removes from config + database."""
    cache = get_cache_manager()
    config = get_config()

    folder_path = "/" + folder_path.lstrip("/")

    if folder_path in config.paths.source:
        config.paths.source.remove(folder_path)
        config.save()

    await cache.remove_folder(folder_path)

    return {
        "message": f"Folder removed: {folder_path}",
        "path": folder_path,
    }


@router.put("")
async def update_folder_by_query(path: str, request: UpdateFolderRequest):
    """Update folder settings by query path (safer for special chars)."""
    return await update_folder(path, request)


@router.delete("")
async def remove_folder_by_query(path: str):
    """Remove folder by query path (safer for special chars)."""
    return await remove_folder(path)


@router.get("/{folder_path:path}/files")
async def list_folder_files(folder_path: str, limit: int = 100, offset: int = 0):
    """List files in a folder from cache."""
    cache = get_cache_manager()

    folder_path = "/" + folder_path.lstrip("/")

    all_files = await cache.get_all_files(folder_path)

    total = len(all_files)
    files = all_files[offset : offset + limit]

    return {
        "folder": folder_path,
        "total": total,
        "offset": offset,
        "limit": limit,
        "files": files,
    }


@router.get("/browse")
async def browse_openlist(path: str = "/"):
    """Browse OpenList directory structure."""
    from app.core.openlist import get_openlist_client

    client = get_openlist_client()

    try:
        items = await client.list_all_files(path)

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
