"""Authentication module for OpenList2STRM"""

import hashlib
import secrets
import time
import logging
from typing import Optional
from functools import wraps

from fastapi import Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_config

logger = logging.getLogger(__name__)

# Session storage (in-memory, resets on restart)
_sessions: dict[str, dict] = {}

# Security
security = HTTPBearer(auto_error=False)

# Session configuration
SESSION_COOKIE_NAME = "openlist2strm_session"
SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def hash_password(password: str) -> str:
    """Hash password using SHA256 with salt"""
    # Using simple hash for portability (no bcrypt dependency)
    salt = "openlist2strm_salt_v1"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == hashed


def generate_session_id() -> str:
    """Generate a secure session ID"""
    return secrets.token_urlsafe(32)


def generate_api_token() -> str:
    """Generate a secure API token"""
    return secrets.token_urlsafe(48)


def create_session(username: str) -> str:
    """Create a new session for user"""
    session_id = generate_session_id()
    _sessions[session_id] = {
        "username": username,
        "created_at": time.time(),
        "last_access": time.time(),
    }
    logger.info(f"Session created for user: {username}")
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """Get session data"""
    if session_id not in _sessions:
        return None
    
    session = _sessions[session_id]
    
    # Check if session expired
    if time.time() - session["created_at"] > SESSION_MAX_AGE:
        del _sessions[session_id]
        return None
    
    # Update last access time
    session["last_access"] = time.time()
    return session


def delete_session(session_id: str):
    """Delete a session"""
    if session_id in _sessions:
        del _sessions[session_id]


def is_auth_enabled() -> bool:
    """Check if authentication is enabled"""
    config = get_config()
    return config.web.auth.enabled


def get_session_from_request(request: Request) -> Optional[dict]:
    """Extract and validate session from request"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    return get_session(session_id)


def verify_api_token(token: str) -> bool:
    """Verify API token"""
    config = get_config()
    if not config.web.auth.api_token:
        return False
    return token == config.web.auth.api_token


def generate_api_token() -> str:
    """Generate a new random API token"""
    return secrets.token_urlsafe(48)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[str]:
    """
    Get current authenticated user from session or API token.
    Returns username if authenticated, None otherwise.
    """
    config = get_config()
    
    # If auth is disabled, return default user
    if not config.web.auth.enabled:
        return "admin"
    
    # Check API token first (for API calls)
    if credentials and credentials.credentials:
        if verify_api_token(credentials.credentials):
            return "api_user"
    
    # Check session
    session = get_session_from_request(request)
    if session:
        return session["username"]
    
    return None


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Dependency that requires authentication.
    Raises 401 if not authenticated.
    """
    user = await get_current_user(request, credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def require_auth_redirect(request: Request) -> Optional[RedirectResponse]:
    """
    Check authentication for web pages.
    Returns redirect response if not authenticated, None if OK.
    """
    config = get_config()
    
    if not config.web.auth.enabled:
        return None
    
    session = get_session_from_request(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return None


def login_user(username: str, password: str) -> Optional[str]:
    """
    Attempt to log in a user.
    Returns session_id if successful, None otherwise.
    """
    config = get_config()
    
    # Check username
    if username != config.web.auth.username:
        logger.warning(f"Login failed: invalid username '{username}'")
        return None
    
    # Check password
    stored_password = config.web.auth.password
    
    # If password is empty, it means first-time setup needed
    if not stored_password:
        logger.warning("Login failed: password not configured")
        return None
    
    # Check if password matches (support both plain and hashed)
    if password == stored_password or verify_password(password, stored_password):
        return create_session(username)
    
    logger.warning(f"Login failed: invalid password for user '{username}'")
    return None


# Exempt paths that don't require authentication
EXEMPT_PATHS = [
    "/api/health",
    "/login",
    "/api/auth/login",
    "/static",
    "/favicon.ico",
]


def is_exempt_path(path: str) -> bool:
    """Check if path is exempt from authentication"""
    for exempt in EXEMPT_PATHS:
        if path.startswith(exempt):
            return True
    return False
