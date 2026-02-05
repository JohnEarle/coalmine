"""
FastAPI Application Setup

Main application initialization with middleware, routers, and exception handlers.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from .routes import canaries, environments, logging, alerts
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
app.include_router(canaries.router, prefix="/api/v1", tags=["canaries"])
app.include_router(environments.router, prefix="/api/v1", tags=["environments"])
app.include_router(logging.router, prefix="/api/v1", tags=["logging"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
