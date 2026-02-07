"""
FastAPI Application Setup

Main application initialization with middleware, routers, and exception handlers.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
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
    
    # Seed admin user if needed
    try:
        from ..auth.seed import seed_admin_if_needed
        await seed_admin_if_needed()
    except Exception as e:
        logger.warning(f"Admin seeding skipped: {e}")
    
    yield
    logger.info("Shutting down Coalmine API")


app = FastAPI(
    title="Coalmine API",
    description="REST API for managing canary resources and cloud security monitoring",
    version="1.0.0",
    lifespan=lifespan
)

# Session middleware for OIDC state storage
# Secret loaded from auth config (single source of truth)
def _get_session_secret() -> str:
    try:
        from ..auth import get_auth_config
        return get_auth_config().session.secret_key
    except Exception:
        return os.getenv("SECRET_KEY", "coalmine-dev-secret-change-in-production")
app.add_middleware(SessionMiddleware, secret_key=_get_session_secret())

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
# Auth status/logout endpoints
app.include_router(session_router)

# OIDC routes (if enabled in config)
try:
    from ..auth.oidc import router as oidc_router, is_oidc_enabled
    app.include_router(oidc_router)
    if is_oidc_enabled():
        logger.info("OIDC authentication enabled")
except Exception as e:
    logger.debug(f"OIDC router not loaded: {e}")

# API routes
app.include_router(meta.router, prefix="/api/v1", tags=["metadata"])
app.include_router(canaries.router, prefix="/api/v1", tags=["canaries"])
app.include_router(logging.router, prefix="/api/v1", tags=["logging"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(credentials.router, prefix="/api/v1", tags=["credentials"])
app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])

# Task log routes
from .routes import tasks
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])

# API key management routes
from .routes import api_keys
app.include_router(api_keys.router, prefix="/api/v1", tags=["api-keys"])

# Admin routes (sessions, RBAC)
from .routes import admin
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])

# User management routes (list users)
from .routes import users
app.include_router(users.router, prefix="/api/v1", tags=["users"])

# fastapi-users authentication routes
try:
    from ..auth.users import fastapi_users, jwt_backend, cookie_backend
    from ..models import User
    from .schemas.users import UserRead, UserCreate, UserUpdate
    
    # Auth routes (login/logout)
    app.include_router(
        fastapi_users.get_auth_router(jwt_backend),
        prefix="/auth/jwt",
        tags=["auth"]
    )
    app.include_router(
        fastapi_users.get_auth_router(cookie_backend),
        prefix="/auth/cookie",
        tags=["auth"]
    )
    
    # User management routes (GET/PATCH/DELETE via fastapi-users)
    # Authorization: requires is_superuser=True
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/v1/users",
        tags=["users"]
    )
    
    # Registration: open when zero users exist, superuser-only otherwise
    from .routes._register_guard import router as guarded_register_router
    app.include_router(guarded_register_router, prefix="/auth", tags=["auth"])
    
    logger.info("fastapi-users authentication enabled")
    
except Exception as e:
    logger.warning(f"fastapi-users not loaded: {e}")


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

