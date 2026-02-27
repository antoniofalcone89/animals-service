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
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.challenge import router as challenge_router
from app.api.v1.endpoints.leaderboard import router as leaderboard_router
from app.api.v1.endpoints.levels import router as levels_router
from app.api.v1.endpoints.quiz import router as quiz_router
from app.api.v1.endpoints.users import router as users_router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Animal Quiz Academy API",
    description="Backend API for Animal Quiz Academy — an educational quiz app about animals with gamified progression.",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
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
    allow_methods=["GET", "POST", "PATCH"],
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


# API key authentication (for legacy /animals endpoints only)
# New endpoints use Bearer auth via FastAPI dependencies.
_BEARER_AUTH_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/challenge",
    "/api/v1/levels",
    "/api/v1/quiz",
    "/api/v1/users",
    "/api/v1/leaderboard",
)


@app.middleware("http")
async def api_key_auth(request: Request, call_next) -> Response:
    """Validate API key for legacy animal endpoints."""
    # Exempt paths that don't need API key auth
    exempt_paths = {"/api/v1/health", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json"}
    if request.url.path in exempt_paths or request.url.path.startswith("/static"):
        return await call_next(request)

    # New endpoints use Bearer auth (handled by FastAPI Depends), skip API key check
    if any(request.url.path.startswith(prefix) for prefix in _BEARER_AUTH_PREFIXES):
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
app.include_router(auth_router, prefix="/api/v1", tags=["Auth"])
app.include_router(challenge_router, prefix="/api/v1", tags=["Challenge"])
app.include_router(levels_router, prefix="/api/v1", tags=["Levels"])
app.include_router(quiz_router, prefix="/api/v1", tags=["Quiz"])
app.include_router(users_router, prefix="/api/v1", tags=["Users"])
app.include_router(leaderboard_router, prefix="/api/v1", tags=["Leaderboard"])

logger.info("Animal Quiz Academy API started (debug=%s)", settings.DEBUG)
