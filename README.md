# Animal API

REST API service built with Python and FastAPI that provides animal information including name, image, and rarity level (1-10, where 1 is very common and 10 is extremely rare).

## Prerequisites

- Python 3.9+ (tested with 3.13)
- Docker and Docker Compose (optional, for containerized deployment)

## Project Structure

```
animal-service/
├── app/
│   ├── main.py                    # FastAPI app, middleware, startup
│   ├── config.py                  # Settings loaded from .env
│   ├── models/
│   │   └── animal.py              # Pydantic request/response models
│   ├── api/v1/endpoints/
│   │   └── animals.py             # Route handlers
│   ├── services/
│   │   └── animal_service.py      # Business logic & caching
│   └── db/
│       └── database.py            # JSON data access layer
├── data/
│   └── animals.json               # 63 animals across levels 1-10
├── static/images/                 # Animal placeholder images
├── tests/
│   └── test_animals.py            # 12 endpoint & auth tests
├── generate_images.py             # Script to regenerate placeholder images
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── .env
```

## Getting Started

### 1. Clone and enter the project

```bash
cd animal-service
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` to set your values:

```env
API_KEY=your-secret-api-key-here
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
RATE_LIMIT=100/minute
CACHE_TTL=3600
DEBUG=true
```

| Variable          | Default                                       | Description                                         |
| ----------------- | --------------------------------------------- | --------------------------------------------------- |
| `API_KEY`         | `changeme`                                    | Secret key clients must pass via `X-API-Key` header |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8080` | Comma-separated CORS allowed origins                |
| `RATE_LIMIT`      | `100/minute`                                  | Max requests per IP per time window                 |
| `CACHE_TTL`       | `3600`                                        | Cache time-to-live in seconds                       |
| `DEBUG`           | `false`                                       | Enable debug-level logging                          |

### 5. Start the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at **http://localhost:8000**.

### 6. Run tests

```bash
pytest tests/ -v
```

## Running with Docker

```bash
# Build and start
docker-compose up --build

# Stop
docker-compose down
```

The container exposes port **8000** and reads configuration from your `.env` file.

## API Reference

### Authentication

All endpoints except `/api/v1/health` and `/docs` require an API key passed in the `X-API-Key` header.

### Endpoints

#### Health Check

```
GET /api/v1/health
```

No authentication required.

```bash
curl http://localhost:8000/api/v1/health
```

Response:

```json
{
  "status": "healthy",
  "service": "animal-service",
  "version": "1.0.0"
}
```

#### Get All Animals

```
GET /api/v1/animals
GET /api/v1/animals?level={1-10}
```

Returns all animals, optionally filtered by rarity level.

```bash
curl -H "X-API-Key: your-secret-api-key-here" http://localhost:8000/api/v1/animals

# Filter by level
curl -H "X-API-Key: your-secret-api-key-here" "http://localhost:8000/api/v1/animals?level=10"
```

Response:

```json
{
  "success": true,
  "data": [
    {
      "name": "Dog",
      "level": 1,
      "image_url": "/static/images/dog.jpg",
      "description": "Loyal domesticated companion, one of the most popular pets worldwide.",
      "scientific_name": "Canis lupus familiaris"
    }
  ],
  "count": 63
}
```

#### Get Animal by Name

```
GET /api/v1/animals/{name}
```

Lookup is case-insensitive (e.g. `dog`, `Dog`, `DOG` all work).

```bash
curl -H "X-API-Key: your-secret-api-key-here" http://localhost:8000/api/v1/animals/Axolotl
```

Response:

```json
{
  "success": true,
  "data": {
    "name": "Axolotl",
    "level": 7,
    "image_url": "/static/images/axolotl.jpg",
    "description": "Mexican salamander that retains larval features throughout life.",
    "scientific_name": "Ambystoma mexicanum"
  }
}
```

#### Get Animals by Level

```
GET /api/v1/animals/level/{level}
```

Level must be an integer from 1 to 10.

```bash
curl -H "X-API-Key: your-secret-api-key-here" http://localhost:8000/api/v1/animals/level/9
```

### Error Responses

All errors follow a consistent format:

```json
{
  "success": false,
  "error": "Error message",
  "detail": "Additional details"
}
```

| Status Code | Meaning                                 |
| ----------- | --------------------------------------- |
| 400         | Invalid input (e.g. level out of range) |
| 401         | Missing or invalid API key              |
| 404         | Animal not found                        |
| 422         | Validation error                        |
| 429         | Rate limit exceeded                     |

## Rarity Levels

| Level | Rarity      | Example Animals                            |
| ----- | ----------- | ------------------------------------------ |
| 1     | Very Common | Dog, Cat, Chicken, Cow                     |
| 2     | Common      | Duck, Pigeon, Sparrow                      |
| 3-4   | Uncommon    | Fox, Deer, Eagle, Owl                      |
| 5-6   | Moderate    | Red Panda, Koala, Penguin, Capybara        |
| 7-8   | Rare        | Snow Leopard, Pangolin, Axolotl, Cassowary |
| 9     | Very Rare   | Kakapo, Philippine Eagle, Amur Leopard     |
| 10    | Legendary   | Vaquita, Javan Rhino, Hainan Gibbon        |

## Static Images

Placeholder images are served at `/static/images/{filename}.jpg` and are color-coded by rarity level (green for common through gold for legendary).

To regenerate images:

```bash
pip install Pillow
python3 generate_images.py
```

## Interactive API Docs

FastAPI auto-generates interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Architecture Notes

- **Data layer**: JSON file (`data/animals.json`) — designed for easy migration to a database
- **Caching**: `functools.lru_cache` on data loading and individual name lookups
- **Rate limiting**: slowapi (backed by limits library), configurable via `RATE_LIMIT`
- **CORS**: Configurable allowed origins, restricted to GET methods only
- **Async**: All endpoints use `async/await`
- **Stateless**: No server-side session state, ready for horizontal scaling
