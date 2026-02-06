"""
FastAPI Application Setup

Main application initialization with middleware, routers, and exception handlers.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from .routes import canaries, logging, alerts, meta, credentials, accounts
from .session_auth import router as session_router
from ..models import init_db
from ..logging_config import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Coalmine API")
    init_db()
    yield
    logger.info("Shutting down Coalmine API")


app = FastAPI(
    title="Coalmine API",
    description="REST API for managing canary resources and cloud security monitoring",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Register routers
# Session auth for WebUI (separate from API key auth)
app.include_router(session_router)

# API routes
app.include_router(meta.router, prefix="/api/v1", tags=["metadata"])
app.include_router(canaries.router, prefix="/api/v1", tags=["canaries"])
app.include_router(logging.router, prefix="/api/v1", tags=["logging"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(credentials.router, prefix="/api/v1", tags=["credentials"])
app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])


# =============================================================================
# WebUI Static File Serving
# =============================================================================
# The WebUI is completely segmented in the webui/ directory.
# We only serve it if the build output exists, allowing the API to run
# independently if the WebUI hasn't been built.

# Check multiple possible locations for WebUI build
_WEBUI_PATHS = [
    os.path.join(os.path.dirname(__file__), "../../webui/dist"),  # Development
    "/app/webui/dist",  # Docker container
]

WEBUI_DIST = None
for path in _WEBUI_PATHS:
    if os.path.exists(path) and os.path.isdir(path):
        WEBUI_DIST = os.path.abspath(path)
        break

if WEBUI_DIST:
    logger.info(f"WebUI enabled, serving from: {WEBUI_DIST}")
    
    # Serve static assets (JS, CSS, images)
    assets_path = os.path.join(WEBUI_DIST, "assets")
    if os.path.exists(assets_path):
        app.mount("/ui/assets", StaticFiles(directory=assets_path), name="webui-assets")
    
    # SPA catch-all route - serves index.html for all /ui/* paths
    # This enables client-side routing in the React app
    @app.get("/ui/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the WebUI SPA for all /ui routes."""
        index_path = os.path.join(WEBUI_DIST, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse({"error": "WebUI not found"}, status_code=404)
    
    @app.get("/ui")
    async def serve_spa_root():
        """Serve WebUI at /ui root."""
        index_path = os.path.join(WEBUI_DIST, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse({"error": "WebUI not found"}, status_code=404)
else:
    logger.info("WebUI not available (webui/dist not found)")

