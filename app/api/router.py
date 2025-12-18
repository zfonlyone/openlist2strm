"""API router configuration"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .scan import router as scan_router
from .folders import router as folders_router
from .tasks import router as tasks_router
from .settings import router as settings_router
from .auth import (
    require_auth, 
    login_user, 
    delete_session, 
    generate_api_token,
    hash_password,
    SESSION_COOKIE_NAME,
    get_session_from_request,
)
from app.config import get_config

api_router = APIRouter(prefix="/api")


# Auth models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str


# Auth endpoints (no auth required)
@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: Request, data: LoginRequest):
    """Login endpoint"""
    session_id = login_user(data.username, data.password)
    
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    response = JSONResponse(
        content={"success": True, "message": "Login successful"}
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days
        samesite="lax",
    )
    return response


@api_router.post("/auth/logout")
async def logout(request: Request):
    """Logout endpoint"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        delete_session(session_id)
    
    response = JSONResponse(content={"success": True, "message": "Logged out"})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@api_router.get("/auth/status")
async def auth_status(request: Request):
    """Check authentication status"""
    config = get_config()
    session = get_session_from_request(request)
    
    return {
        "authenticated": session is not None or not config.web.auth.enabled,
        "auth_enabled": config.web.auth.enabled,
        "username": session["username"] if session else None,
    }


@api_router.post("/auth/generate-token", dependencies=[Depends(require_auth)])
async def generate_new_token():
    """Generate a new API token"""
    token = generate_api_token()
    return {"token": token, "message": "Save this token - it won't be shown again!"}


# Protected sub-routers with auth dependency
protected_router = APIRouter(dependencies=[Depends(require_auth)])
protected_router.include_router(scan_router, tags=["scan"])
protected_router.include_router(folders_router, tags=["folders"])
protected_router.include_router(tasks_router, tags=["tasks"])
protected_router.include_router(settings_router, tags=["settings"])

api_router.include_router(protected_router)


# Health check (no auth required)
@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "openlist2strm"}


# Status endpoint (protected)
@api_router.get("/status", dependencies=[Depends(require_auth)])
async def get_status():
    """Get overall system status"""
    from app.core.cache import get_cache_manager
    from app.core.scanner import get_scanner
    from app.scheduler import get_scheduler_manager
    
    cache = get_cache_manager()
    scanner = get_scanner()
    scheduler = get_scheduler_manager()
    
    # Get cache stats
    stats = await cache.get_stats()
    last_scan = await cache.get_last_scan()
    
    return {
        "scanner": {
            "running": scanner.is_running,
            "progress": scanner.progress.to_dict() if scanner.is_running else None,
        },
        "scheduler": scheduler.status,
        "cache": stats,
        "last_scan": last_scan,
    }

