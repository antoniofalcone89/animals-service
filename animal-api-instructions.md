# Animal API Service - Development Instructions

## Project Overview

Build a REST API service using Python and FastAPI that provides animal information including name, image, and rarity level (1-10, where 1 is very common and 10 is very rare).

## Requirements

- Python 3.9+
- FastAPI framework
- Read-only endpoints (GET methods only)
- Simple but extensible and scalable architecture

## Project Structure

Create the following directory structure:

```
animal-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization
│   ├── config.py            # Configuration and settings
│   ├── models/
│   │   ├── __init__.py
│   │   └── animal.py        # Pydantic models
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── animals.py  # Animal endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   └── animal_service.py   # Business logic
│   └── db/
│       ├── __init__.py
│       └── database.py      # Data access layer
├── data/
│   └── animals.json         # Animal data storage
├── static/
│   └── images/              # Animal images directory
├── tests/
│   ├── __init__.py
│   └── test_animals.py
├── .env.example
├── .env
├── .gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## API Endpoints Specification

Implement the following endpoints:

1. `GET /api/v1/animals` - Get all animals
   - Optional query param: `?level={level}` to filter by level
2. `GET /api/v1/animals/{name}` - Get specific animal by name
   - Path param: animal name (case-insensitive)
3. `GET /api/v1/animals/level/{level}` - Get all animals with specific level
   - Path param: level (1-10)
4. `GET /api/v1/health` - Health check endpoint

## Data Model

### Animal Schema (Pydantic)

```python
{
    "name": str,                    # Animal name (e.g., "Dog", "Kakapo")
    "level": int,                   # Rarity level 1-10 (1=common, 10=rare)
    "image_url": str,               # URL to animal image
    "description": Optional[str],   # Animal description
    "scientific_name": Optional[str] # Scientific name
}
```

## Implementation Details

### 1. Data Storage (MVP - JSON File)

- Use `data/animals.json` for initial implementation
- Structure as array of animal objects
- Include at least 60 sample animals with varying levels

### 2. Image Handling

- Store images in `static/images/` directory
- Naming convention: `{animal_name_lowercase}.jpg` (e.g., `dog.jpg`, `kakapo.jpg`)
- FastAPI should serve static files from `/static/images/`
- Return full URL in API responses (e.g., `http://localhost:8000/static/images/dog.jpg`)

### 3. Caching Implementation

- Use `functools.lru_cache` for in-memory caching
- Cache the entire animal dataset
- Cache individual animal lookups
- Set reasonable cache size limits

### 4. Security Features

**Rate Limiting:**

- Install and configure `slowapi`
- Limit: 100 requests per minute per IP
- Apply to all animal endpoints

**API Key Authentication:**

- Implement API key validation via `X-API-Key` header
- Store API key in `.env` file
- Create middleware to check API key on protected endpoints
- Allow health check endpoint without authentication

**CORS:**

- Configure CORS middleware
- Allow configurable origins from environment variables
- Default to restrictive settings

**Input Validation:**

- Use Pydantic models for automatic validation
- Validate level range (1-10)
- Sanitize string inputs

### 5. Configuration Management

- Use `pydantic-settings` for configuration
- Load settings from `.env` file
- Include settings for:
  - API_KEY
  - ALLOWED_ORIGINS (comma-separated)
  - RATE_LIMIT (e.g., "100/minute")
  - CACHE_TTL (seconds)
  - DEBUG mode

### 6. Error Handling

- Return appropriate HTTP status codes
- 404 for animal not found
- 400 for invalid input
- 422 for validation errors
- 429 for rate limit exceeded
- 401 for invalid API key
- Include meaningful error messages in JSON format

### 7. Response Format

**Success Response:**

```json
{
    "success": true,
    "data": [...],
    "count": 10
}
```

**Single Item Response:**

```json
{
    "success": true,
    "data": {...}
}
```

**Error Response:**

```json
{
  "success": false,
  "error": "Error message here",
  "detail": "Detailed error information"
}
```

## Requirements File

Include the following dependencies in `requirements.txt`:

- fastapi
- uvicorn[standard]
- pydantic
- pydantic-settings
- python-dotenv
- slowapi
- python-multipart

## Sample Animal Data

Include at least these animals in `animals.json`:

**Level 1 (Very Common):**

- Dog, Cat, Chicken, Cow, Sheep

**Level 3-4 (Common):**

- Fox, Deer, Rabbit, Squirrel

**Level 5-6 (Moderate):**

- Red Panda, Koala, Penguin, Otter

**Level 7-8 (Rare):**

- Snow Leopard, Pangolin, Axolotl

**Level 9-10 (Very Rare):**

- Kakapo, Vaquita, Javan Rhino, Philippine Eagle

## Docker Configuration

### Dockerfile

- Use Python 3.11 slim image
- Copy requirements and install dependencies
- Copy application code
- Expose port 8000
- Run with uvicorn

### docker-compose.yml

- Service for FastAPI app
- Optional Redis service (for future use)
- Volume mounts for development
- Environment variables from .env

## Testing Requirements

Create basic tests for:

- Get all animals endpoint
- Get animal by name (found and not found cases)
- Get animals by level
- Rate limiting
- API key validation
- Invalid input handling

## Environment Variables (.env.example)

```env
API_KEY=your-secret-api-key-here
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
RATE_LIMIT=100/minute
CACHE_TTL=3600
DEBUG=true
```

## Running Instructions

Include in README.md:

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run with Docker
docker-compose up --build

# Run tests
pytest tests/
```

## Code Quality Requirements

- Use type hints throughout the codebase
- Follow PEP 8 style guidelines
- Add docstrings to all functions and classes
- Keep functions small and focused (single responsibility)
- Use meaningful variable and function names
- Add comments for complex logic

## Logging

- Configure structured logging
- Log all API requests
- Log errors with stack traces
- Log rate limit violations
- Use different log levels appropriately (DEBUG, INFO, WARNING, ERROR)

## Documentation

Generate automatic API documentation:

- FastAPI will auto-generate docs at `/docs` (Swagger UI)
- Alternative docs at `/redoc` (ReDoc)

## Future Scalability Considerations

Design the code to easily support:

- Migration from JSON to PostgreSQL database
- Moving images to object storage (S3, MinIO)
- Adding Redis for distributed caching
- Adding POST/PUT/DELETE endpoints
- User authentication and authorization
- Pagination for large datasets
- Full-text search capabilities

## Success Criteria

The implementation should:

1. ✓ Run without errors on fresh installation
2. ✓ Return correct data for all endpoints
3. ✓ Enforce rate limiting
4. ✓ Validate API keys
5. ✓ Serve images correctly
6. ✓ Handle errors gracefully
7. ✓ Be well-documented
8. ✓ Pass all tests
9. ✓ Follow Python best practices
10. ✓ Be ready for Docker deployment

## Additional Notes

- Prioritize code readability and maintainability
- Use async/await for all endpoints
- Implement proper exception handling
- Consider adding request/response logging middleware
- Make the service stateless for horizontal scaling
- Use connection pooling if migrating to a database

## Optional Enhancements (if time permits)

- Add filtering by multiple criteria
- Implement search functionality with fuzzy matching
- Add sorting options (by name, level)
- Include animal habitat and diet information
- Add pagination support
- Create health check with dependency validation
- Add metrics endpoint for monitoring
- Implement API versioning strategy
