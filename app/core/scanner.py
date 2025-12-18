"""Scanner module for traversing OpenList and generating STRM files"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional, Set

from app.config import get_config
from .openlist import OpenListClient, get_openlist_client
from .strm_generator import StrmGenerator, get_strm_generator
from .cache import CacheManager, get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class ScanProgress:
    """Scan progress tracking"""
    folder: str = ""
    status: str = "idle"  # idle, scanning, completed, failed, cancelled
    current_path: str = ""
    files_scanned: int = 0
    files_created: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Get scan duration in seconds"""
        if self.start_time:
            end = self.end_time or datetime.now()
            return (end - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "folder": self.folder,
            "status": self.status,
            "current_path": self.current_path,
            "files_scanned": self.files_scanned,
            "files_created": self.files_created,
            "files_updated": self.files_updated,
            "files_deleted": self.files_deleted,
            "errors": self.errors[-10:],  # Last 10 errors
            "error_count": len(self.errors),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
        }


class Scanner:
    """
    Scanner that traverses OpenList directories and generates STRM files.
    
    Features:
    - Recursive directory traversal
    - Incremental updates based on file modification time
    - Progress callbacks
    - Cancellation support
    """
    
    def __init__(
        self,
        client: Optional[OpenListClient] = None,
        generator: Optional[StrmGenerator] = None,
        cache: Optional[CacheManager] = None,
    ):
        """
        Initialize scanner.
        
        Args:
            client: OpenList API client
            generator: STRM file generator
            cache: Cache manager for incremental updates
        """
        self.client = client or get_openlist_client()
        self.generator = generator or get_strm_generator()
        self.cache = cache or get_cache_manager()
        
        # Configuration
        config = get_config()
        self.incremental_enabled = config.incremental.enabled
        self.check_method = config.incremental.check_method
        
        # State
        self._progress = ScanProgress()
        self._cancelled = False
        self._running = False
        self._progress_callback: Optional[Callable[[ScanProgress], None]] = None
    
    @property
    def progress(self) -> ScanProgress:
        """Get current progress"""
        return self._progress
    
    @property
    def is_running(self) -> bool:
        """Check if scan is running"""
        return self._running
    
    def set_progress_callback(self, callback: Callable[[ScanProgress], None]) -> None:
        """Set progress callback function"""
        self._progress_callback = callback
    
    def _update_progress(self, **kwargs) -> None:
        """Update progress and call callback"""
        for key, value in kwargs.items():
            if hasattr(self._progress, key):
                setattr(self._progress, key, value)
        
        if self._progress_callback:
            try:
                self._progress_callback(self._progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    def cancel(self) -> None:
        """Cancel the current scan"""
        if self._running:
            self._cancelled = True
            logger.info("Scan cancellation requested")
    
    async def scan_folder(
        self,
        folder: str,
        force: bool = False,
    ) -> ScanProgress:
        """
        Scan a single folder and generate STRM files.
        
        Args:
            folder: Folder path in OpenList to scan
            force: Force regenerate all STRM files
            
        Returns:
            Scan progress with results
        """
        if self._running:
            raise RuntimeError("Another scan is already running")
        
        self._running = True
        self._cancelled = False
        self._progress = ScanProgress(
            folder=folder,
            status="scanning",
            start_time=datetime.now(),
        )
        self.generator.reset_stats()
        
        # Start recording in cache
        scan_id = await self.cache.start_scan(folder)
        
        logger.info(f"Starting scan: {folder}")
        self._update_progress()
        
        try:
            # Track processed paths for cleanup
            processed_paths: Set[str] = set()
            
            # Walk through directory tree
            async for current_path, dirs, files in self.client.walk(folder):
                if self._cancelled:
                    self._update_progress(status="cancelled")
                    break
                
                self._update_progress(current_path=current_path)
                
                # Process each file
                for file_info in files:
                    if self._cancelled:
                        break
                    
                    await self._process_file(
                        current_path,
                        file_info,
                        force,
                        processed_paths,
                    )
            
            # Cleanup deleted files
            if not self._cancelled:
                deleted_count = await self._cleanup_deleted(folder, processed_paths)
                self._update_progress(files_deleted=deleted_count)
            
            # Update final status
            if self._cancelled:
                status = "cancelled"
            else:
                status = "completed"
            
            self._progress.end_time = datetime.now()
            self._update_progress(
                status=status,
                files_created=self.generator.stats["files_created"],
                files_updated=self.generator.stats["files_updated"],
            )
            
            # Update cache
            await self.cache.finish_scan(
                scan_id=scan_id,
                files_scanned=self._progress.files_scanned,
                files_created=self._progress.files_created,
                files_updated=self._progress.files_updated,
                files_deleted=self._progress.files_deleted,
                status=status,
            )
            await self.cache.update_folder_scan_time(folder)
            
            logger.info(
                f"Scan completed: {folder} - "
                f"scanned={self._progress.files_scanned}, "
                f"created={self._progress.files_created}, "
                f"updated={self._progress.files_updated}, "
                f"deleted={self._progress.files_deleted}"
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Scan failed: {folder} - {error_msg}")
            
            self._progress.errors.append(error_msg)
            self._progress.end_time = datetime.now()
            self._update_progress(status="failed")
            
            await self.cache.finish_scan(
                scan_id=scan_id,
                files_scanned=self._progress.files_scanned,
                files_created=self._progress.files_created,
                files_updated=self._progress.files_updated,
                status="failed",
                error_message=error_msg,
            )
        
        finally:
            self._running = False
        
        return self._progress
    
    async def _process_file(
        self,
        current_path: str,
        file_info: dict,
        force: bool,
        processed_paths: Set[str],
    ) -> None:
        """Process a single file"""
        name = file_info.get("name", "")
        size = file_info.get("size", 0)
        modified = file_info.get("modified", "")
        
        file_path = f"{current_path.rstrip('/')}/{name}"
        
        self._progress.files_scanned += 1
        
        # Check if file is a video
        if not self.generator.is_video_file(name):
            return
        
        processed_paths.add(file_path)
        
        # Check if incremental update is needed
        if self.incremental_enabled and not force:
            has_changed = await self.cache.has_changed(
                path=file_path,
                modified=modified,
                size=size,
                check_method=self.check_method,
            )
            if not has_changed:
                return
        
        # Generate STRM file
        try:
            strm_path = self.generator.generate(file_path, force=force)
            
            if strm_path:
                # Update cache
                await self.cache.upsert_file(
                    path=file_path,
                    name=name,
                    size=size,
                    modified=modified,
                    strm_path=strm_path,
                )
        except Exception as e:
            error_msg = f"Failed to process {file_path}: {e}"
            logger.warning(error_msg)
            self._progress.errors.append(error_msg)
    
    async def _cleanup_deleted(
        self,
        folder: str,
        processed_paths: Set[str],
    ) -> int:
        """
        Clean up STRM files for deleted source files.
        
        Args:
            folder: Scanned folder
            processed_paths: Set of paths that still exist
            
        Returns:
            Number of deleted files
        """
        deleted_count = 0
        
        # Get all cached files for this folder
        cached_files = await self.cache.get_all_files(folder)
        
        for cached in cached_files:
            path = cached.get("path", "")
            strm_path = cached.get("strm_path")
            
            if path and path not in processed_paths:
                # File no longer exists, delete STRM
                if strm_path:
                    if self.generator.delete_strm(strm_path):
                        deleted_count += 1
                
                # Remove from cache
                await self.cache.delete_file(path)
                logger.debug(f"Cleaned up deleted file: {path}")
        
        return deleted_count
    
    async def scan_all(self, force: bool = False) -> List[ScanProgress]:
        """
        Scan all configured source folders.
        
        Args:
            force: Force regenerate all STRM files
            
        Returns:
            List of scan progress for each folder
        """
        config = get_config()
        results = []
        
        for folder in config.paths.source:
            if self._cancelled:
                break
            
            progress = await self.scan_folder(folder, force)
            results.append(progress)
        
        return results


# Global scanner instance
_scanner: Optional[Scanner] = None


def get_scanner() -> Scanner:
    """Get the global scanner instance"""
    global _scanner
    if _scanner is None:
        _scanner = Scanner()
    return _scanner


def reset_scanner() -> None:
    """Reset the global scanner instance"""
    global _scanner
    _scanner = None
