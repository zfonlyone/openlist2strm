"""SQLite cache manager for incremental updates"""

import asyncio
import aiosqlite
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path("/data/cache.db")


class CacheManager:
    """
    SQLite-based cache manager for tracking file changes
    and enabling incremental updates.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize cache manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or DB_PATH
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
    
    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create database connection"""
        if self._db is None:
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._db = await aiosqlite.connect(str(self.db_path))
            self._db.row_factory = aiosqlite.Row
            await self._init_tables()
            
            logger.info(f"Database connected: {self.db_path}")
        
        return self._db
    
    async def _init_tables(self) -> None:
        """Initialize database tables"""
        db = await self._get_db()
        
        # File cache table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                modified TEXT,
                is_dir INTEGER DEFAULT 0,
                strm_path TEXT,
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_cache_path ON file_cache(path)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_cache_strm ON file_cache(strm_path)
        """)
        
        # Scan history table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder TEXT NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                files_scanned INTEGER DEFAULT 0,
                files_created INTEGER DEFAULT 0,
                files_updated INTEGER DEFAULT 0,
                files_deleted INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Folder config table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS folder_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                enabled INTEGER DEFAULT 1,
                last_scan TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()
        logger.debug("Database tables initialized")
    
    async def close(self) -> None:
        """Close database connection"""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed")
    
    # ==================== File Cache Operations ====================
    
    async def get_file(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached file info by path.
        
        Args:
            path: File path in OpenList
            
        Returns:
            File info dict or None if not found
        """
        db = await self._get_db()
        async with self._lock:
            cursor = await db.execute(
                "SELECT * FROM file_cache WHERE path = ?",
                (path,)
            )
            row = await cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    async def upsert_file(
        self,
        path: str,
        name: str,
        size: int = 0,
        modified: Optional[str] = None,
        is_dir: bool = False,
        strm_path: Optional[str] = None,
    ) -> None:
        """
        Insert or update file cache entry.
        
        Args:
            path: File path in OpenList
            name: File name
            size: File size in bytes
            modified: Modification time string
            is_dir: Whether it's a directory
            strm_path: Generated STRM file path
        """
        db = await self._get_db()
        async with self._lock:
            await db.execute("""
                INSERT INTO file_cache (path, name, size, modified, is_dir, strm_path, last_sync)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    name = excluded.name,
                    size = excluded.size,
                    modified = excluded.modified,
                    is_dir = excluded.is_dir,
                    strm_path = excluded.strm_path,
                    last_sync = CURRENT_TIMESTAMP
            """, (path, name, size, modified, int(is_dir), strm_path))
            await db.commit()
    
    async def has_changed(
        self,
        path: str,
        modified: Optional[str] = None,
        size: Optional[int] = None,
        check_method: str = "mtime",
    ) -> bool:
        """
        Check if a file has changed since last sync.
        
        Args:
            path: File path
            modified: Current modification time
            size: Current file size
            check_method: Check method (mtime, size, both)
            
        Returns:
            True if file has changed or not in cache
        """
        cached = await self.get_file(path)
        
        if cached is None:
            return True  # New file
        
        if check_method == "mtime" or check_method == "both":
            if modified and cached.get("modified") != modified:
                return True
        
        if check_method == "size" or check_method == "both":
            if size is not None and cached.get("size") != size:
                return True
        
        return False
    
    async def delete_file(self, path: str) -> None:
        """Delete file from cache"""
        db = await self._get_db()
        async with self._lock:
            await db.execute("DELETE FROM file_cache WHERE path = ?", (path,))
            await db.commit()
    
    async def get_all_files(self, folder: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all cached files.
        
        Args:
            folder: Optional folder prefix to filter
            
        Returns:
            List of file info dicts
        """
        db = await self._get_db()
        async with self._lock:
            if folder:
                cursor = await db.execute(
                    "SELECT * FROM file_cache WHERE path LIKE ? AND is_dir = 0",
                    (f"{folder}%",)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM file_cache WHERE is_dir = 0"
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        db = await self._get_db()
        async with self._lock:
            # Total files
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM file_cache WHERE is_dir = 0"
            )
            row = await cursor.fetchone()
            total_files = row["count"] if row else 0
            
            # Total directories
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM file_cache WHERE is_dir = 1"
            )
            row = await cursor.fetchone()
            total_dirs = row["count"] if row else 0
            
            # Total STRM files
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM file_cache WHERE strm_path IS NOT NULL"
            )
            row = await cursor.fetchone()
            total_strm = row["count"] if row else 0
            
            # Total size
            cursor = await db.execute(
                "SELECT SUM(size) as total FROM file_cache WHERE is_dir = 0"
            )
            row = await cursor.fetchone()
            total_size = row["total"] if row and row["total"] else 0
            
            return {
                "total_files": total_files,
                "total_directories": total_dirs,
                "total_strm": total_strm,
                "total_size": total_size,
                "total_size_human": self._format_size(total_size),
            }
    
    # ==================== Scan History Operations ====================
    
    async def start_scan(self, folder: str) -> int:
        """
        Record scan start.
        
        Args:
            folder: Folder being scanned
            
        Returns:
            Scan ID
        """
        db = await self._get_db()
        async with self._lock:
            cursor = await db.execute("""
                INSERT INTO scan_history (folder, start_time, status)
                VALUES (?, CURRENT_TIMESTAMP, 'running')
            """, (folder,))
            await db.commit()
            return cursor.lastrowid
    
    async def finish_scan(
        self,
        scan_id: int,
        files_scanned: int = 0,
        files_created: int = 0,
        files_updated: int = 0,
        files_deleted: int = 0,
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> None:
        """
        Record scan completion.
        
        Args:
            scan_id: Scan ID from start_scan
            files_scanned: Number of files scanned
            files_created: Number of new STRM files created
            files_updated: Number of STRM files updated
            files_deleted: Number of STRM files deleted
            status: Final status (completed, failed, cancelled)
            error_message: Error message if failed
        """
        db = await self._get_db()
        async with self._lock:
            await db.execute("""
                UPDATE scan_history SET
                    end_time = CURRENT_TIMESTAMP,
                    files_scanned = ?,
                    files_created = ?,
                    files_updated = ?,
                    files_deleted = ?,
                    status = ?,
                    error_message = ?
                WHERE id = ?
            """, (files_scanned, files_created, files_updated, files_deleted, status, error_message, scan_id))
            await db.commit()
    
    async def get_scan_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent scan history.
        
        Args:
            limit: Maximum number of records
            
        Returns:
            List of scan records
        """
        db = await self._get_db()
        async with self._lock:
            cursor = await db.execute("""
                SELECT * FROM scan_history
                ORDER BY start_time DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_last_scan(self, folder: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the last successful scan info.
        
        Args:
            folder: Optional folder filter
            
        Returns:
            Last scan record or None
        """
        db = await self._get_db()
        async with self._lock:
            if folder:
                cursor = await db.execute("""
                    SELECT * FROM scan_history
                    WHERE folder = ? AND status = 'completed'
                    ORDER BY end_time DESC
                    LIMIT 1
                """, (folder,))
            else:
                cursor = await db.execute("""
                    SELECT * FROM scan_history
                    WHERE status = 'completed'
                    ORDER BY end_time DESC
                    LIMIT 1
                """)
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Folder Config Operations ====================
    
    async def get_folders(self) -> List[Dict[str, Any]]:
        """Get all monitored folders"""
        db = await self._get_db()
        async with self._lock:
            cursor = await db.execute("SELECT * FROM folder_config ORDER BY path")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def add_folder(self, path: str, enabled: bool = True) -> None:
        """Add a folder to monitor"""
        db = await self._get_db()
        async with self._lock:
            await db.execute("""
                INSERT INTO folder_config (path, enabled)
                VALUES (?, ?)
                ON CONFLICT(path) DO UPDATE SET enabled = excluded.enabled
            """, (path, int(enabled)))
            await db.commit()
    
    async def remove_folder(self, path: str) -> None:
        """Remove a folder from monitoring"""
        db = await self._get_db()
        async with self._lock:
            await db.execute("DELETE FROM folder_config WHERE path = ?", (path,))
            await db.commit()
    
    async def set_folder_enabled(self, path: str, enabled: bool) -> None:
        """Enable or disable a folder"""
        db = await self._get_db()
        async with self._lock:
            await db.execute(
                "UPDATE folder_config SET enabled = ? WHERE path = ?",
                (int(enabled), path)
            )
            await db.commit()
    
    async def update_folder_scan_time(self, path: str) -> None:
        """Update last scan time for a folder"""
        db = await self._get_db()
        async with self._lock:
            await db.execute(
                "UPDATE folder_config SET last_scan = CURRENT_TIMESTAMP WHERE path = ?",
                (path,)
            )
            await db.commit()
    
    # ==================== Utility Methods ====================
    
    @staticmethod
    def _format_size(size: int) -> str:
        """Format size in human-readable format"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


async def close_cache_manager() -> None:
    """Close the global cache manager"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.close()
        _cache_manager = None
