"""Emby integration for library refresh notifications"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_config

logger = logging.getLogger(__name__)


class EmbyClient:
    """
    Client for interacting with Emby Media Server API.
    
    Used to trigger library scans after STRM file generation.
    """
    
    def __init__(self, host: str = "", api_key: str = ""):
        """Initialize Emby client"""
        config = get_config()
        self._host = host or config.emby.host
        self._api_key = api_key or config.emby.api_key
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "X-Emby-Token": self._api_key,
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _build_url(self, endpoint: str) -> str:
        """Build full API URL"""
        host = self._host.rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{host}/{endpoint}"
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Emby server.
        
        Returns:
            Dict with connection status and server info
        """
        if not self._host or not self._api_key:
            return {
                "success": False,
                "error": "Emby host or API key not configured",
            }
        
        try:
            client = await self._get_client()
            response = await client.get(self._build_url("/System/Info"))
            response.raise_for_status()
            
            data = response.json()
            return {
                "success": True,
                "server_name": data.get("ServerName", "Unknown"),
                "version": data.get("Version", "Unknown"),
                "id": data.get("Id", ""),
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Emby connection failed: HTTP {e.response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            logger.error(f"Emby connection failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def get_libraries(self) -> List[Dict[str, Any]]:
        """
        Get list of media libraries.
        
        Returns:
            List of library info dicts
        """
        try:
            client = await self._get_client()
            response = await client.get(self._build_url("/Library/VirtualFolders"))
            response.raise_for_status()
            
            libraries = []
            for lib in response.json():
                libraries.append({
                    "id": lib.get("ItemId", ""),
                    "name": lib.get("Name", "Unknown"),
                    "type": lib.get("CollectionType", ""),
                    "locations": lib.get("Locations", []),
                })
            
            return libraries
        except Exception as e:
            logger.error(f"Failed to get libraries: {e}")
            return []
    
    async def refresh_library(self, library_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger a library scan/refresh.
        
        Args:
            library_id: Optional specific library ID. If None, refreshes all libraries.
            
        Returns:
            Dict with operation status
        """
        config = get_config()
        
        if not config.emby.enabled:
            logger.debug("Emby notifications disabled, skipping refresh")
            return {"success": True, "skipped": True, "reason": "disabled"}
        
        if not self._host or not self._api_key:
            return {
                "success": False,
                "error": "Emby host or API key not configured",
            }
        
        try:
            client = await self._get_client()
            
            # Use specified library_id or config library_id
            target_library = library_id or config.emby.library_id
            
            if target_library:
                # Refresh specific library
                url = self._build_url(f"/Items/{target_library}/Refresh")
                logger.info(f"Refreshing Emby library: {target_library}")
            else:
                # Refresh all libraries
                url = self._build_url("/Library/Refresh")
                logger.info("Refreshing all Emby libraries")
            
            response = await client.post(url)
            response.raise_for_status()
            
            return {
                "success": True,
                "library_id": target_library or "all",
                "message": "Library refresh triggered",
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Emby refresh failed: HTTP {e.response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"Emby refresh failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def notify_scan_complete(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called when STRM scan completes. Triggers Emby refresh if enabled.
        
        Args:
            results: Scan results dict
            
        Returns:
            Notification result
        """
        config = get_config()
        
        if not config.emby.enabled or not config.emby.notify_on_scan:
            return {"success": True, "skipped": True}
        
        return await self.refresh_library()


# Global client instance
_emby_client: Optional[EmbyClient] = None


def get_emby_client() -> EmbyClient:
    """Get the global Emby client instance"""
    global _emby_client
    if _emby_client is None:
        _emby_client = EmbyClient()
    return _emby_client


async def close_emby_client():
    """Close the global Emby client"""
    global _emby_client
    if _emby_client:
        await _emby_client.close()
        _emby_client = None
