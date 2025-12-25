"""Cleanup API endpoints"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.cleanup import get_cleanup_manager

router = APIRouter(prefix="/cleanup")


class CleanupRequest(BaseModel):
    """Cleanup request model"""
    path: Optional[str] = None
    dry_run: bool = True


@router.get("/stats")
async def get_cleanup_stats():
    """Get statistics about the STRM directory"""
    cleanup = get_cleanup_manager()
    stats = await cleanup.get_stats()
    return stats


@router.post("/preview")
async def preview_cleanup(request: CleanupRequest = CleanupRequest()):
    """
    Preview cleanup without making changes (dry-run).
    
    Scans for:
    - Invalid/inaccessible folders
    - Broken symbolic links
    - Empty directories
    - Orphaned STRM files
    """
    cleanup = get_cleanup_manager()
    result = await cleanup.preview(request.path)
    return result.to_dict()


@router.post("")
async def run_cleanup(request: CleanupRequest = CleanupRequest()):
    """
    Run cleanup operation.
    
    - **path**: Optional path to clean (defaults to STRM output)
    - **dry_run**: If true, only preview changes without deleting
    
    Removes:
    - Broken symbolic links
    - Empty directories
    
    Note: Invalid folders and orphaned STRM files require manual review.
    """
    cleanup = get_cleanup_manager()
    result = await cleanup.cleanup(request.path, dry_run=request.dry_run)
    
    return result.to_dict()


@router.post("/symlinks")
async def cleanup_broken_symlinks(path: Optional[str] = None, dry_run: bool = True):
    """
    Clean up broken symbolic links only.
    
    - **path**: Optional path to scan
    - **dry_run**: Preview only if true
    """
    cleanup = get_cleanup_manager()
    broken = await cleanup.scan_broken_symlinks(path)
    
    result = {
        "broken_symlinks": broken,
        "count": len(broken),
        "dry_run": dry_run,
        "deleted": 0,
    }
    
    if not dry_run:
        import os
        deleted = 0
        errors = []
        for link in broken:
            try:
                os.unlink(link)
                deleted += 1
            except Exception as e:
                errors.append(f"{link}: {e}")
        result["deleted"] = deleted
        result["errors"] = errors
    
    return result


@router.post("/empty-dirs")
async def cleanup_empty_dirs(path: Optional[str] = None, dry_run: bool = True):
    """
    Clean up empty directories only.
    
    - **path**: Optional path to scan
    - **dry_run**: Preview only if true
    """
    cleanup = get_cleanup_manager()
    empty = await cleanup.scan_empty_dirs(path)
    
    result = {
        "empty_directories": empty,
        "count": len(empty),
        "dry_run": dry_run,
        "deleted": 0,
    }
    
    if not dry_run:
        import os
        deleted = 0
        errors = []
        for dir_path in empty:
            try:
                os.rmdir(dir_path)
                deleted += 1
            except Exception as e:
                errors.append(f"{dir_path}: {e}")
        result["deleted"] = deleted
        result["errors"] = errors
    
    return result
