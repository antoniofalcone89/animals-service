"""FastAPI application initialization and configuration."""

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.endpoints.animals import limiter, router as animals_router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Animal API",
    description="REST API providing animal information including name, image, and rarity level.",
    version="1.0.0",
)

# --- Middleware ---

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Request logging
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Log every incoming request and its duration."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# API key authentication
@app.middleware("http")
async def api_key_auth(request: Request, call_next) -> Response:
    """Validate API key for protected endpoints."""
    # Allow health check and docs without auth
    exempt_paths = {"/api/v1/health", "/docs", "/redoc", "/openapi.json"}
    if request.url.path in exempt_paths or request.url.path.startswith("/static"):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    if api_key != settings.API_KEY:
        logger.warning("Unauthorized request from %s", request.client.host if request.client else "unknown")
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Unauthorized", "detail": "Invalid or missing API key"},
        )
    return await call_next(request)


# Static files (images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routes
app.include_router(animals_router, prefix="/api/v1", tags=["animals"])

logger.info("Animal API started (debug=%s)", settings.DEBUG)
