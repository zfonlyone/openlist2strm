"""STRM file generator module"""

import os
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.config import get_config

logger = logging.getLogger(__name__)


class StrmGenerator:
    """
    STRM file generator.
    
    Generates STRM files that contain URLs pointing to media files
    in OpenList for playback in media players like Emby/Jellyfin.
    """
    
    # Supported video extensions
    DEFAULT_EXTENSIONS = {
        ".mp4", ".mkv", ".avi", ".ts", ".wmv",
        ".rmvb", ".mov", ".flv", ".m2ts", ".webm",
        ".mpg", ".mpeg", ".m4v", ".3gp", ".vob",
    }
    
    def __init__(
        self,
        output_path: Optional[str] = None,
        path_mapping: Optional[dict] = None,
        extensions: Optional[list] = None,
        url_encode: Optional[bool] = None,
        keep_structure: Optional[bool] = None,
    ):
        """
        Initialize STRM generator.
        
        Note: If any arguments are not provided, they will be 
        fetched dynamically from the global config.
        """
        self._output_path_override = output_path
        self._path_mapping_override = path_mapping
        self._extensions_override = extensions
        self._url_encode_override = url_encode
        self._keep_structure_override = keep_structure
        
        # Statistics
        self._files_created = 0
        self._files_updated = 0
        self._files_skipped = 0
        
        logger.info("STRM generator initialized")

    @property
    def output_path(self) -> Path:
        return Path(self._output_path_override or get_config().paths.output)

    @property
    def path_mapping(self) -> dict:
        return self._path_mapping_override or get_config().path_mapping

    @property
    def url_encode(self) -> bool:
        if self._url_encode_override is not None:
            return self._url_encode_override
        return get_config().strm.url_encode

    @property
    def keep_structure(self) -> bool:
        if self._keep_structure_override is not None:
            return self._keep_structure_override
        return get_config().strm.keep_structure

    @property
    def extensions(self) -> set:
        if self._extensions_override:
            return set(ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in self._extensions_override)
        return set(ext.lower() for ext in get_config().strm.extensions)

    
    def is_video_file(self, filename: str) -> bool:
        """
        Check if a file is a supported video file.
        
        Args:
            filename: File name to check
            
        Returns:
            True if it's a video file
        """
        ext = Path(filename).suffix.lower()
        return ext in self.extensions
    
    def get_strm_path(self, source_path: str) -> Path:
        """
        Get the output STRM file path for a source file.
        
        Args:
            source_path: Source file path in OpenList
            
        Returns:
            Path object for the STRM file
        """
        # Remove leading slash and change extension to .strm
        relative_path = source_path.lstrip("/")
        strm_name = Path(relative_path).with_suffix(".strm")
        
        if self.keep_structure:
            return self.output_path / strm_name
        else:
            # Flatten structure - just use filename
            return self.output_path / strm_name.name
    
    def get_url(self, source_path: str) -> str:
        """
        Generate the URL to embed in the STRM file.
        
        Args:
            source_path: Source file path in OpenList
            
        Returns:
            URL string for the media file
        """
        # Find matching path mapping
        url_prefix = None
        matched_prefix = ""
        
        for path_prefix, url in self.path_mapping.items():
            if source_path.startswith(path_prefix):
                if len(path_prefix) > len(matched_prefix):
                    matched_prefix = path_prefix
                    url_prefix = url
        
        if url_prefix:
            # Replace the path prefix with URL prefix
            relative = source_path[len(matched_prefix):]
            if self.url_encode:
                relative = quote(relative, safe="/")
            url = url_prefix.rstrip("/") + relative
        else:
            # No mapping found, use path as-is
            if self.url_encode:
                url = quote(source_path, safe="/")
            else:
                url = source_path
        
        return url
    
    def generate(
        self,
        source_path: str,
        force: bool = False,
    ) -> Optional[str]:
        """
        Generate a STRM file for a source video file.
        
        Args:
            source_path: Source file path in OpenList
            force: Force overwrite if file exists
            
        Returns:
            Path to the created STRM file, or None if skipped
        """
        if not self.is_video_file(source_path):
            logger.debug(f"Skipping non-video file: {source_path}")
            self._files_skipped += 1
            return None
        
        strm_path = self.get_strm_path(source_path)
        url = self.get_url(source_path)
        
        # Check if file exists
        if strm_path.exists() and not force:
            # Check if content is the same
            try:
                existing_content = strm_path.read_text(encoding="utf-8").strip()
                if existing_content == url:
                    logger.debug(f"STRM unchanged: {strm_path}")
                    self._files_skipped += 1
                    return None
            except Exception:
                pass
            
            # Content is different, update
            self._files_updated += 1
        else:
            self._files_created += 1
        
        # Create parent directories
        strm_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write STRM file
        try:
            strm_path.write_text(url, encoding="utf-8")
            logger.debug(f"Generated STRM: {strm_path}")
            return str(strm_path)
        except Exception as e:
            logger.error(f"Failed to write STRM file {strm_path}: {e}")
            return None
    
    def delete_strm(self, strm_path: str) -> bool:
        """
        Delete a STRM file.
        
        Args:
            strm_path: Path to STRM file to delete
            
        Returns:
            True if deleted successfully
        """
        path = Path(strm_path)
        if path.exists():
            try:
                path.unlink()
                logger.debug(f"Deleted STRM: {strm_path}")
                
                # Clean up empty directories
                self._cleanup_empty_dirs(path.parent)
                return True
            except Exception as e:
                logger.error(f"Failed to delete STRM file {strm_path}: {e}")
        return False
    
    def _cleanup_empty_dirs(self, directory: Path) -> None:
        """Remove empty directories up to output path"""
        while directory != self.output_path and directory.is_dir():
            try:
                if not any(directory.iterdir()):
                    directory.rmdir()
                    logger.debug(f"Removed empty directory: {directory}")
                    directory = directory.parent
                else:
                    break
            except Exception:
                break
    
    @property
    def stats(self) -> dict:
        """Get generation statistics"""
        return {
            "files_created": self._files_created,
            "files_updated": self._files_updated,
            "files_skipped": self._files_skipped,
            "total_processed": self._files_created + self._files_updated + self._files_skipped,
        }
    
    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self._files_created = 0
        self._files_updated = 0
        self._files_skipped = 0
    
    def get_existing_strm_files(self) -> list:
        """
        Get all existing STRM files in output directory.
        
        Returns:
            List of STRM file paths
        """
        strm_files = []
        if self.output_path.exists():
            for strm_file in self.output_path.rglob("*.strm"):
                strm_files.append(str(strm_file))
        return strm_files


# Global generator instance
_generator: Optional[StrmGenerator] = None


def get_strm_generator() -> StrmGenerator:
    """Get the global STRM generator instance"""
    global _generator
    if _generator is None:
        _generator = StrmGenerator()
    return _generator


def reset_strm_generator() -> None:
    """Reset the global STRM generator instance"""
    global _generator
    _generator = None
