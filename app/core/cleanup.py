"""Cleanup utilities for maintaining local-cloud consistency"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of cleanup operation"""
    invalid_folders: List[str] = field(default_factory=list)
    broken_symlinks: List[str] = field(default_factory=list)
    empty_dirs: List[str] = field(default_factory=list)
    orphaned_strm: List[str] = field(default_factory=list)
    deleted_count: int = 0
    dry_run: bool = True
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "invalid_folders": self.invalid_folders,
            "broken_symlinks": self.broken_symlinks,
            "empty_dirs": self.empty_dirs,
            "orphaned_strm": self.orphaned_strm,
            "deleted_count": self.deleted_count,
            "dry_run": self.dry_run,
            "errors": self.errors,
            "total_issues": len(self.invalid_folders) + len(self.broken_symlinks) + 
                          len(self.empty_dirs) + len(self.orphaned_strm),
        }


class CleanupManager:
    """
    Manages cleanup of invalid files, folders, and symlinks.
    
    Features:
    - Detect and remove broken symlinks
    - Remove empty directories
    - Remove orphaned STRM files
    - Sync local state with cloud
    """
    
    def __init__(self):
        """Initialize cleanup manager"""
        self._config = get_config()
    
    async def scan_invalid_folders(self, base_path: Optional[str] = None) -> List[str]:
        """
        Scan for invalid/inaccessible folders.
        
        Args:
            base_path: Path to scan. Defaults to STRM output.
            
        Returns:
            List of invalid folder paths
        """
        path = Path(base_path or self._config.strm.output_path)
        invalid = []
        
        if not path.exists():
            return invalid
        
        try:
            for item in path.rglob("*"):
                if item.is_dir():
                    try:
                        # Try to list directory contents
                        list(item.iterdir())
                    except PermissionError:
                        invalid.append(str(item))
                    except OSError as e:
                        logger.warning(f"Invalid folder detected: {item} - {e}")
                        invalid.append(str(item))
        except Exception as e:
            logger.error(f"Error scanning folders: {e}")
        
        return invalid
    
    async def scan_broken_symlinks(self, base_path: Optional[str] = None) -> List[str]:
        """
        Scan for broken symbolic links.
        
        Args:
            base_path: Path to scan. Defaults to STRM output.
            
        Returns:
            List of broken symlink paths
        """
        path = Path(base_path or self._config.strm.output_path)
        broken = []
        
        if not path.exists():
            return broken
        
        try:
            for item in path.rglob("*"):
                if item.is_symlink():
                    target = item.resolve()
                    if not target.exists():
                        broken.append(str(item))
        except Exception as e:
            logger.error(f"Error scanning symlinks: {e}")
        
        return broken
    
    async def scan_empty_dirs(self, base_path: Optional[str] = None) -> List[str]:
        """
        Scan for empty directories.
        
        Args:
            base_path: Path to scan. Defaults to STRM output.
            
        Returns:
            List of empty directory paths
        """
        path = Path(base_path or self._config.strm.output_path)
        empty = []
        
        if not path.exists():
            return empty
        
        try:
            # Walk bottom-up to find empty dirs
            for dirpath, dirnames, filenames in os.walk(str(path), topdown=False):
                dir_path = Path(dirpath)
                # Skip root directory
                if dir_path == path:
                    continue
                # Check if truly empty (no files, no non-empty subdirs)
                if not any(dir_path.iterdir()):
                    empty.append(str(dir_path))
        except Exception as e:
            logger.error(f"Error scanning empty dirs: {e}")
        
        return empty
    
    async def scan_orphaned_strm(
        self, 
        strm_path: Optional[str] = None,
        source_folders: Optional[List[str]] = None
    ) -> List[str]:
        """
        Scan for STRM files whose source no longer exists.
        
        Note: This requires access to OpenList to verify sources.
        For now, returns empty list. Full implementation needs async OpenList checks.
        
        Returns:
            List of orphaned STRM file paths
        """
        # TODO: Implement with OpenList integration
        # This would need to check each STRM's source path against OpenList
        return []
    
    async def preview(self, base_path: Optional[str] = None) -> CleanupResult:
        """
        Preview cleanup without making changes (dry-run).
        
        Args:
            base_path: Path to scan
            
        Returns:
            CleanupResult with all detected issues
        """
        result = CleanupResult(dry_run=True)
        
        result.invalid_folders = await self.scan_invalid_folders(base_path)
        result.broken_symlinks = await self.scan_broken_symlinks(base_path)
        result.empty_dirs = await self.scan_empty_dirs(base_path)
        result.orphaned_strm = await self.scan_orphaned_strm(base_path)
        
        logger.info(
            f"Cleanup preview: {len(result.invalid_folders)} invalid folders, "
            f"{len(result.broken_symlinks)} broken symlinks, "
            f"{len(result.empty_dirs)} empty dirs"
        )
        
        return result
    
    async def cleanup(
        self, 
        base_path: Optional[str] = None,
        dry_run: bool = False
    ) -> CleanupResult:
        """
        Perform cleanup operation.
        
        Args:
            base_path: Path to clean
            dry_run: If True, only preview changes
            
        Returns:
            CleanupResult with results
        """
        result = await self.preview(base_path)
        result.dry_run = dry_run
        
        if dry_run:
            return result
        
        deleted = 0
        
        # Remove broken symlinks
        for link_path in result.broken_symlinks:
            try:
                os.unlink(link_path)
                deleted += 1
                logger.info(f"Removed broken symlink: {link_path}")
            except Exception as e:
                result.errors.append(f"Failed to remove {link_path}: {e}")
                logger.error(f"Failed to remove broken symlink {link_path}: {e}")
        
        # Remove empty directories (bottom-up order already from scan)
        for dir_path in result.empty_dirs:
            try:
                os.rmdir(dir_path)
                deleted += 1
                logger.info(f"Removed empty directory: {dir_path}")
            except Exception as e:
                result.errors.append(f"Failed to remove {dir_path}: {e}")
                logger.warning(f"Failed to remove empty dir {dir_path}: {e}")
        
        # Note: Invalid folders and orphaned STRM require manual review
        # We don't auto-delete them as they may need investigation
        
        result.deleted_count = deleted
        
        logger.info(f"Cleanup complete: {deleted} items removed")
        
        return result
    
    async def get_stats(self, base_path: Optional[str] = None) -> dict:
        """
        Get statistics about the STRM directory.
        
        Returns:
            Dict with directory statistics
        """
        path = Path(base_path or self._config.strm.output_path)
        
        stats = {
            "path": str(path),
            "exists": path.exists(),
            "total_files": 0,
            "total_dirs": 0,
            "strm_files": 0,
            "total_size_bytes": 0,
        }
        
        if not path.exists():
            return stats
        
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    stats["total_files"] += 1
                    stats["total_size_bytes"] += item.stat().st_size
                    if item.suffix.lower() == ".strm":
                        stats["strm_files"] += 1
                elif item.is_dir():
                    stats["total_dirs"] += 1
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            stats["error"] = str(e)
        
        return stats


# Global instance
_cleanup_manager: Optional[CleanupManager] = None


def get_cleanup_manager() -> CleanupManager:
    """Get the global cleanup manager instance"""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = CleanupManager()
    return _cleanup_manager
