"""Tests for the Animal API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

HEADERS = {"X-API-Key": settings.API_KEY}


class TestHealthCheck:
    """Health endpoint tests (no auth required)."""

    def test_health_returns_ok(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestGetAllAnimals:
    """GET /api/v1/animals tests."""

    def test_get_all_animals(self):
        response = client.get("/api/v1/animals", headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["count"] > 0
        assert len(body["data"]) == body["count"]

    def test_filter_by_level(self):
        response = client.get("/api/v1/animals?level=1", headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert all(a["level"] == 1 for a in body["data"])

    def test_filter_by_invalid_level(self):
        response = client.get("/api/v1/animals?level=11", headers=HEADERS)
        assert response.status_code == 422


class TestGetAnimalByName:
    """GET /api/v1/animals/{name} tests."""

    def test_get_existing_animal(self):
        response = client.get("/api/v1/animals/Dog", headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Dog"

    def test_get_animal_case_insensitive(self):
        response = client.get("/api/v1/animals/dog", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Dog"

    def test_get_nonexistent_animal(self):
        response = client.get("/api/v1/animals/Unicorn", headers=HEADERS)
        assert response.status_code == 404


class TestGetAnimalsByLevel:
    """GET /api/v1/animals/level/{level} tests."""

    def test_get_level_1_animals(self):
        response = client.get("/api/v1/animals/level/1", headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert all(a["level"] == 1 for a in body["data"])

    def test_get_invalid_level(self):
        response = client.get("/api/v1/animals/level/0", headers=HEADERS)
        assert response.status_code == 400


class TestApiKeyAuth:
    """API key validation tests."""

    def test_missing_api_key(self):
        response = client.get("/api/v1/animals")
        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False

    def test_wrong_api_key(self):
        response = client.get("/api/v1/animals", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

    def test_health_no_auth_needed(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
