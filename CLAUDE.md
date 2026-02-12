# CLAUDE.md

## Project Overview

Backend API for **Animal Quiz Academy** — an educational quiz app about animals with gamified progression. Built with FastAPI. Animal data is served from `data/animals.json`, quiz levels from `data/levels.json`.

Authentication is handled client-side by **Firebase Authentication** (Flutter app). The backend verifies Firebase ID tokens via the Firebase Admin SDK. When `FIREBASE_CREDENTIALS` is not set, the API runs in mock auth mode for development/testing.

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
├── main.py                          # App setup, middleware (API key, CORS, logging, rate limiting)
├── config.py                        # pydantic-settings config from .env
├── dependencies.py                  # FastAPI Depends: Bearer token verification
├── models/
│   ├── animal.py                    # Pydantic models for legacy animal endpoints
│   ├── auth.py                      # User, RegisterRequest, UpdateProfileRequest, error models
│   └── quiz.py                      # Level, AnswerRequest/Response, LeaderboardEntry models
├── api/v1/endpoints/
│   ├── animals.py                   # Legacy animal CRUD (X-API-Key auth)
│   ├── auth.py                      # POST /register, GET /me (Bearer auth)
│   ├── levels.py                    # GET /levels, GET /levels/{id}
│   ├── quiz.py                      # POST /quiz/answer
│   ├── users.py                     # GET /users/me/progress, coins; PATCH profile
│   └── leaderboard.py              # GET /leaderboard
├── services/
│   ├── animal_service.py            # Animal lookup with LRU caching
│   ├── auth_service.py              # Firebase token verification + user storage (mock/Firestore)
│   ├── level_service.py             # Level data from animals.json + levels.json
│   └── quiz_service.py              # Answer checking, progress, coins (in-memory)
└── db/database.py                   # JSON data access layer
data/
├── animals.json                     # 63 animals with name, rarity level, image, description
└── levels.json                      # 10 quiz levels with title and emoji
```

- **Layered architecture**: endpoints -> services -> db. Endpoints never access db directly.
- **Routing**: All API routes live under `/api/v1/` via `APIRouter`, registered in `main.py`.
- **Data**: `data/animals.json` is the animal data source. `data/levels.json` defines quiz level metadata. Both are cached with `@lru_cache`.
- **Auth (new endpoints)**: Bearer token via Firebase ID token, verified in `dependencies.py` → `auth_service.verify_token()`. Falls back to mock mode when `FIREBASE_CREDENTIALS` is not set.
- **Auth (legacy endpoints)**: API key via `X-API-Key` header, enforced in middleware.
- **Static files**: Served from `/static/`, mounted in `main.py`.

## Code Conventions

- **Python 3.9+** with modern type hints (`list[Animal]`, `int | None`).
- **Module docstrings**: Every module starts with a one-line `"""Description."""` docstring.
- **Class/function docstrings**: All public classes and functions have docstrings.
- **Logging**: Use `logging.getLogger(__name__)` per module. Log format: `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`.
- **Pydantic models**: Use `Field(...)` with descriptions for all model fields. `Optional[str]` for nullable fields. New quiz models use `alias_generator=to_camel` for camelCase JSON serialization.
- **Response format (legacy)**: `{"success": bool, "data": ..., "count": ...}` (list) or `{"success": bool, "data": ...}` (detail). Errors use `{"success": false, "error": ..., "detail": ...}`.
- **Response format (quiz API)**: Matches the OpenAPI spec in `docs/api-spec.yaml`. Errors use `{"error": {"code": "...", "message": "..."}}`.
- **Async endpoints**: All route handlers use `async def`.
- **Rate limiting**: Applied per-endpoint via `@limiter.limit(settings.RATE_LIMIT)`.
- **Config**: All settings via environment variables loaded through `pydantic-settings`. Access via `app.config.settings`.

## Testing Conventions

- **Framework**: pytest with `fastapi.testclient.TestClient`.
- **Test structure**: Group tests into classes by endpoint (`TestHealthCheck`, `TestGetAllAnimals`, etc.).
- **Naming**: `test_<what_it_tests>` (e.g., `test_get_animal_case_insensitive`).
- **Auth in tests (legacy)**: Use `HEADERS = {"X-API-Key": settings.API_KEY}` module-level constant.
- **Auth in tests (quiz API)**: Use mock Bearer tokens via helper functions (`_next_token()`, `_register_and_header()`). In mock auth mode, any non-empty token is accepted as a uid.
- **No fixtures**: Tests use a module-level `client = TestClient(app)` directly.

## Environment Variables

Configured in `.env` (not committed). See `.env.example` for defaults:

| Variable               | Default         | Description                                          |
| ---------------------- | --------------- | ---------------------------------------------------- |
| `API_KEY`              | `changeme`      | API key for `X-API-Key` header (legacy endpoints)    |
| `FIREBASE_CREDENTIALS` | (empty)         | Path to Firebase service account JSON. Empty = mock. |
| `ALLOWED_ORIGINS`      | `localhost:*`   | Comma-separated CORS origins                         |
| `RATE_LIMIT`           | `100/minute`    | Rate limit per IP                                    |
| `CACHE_TTL`            | `3600`          | Cache TTL in seconds                                 |
| `DEBUG`                | `false`         | Enable debug logging                                 |
