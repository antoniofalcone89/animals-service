# CLAUDE.md

## Project Overview

REST API service built with FastAPI that provides animal information (name, image, rarity level 1-10). Data is served from a JSON file (`data/animals.json`).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v

# Run a single test class
pytest tests/test_animals.py::TestGetAnimalByName -v

# Docker
docker-compose up --build
```

## Architecture

```
app/
├── main.py                      # App setup, middleware (auth, CORS, logging, rate limiting)
├── config.py                    # pydantic-settings config from .env
├── models/animal.py             # Pydantic request/response models
├── api/v1/endpoints/animals.py  # Route handlers
├── services/animal_service.py   # Business logic with LRU caching
└── db/database.py               # JSON data access layer
```

- **Layered architecture**: endpoints -> services -> db. Endpoints never access db directly.
- **Routing**: All API routes live under `/api/v1/` via `APIRouter`, registered in `main.py`.
- **Data**: `data/animals.json` is the single data source. `load_animals()` is cached with `@lru_cache`.
- **Static files**: Served from `/static/`, mounted in `main.py`.

## Code Conventions

- **Python 3.9+** with modern type hints (`list[Animal]`, `int | None`).
- **Module docstrings**: Every module starts with a one-line `"""Description."""` docstring.
- **Class/function docstrings**: All public classes and functions have docstrings.
- **Logging**: Use `logging.getLogger(__name__)` per module. Log format: `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`.
- **Pydantic models**: Use `Field(...)` with descriptions for all model fields. `Optional[str]` for nullable fields.
- **Response format**: All responses use `{"success": bool, "data": ..., "count": ...}` (list) or `{"success": bool, "data": ...}` (detail). Errors use `{"success": false, "error": ..., "detail": ...}`.
- **Async endpoints**: All route handlers use `async def`.
- **Rate limiting**: Applied per-endpoint via `@limiter.limit(settings.RATE_LIMIT)`.
- **Auth**: API key via `X-API-Key` header, enforced in middleware. Exempt paths: `/api/v1/health`, `/docs`, `/redoc`, `/openapi.json`, `/static/*`.
- **Config**: All settings via environment variables loaded through `pydantic-settings`. Access via `app.config.settings`.

## Testing Conventions

- **Framework**: pytest with `fastapi.testclient.TestClient`.
- **Test structure**: Group tests into classes by endpoint (`TestHealthCheck`, `TestGetAllAnimals`, etc.).
- **Naming**: `test_<what_it_tests>` (e.g., `test_get_animal_case_insensitive`).
- **Auth in tests**: Use `HEADERS = {"X-API-Key": settings.API_KEY}` module-level constant.
- **No fixtures**: Tests use a module-level `client = TestClient(app)` directly.

## Environment Variables

Configured in `.env` (not committed). See `.env.example` for defaults:

| Variable          | Default         | Description                     |
| ----------------- | --------------- | ------------------------------- |
| `API_KEY`         | `changeme`      | API key for `X-API-Key` header  |
| `ALLOWED_ORIGINS` | `localhost:*`   | Comma-separated CORS origins    |
| `RATE_LIMIT`      | `100/minute`    | Rate limit per IP               |
| `CACHE_TTL`       | `3600`          | Cache TTL in seconds            |
| `DEBUG`           | `false`         | Enable debug logging            |
