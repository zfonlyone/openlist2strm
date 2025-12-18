"""OpenList API client module"""

import logging
import httpx
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, quote

from app.config import get_config
from .qos import get_qos_limiter

logger = logging.getLogger(__name__)


class OpenListError(Exception):
    """OpenList API error"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"OpenList Error [{code}]: {message}")


class OpenListClient:
    """
    OpenList API client with rate limiting support.
    
    Supports:
    - File listing (fs/list)
    - File info (fs/get)
    - Directory traversal
    - Authentication via token
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize OpenList client.
        
        Args:
            host: OpenList server URL
            token: API token for authentication
            timeout: Request timeout in seconds
        """
        config = get_config()
        self.host = host or config.openlist.host
        self.token = token or config.openlist.token
        self.timeout = timeout or config.openlist.timeout
        
        # Remove trailing slash from host
        self.host = self.host.rstrip("/")
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"OpenList client initialized: {self.host}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = self.token
        return headers
    
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make POST request to OpenList API.
        
        Args:
            endpoint: API endpoint (e.g., /api/fs/list)
            data: Request body data
            
        Returns:
            Response data
            
        Raises:
            OpenListError: If API returns an error
        """
        url = urljoin(self.host + "/", endpoint.lstrip("/"))
        
        qos = get_qos_limiter()
        async with qos.acquire():
            client = await self._get_client()
            try:
                response = await client.post(
                    url,
                    json=data,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                result = response.json()
                
                # Check for API errors
                if result.get("code") != 200:
                    raise OpenListError(
                        result.get("code", -1),
                        result.get("message", "Unknown error"),
                    )
                
                return result
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e}")
                raise OpenListError(e.response.status_code, str(e))
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise OpenListError(-1, str(e))
    
    async def list_files(
        self,
        path: str,
        page: int = 1,
        per_page: int = 0,
        password: str = "",
        refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        List files in a directory.
        
        Args:
            path: Directory path in OpenList
            page: Page number (1-indexed)
            per_page: Items per page (0 for all)
            password: Directory password if protected
            refresh: Force refresh from storage
            
        Returns:
            Dictionary containing:
            - content: List of file/folder items
            - total: Total number of items
            - provider: Storage provider name
        """
        logger.debug(f"Listing files: {path}")
        
        response = await self._post("/api/fs/list", {
            "path": path,
            "page": page,
            "per_page": per_page,
            "password": password,
            "refresh": refresh,
        })
        
        data = response.get("data", {})
        content = data.get("content") or []
        
        logger.debug(f"Found {len(content)} items in {path}")
        return data
    
    async def get_file(
        self,
        path: str,
        password: str = "",
    ) -> Dict[str, Any]:
        """
        Get file or directory information.
        
        Args:
            path: File/directory path in OpenList
            password: Password if protected
            
        Returns:
            Dictionary containing file info:
            - name: File name
            - size: File size in bytes
            - is_dir: Whether it's a directory
            - modified: Modification time
            - raw_url: Direct download URL
            - provider: Storage provider name
        """
        logger.debug(f"Getting file info: {path}")
        
        response = await self._post("/api/fs/get", {
            "path": path,
            "password": password,
        })
        
        return response.get("data", {})
    
    async def get_download_url(self, path: str) -> str:
        """
        Get direct download URL for a file.
        
        Args:
            path: File path in OpenList
            
        Returns:
            Direct download URL
        """
        file_info = await self.get_file(path)
        raw_url = file_info.get("raw_url", "")
        
        if raw_url:
            return raw_url
        
        # Fallback to constructed URL
        encoded_path = quote(path, safe="/")
        return f"{self.host}/d{encoded_path}"
    
    async def list_all_files(
        self,
        path: str,
        password: str = "",
        refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List all files in a directory (handling pagination).
        
        Args:
            path: Directory path
            password: Directory password
            refresh: Force refresh
            
        Returns:
            List of all file items
        """
        all_items = []
        page = 1
        per_page = 100
        
        while True:
            data = await self.list_files(
                path=path,
                page=page,
                per_page=per_page,
                password=password,
                refresh=refresh,
            )
            
            content = data.get("content") or []
            all_items.extend(content)
            
            total = data.get("total", len(content))
            if len(all_items) >= total or not content:
                break
            
            page += 1
        
        return all_items
    
    async def walk(
        self,
        path: str,
        password: str = "",
        depth: int = -1,
    ):
        """
        Recursively walk through directories.
        
        Args:
            path: Starting directory path
            password: Directory password
            depth: Maximum depth (-1 for unlimited)
            
        Yields:
            Tuple of (current_path, dirs, files)
        """
        if depth == 0:
            return
        
        try:
            items = await self.list_all_files(path=path, password=password)
        except OpenListError as e:
            logger.warning(f"Failed to list {path}: {e}")
            return
        
        dirs = []
        files = []
        
        for item in items:
            if item.get("is_dir"):
                dirs.append(item)
            else:
                files.append(item)
        
        yield path, dirs, files
        
        # Recurse into subdirectories
        for dir_item in dirs:
            dir_name = dir_item.get("name", "")
            sub_path = f"{path.rstrip('/')}/{dir_name}"
            
            async for result in self.walk(sub_path, password, depth - 1 if depth > 0 else -1):
                yield result


# Global client instance
_client: Optional[OpenListClient] = None


def get_openlist_client() -> OpenListClient:
    """Get the global OpenList client instance"""
    global _client
    if _client is None:
        _client = OpenListClient()
    return _client


async def close_openlist_client() -> None:
    """Close the global OpenList client"""
    global _client
    if _client:
        await _client.close()
        _client = None
