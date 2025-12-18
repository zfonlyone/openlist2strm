"""
OpenList2STRM - Main Application Entry Point

A lightweight tool to convert OpenList files to STRM format
with web management interface and Telegram bot support.
"""

import asyncio
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_config
from app.api import api_router
from app.scheduler import get_scheduler_manager
from app.telegram import start_telegram_bot, stop_telegram_bot
from app.core.cache import get_cache_manager, close_cache_manager
from app.core.openlist import close_openlist_client

# Configure logging
def setup_logging():
    """Configure application logging"""
    config = get_config()
    
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    
    # Log format
    if config.logging.colorize:
        format_str = "\033[90m%(asctime)s\033[0m | %(levelname)s | \033[36m%(name)s\033[0m | %(message)s"
    else:
        format_str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    logger.info("=" * 50)
    logger.info("OpenList2STRM Starting...")
    logger.info("=" * 50)
    
    config = get_config()
    
    # Initialize cache
    cache = get_cache_manager()
    await cache._get_db()  # Initialize database
    logger.info("Cache initialized")
    
    # Initialize folders from config
    for folder in config.paths.source:
        await cache.add_folder(folder)
    logger.info(f"Monitoring {len(config.paths.source)} folders")
    
    # Start scheduler
    scheduler = get_scheduler_manager()
    await scheduler.start()
    
    # Start Telegram bot
    if config.telegram.enabled:
        await start_telegram_bot()
        
        # Set up notification callbacks
        from app.telegram import get_telegram_bot
        bot = get_telegram_bot()
        scheduler.set_on_complete(bot.notify_scan_complete)
        scheduler.set_on_error(bot.notify_error)
    
    logger.info("OpenList2STRM Ready!")
    logger.info(f"Web interface: http://0.0.0.0:{config.web.port}")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down...")
    
    await scheduler.stop()
    await stop_telegram_bot()
    await close_openlist_client()
    await close_cache_manager()
    
    logger.info("Goodbye!")


# Create FastAPI application
app = FastAPI(
    title="OpenList2STRM",
    description="轻量级 OpenList 到 STRM 文件转换工具",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_path = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Templates
templates_path = Path(__file__).parent / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Include API router
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico")
async def favicon():
    """Return empty favicon to prevent 404"""
    return {"status": "ok"}


# Development server
if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=config.web.port,
        reload=True,
        log_level="info",
    )
