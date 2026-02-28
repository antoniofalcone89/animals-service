"""Tests for the Quiz Academy API endpoints (auth, levels, quiz, users, leaderboard).

In mock auth mode (no FIREBASE_CREDENTIALS set), any non-empty Bearer token is
accepted and the token value is used as the user ID.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.animals import limiter as animals_limiter
from app.api.v1.endpoints.auth import limiter as auth_limiter
from app.api.v1.endpoints.challenge import limiter as challenge_limiter
from app.api.v1.endpoints.leaderboard import limiter as leaderboard_limiter
from app.api.v1.endpoints.levels import limiter as levels_limiter
from app.api.v1.endpoints.quiz import limiter as quiz_limiter
from app.api.v1.endpoints.users import limiter as users_limiter
from app.main import app
from app.services import auth_service

client = TestClient(app)

# Counter for unique mock user tokens across test runs
_uid_counter = 0


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    """Reset SlowAPI in-memory counters to avoid cross-test leakage."""
    for limiter in (
        animals_limiter,
        auth_limiter,
        challenge_limiter,
        levels_limiter,
        quiz_limiter,
        users_limiter,
        leaderboard_limiter,
    ):
        storage = getattr(limiter, "_storage", None)
        if storage is not None and hasattr(storage, "reset"):
            storage.reset()


def _next_token() -> str:
    """Return a unique mock Bearer token / uid for each test."""
    global _uid_counter
    _uid_counter += 1
    return f"mock-uid-{_uid_counter}"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(token: str, username: str = "testuser", photo_url: str | None = None) -> dict:
    """Register a user profile and return the response body."""
    payload = {"username": username}
    if photo_url is not None:
        payload["photoUrl"] = photo_url
    resp = client.post(
        "/api/v1/auth/register",
        headers=_auth_header(token),
        json=payload,
    )
    return resp.json(), resp.status_code


def _register_and_header(username: str = "testuser") -> dict:
    """Register a fresh user and return the auth header dict."""
    token = _next_token()
    _register(token, username)
    return _auth_header(token)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuthRegister:
    """POST /api/v1/auth/register tests."""

    def test_register_success(self):
        token = _next_token()
        body, status = _register(token, username="newuser")
        assert status == 201
        assert body["username"] == "newuser"
        assert body["id"] == token  # in mock mode, uid == token

    def test_register_duplicate(self):
        token = _next_token()
        _register(token)
        body, status = _register(token, username="other")
        assert status == 409

    def test_register_duplicate_error_code(self):
        token = _next_token()
        _register(token)
        resp = client.post(
            "/api/v1/auth/register",
            headers=_auth_header(token),
            json={"username": "other"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "profile_exists"

    def test_register_short_username(self):
        token = _next_token()
        resp = client.post(
            "/api/v1/auth/register",
            headers=_auth_header(token),
            json={"username": "a"},
        )
        assert resp.status_code == 422

    def test_register_with_photo_url_hint(self):
        token = _next_token()
        hint = "https://example.com/avatar.png"
        body, status = _register(token, username="withphoto", photo_url=hint)
        assert status == 201
        assert body["photoUrl"] == hint

    def test_register_no_auth(self):
        resp = client.post("/api/v1/auth/register", json={"username": "test"})
        assert resp.status_code in (401, 403)


class TestAuthMe:
    """GET /api/v1/auth/me tests."""

    def test_get_current_user(self):
        token = _next_token()
        _register(token, username="meuser")
        resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["username"] == "meuser"
        assert "photoUrl" in resp.json()
        assert resp.json()["currentStreak"] == 0
        assert resp.json()["lastActivityDate"] is None

    def test_get_current_user_with_photo_url(self):
        token = _next_token()
        hint = "https://example.com/me.png"
        _register(token, username="mephoto", photo_url=hint)
        resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["photoUrl"] == hint

    def test_get_current_user_not_registered(self):
        token = _next_token()
        resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert resp.status_code == 404

    def test_get_current_user_no_auth(self):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------

class TestLevels:
    """GET /api/v1/levels tests."""

    def test_list_levels(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/levels", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "levels" in data
        assert len(data["levels"]) == 6
        for level in data["levels"]:
            assert "id" in level
            assert "title" in level
            assert "animals" in level
            assert len(level["animals"]) == 20

    def test_list_levels_no_auth(self):
        resp = client.get("/api/v1/levels")
        assert resp.status_code in (401, 403)


class TestLevelDetail:
    """GET /api/v1/levels/{levelId} tests."""

    def test_get_level_detail_default_italian(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/levels/1", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["title"] == "Livello 1"
        assert len(data["animals"]) == 20
        assert data["animals"][0]["name"] == "Cane"
        for animal in data["animals"]:
            assert "guessed" in animal
            assert animal["guessed"] is False

    def test_get_level_detail_english(self):
        headers = {**_register_and_header(), "Accept-Language": "en"}
        resp = client.get("/api/v1/levels/1", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Level 1"
        assert data["animals"][0]["name"] == "Dog"

    def test_get_level_not_found(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/levels/999", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

class TestQuizAnswer:
    """POST /api/v1/quiz/answer tests."""

    def test_correct_answer_italian(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["coinsAwarded"] == 12
        assert data["totalCoins"] == 12
        assert data["pointsAwarded"] == 20
        assert data["correctAnswer"] == "Cane"
        assert data["currentStreak"] == 1
        assert data["lastActivityDate"] == datetime.now(timezone.utc).date().isoformat()
        assert data["streakBonusCoins"] == 2

    def test_correct_answer_english(self):
        headers = {**_register_and_header(), "Accept-Language": "en"}
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Dog",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["coinsAwarded"] == 12
        assert data["pointsAwarded"] == 20
        assert data["streakBonusCoins"] == 2

    def test_wrong_answer(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Gatto",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is False
        assert data["coinsAwarded"] == 0
        assert data["pointsAwarded"] == 0
        assert data["correctAnswer"] == "Cane"
        assert data["streakBonusCoins"] == 0

    def test_case_insensitive_answer(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "cane",
        })
        assert resp.status_code == 200
        assert resp.json()["correct"] is True

    def test_already_guessed_no_coins(self):
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        data = resp.json()
        assert data["correct"] is True
        assert data["coinsAwarded"] == 0
        assert data["pointsAwarded"] == 0
        assert data["streakBonusCoins"] == 0

    def test_second_correct_same_day_has_no_streak_bonus(self):
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 1, "answer": "Gatto",
        })
        data = resp.json()
        assert data["correct"] is True
        assert data["coinsAwarded"] == 10
        assert data["streakBonusCoins"] == 0

    def test_first_correct_bonus_uses_streak_and_caps_at_20(self):
        token = _next_token()
        _register(token, username="bonus-streak")
        headers = _auth_header(token)

        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        auth_service.update_user(token, current_streak=10, last_activity_date=yesterday)

        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        data = resp.json()
        assert data["correct"] is True
        assert data["currentStreak"] == 11
        assert data["streakBonusCoins"] == 20
        assert data["coinsAwarded"] == 30

    def test_invalid_level(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 999, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.status_code == 400

    def test_fuzzy_match_one_edit_short_word(self):
        """Short word (<=7 chars): 1 edit allowed — 'Cne' matches 'Cane'."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cne",
        })
        data = resp.json()
        assert data["correct"] is True
        assert data["correctAnswer"] == "Cane"

    def test_fuzzy_match_two_edits_short_word_rejected(self):
        """Short word (<=7 chars): 2 edits NOT allowed — 'Ce' does not match 'Cane'."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Ce",
        })
        assert resp.json()["correct"] is False

    def test_fuzzy_match_two_edits_long_word(self):
        """Long word (8+ chars): 2 edits allowed — 'Elphant' matches 'Elephant'."""
        headers = {**_register_and_header(), "Accept-Language": "en"}
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 16, "answer": "Elphant",
        })
        data = resp.json()
        assert data["correct"] is True
        assert data["correctAnswer"] == "Elephant"

    def test_fuzzy_match_returns_correct_answer(self):
        """Fuzzy match always returns correctAnswer with proper spelling."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cone",
        })
        data = resp.json()
        assert data["correct"] is True
        assert data["correctAnswer"] == "Cane"

    def test_wrong_answer_returns_correct_answer(self):
        """Wrong answer also returns correctAnswer."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Tigre",
        })
        data = resp.json()
        assert data["correct"] is False
        assert data["correctAnswer"] == "Cane"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class TestUserProgress:
    """GET /api/v1/users/me/progress tests."""

    def test_get_progress_default_italian(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/users/me/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "levels" in data
        assert len(data["levels"]) == 6
        # First animal of level 1 should be Italian
        assert data["levels"]["1"][0]["name"] == "Cane"
        for animals in data["levels"].values():
            assert len(animals) == 20
            for animal in animals:
                assert "id" in animal
                assert "name" in animal
                assert "imageUrl" in animal
                assert "emoji" not in animal
                assert animal["guessed"] is False

    def test_get_progress_english(self):
        headers = {**_register_and_header(), "Accept-Language": "en"}
        resp = client.get("/api/v1/users/me/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["levels"]["1"][0]["name"] == "Dog"


class TestUserCoins:
    """GET /api/v1/users/me/coins tests."""

    def test_get_coins(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/users/me/coins", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["totalCoins"] == 0


class TestUserStreak:
    """GET /api/v1/users/me/streak tests."""

    def test_get_streak_starts_at_zero(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/users/me/streak", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["currentStreak"] == 0
        assert resp.json()["lastActivityDate"] is None

    def test_first_correct_sets_streak_to_one(self):
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.get("/api/v1/users/me/streak", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["currentStreak"] == 1
        assert resp.json()["lastActivityDate"] == datetime.now(timezone.utc).date().isoformat()

    def test_multiple_correct_same_day_does_not_increment_streak(self):
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 1, "answer": "Gatto",
        })
        resp = client.get("/api/v1/users/me/streak", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["currentStreak"] == 1

    def test_yesterday_increments_streak(self):
        token = _next_token()
        _register(token, username="streakuser")
        headers = _auth_header(token)
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        auth_service.update_user(token, current_streak=4, last_activity_date=yesterday)

        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.get("/api/v1/users/me/streak", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["currentStreak"] == 5

    def test_older_than_yesterday_resets_streak(self):
        token = _next_token()
        _register(token, username="streakreset")
        headers = _auth_header(token)
        older = (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
        auth_service.update_user(token, current_streak=7, last_activity_date=older)

        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.get("/api/v1/users/me/streak", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["currentStreak"] == 1


class TestBuyHint:
    """POST /api/v1/quiz/buy-hint tests."""

    def test_buy_hint_success(self):
        headers = _register_and_header()
        # First correct answer awards base + streak bonus
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        # Buy first hint for animal at index 1 (cost=5)
        resp = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hintsRevealed"] == 1
        assert data["totalCoins"] == 7
        # Verify coins via GET /users/me/coins
        resp2 = client.get("/api/v1/users/me/coins", headers=headers)
        assert resp2.json()["totalCoins"] == 7

    def test_buy_hint_escalating_cost(self):
        headers = _register_and_header()
        # Earn coins (first daily correct includes streak bonus)
        for idx in range(4):
            # Get the correct Italian name for each animal
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct_name = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": correct_name,
            })
        # Buy 3 hints for animal 5: costs 5, 10, 20
        resp1 = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp1.json()["hintsRevealed"] == 1
        assert resp1.json()["totalCoins"] == 37

        resp2 = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp2.json()["hintsRevealed"] == 2
        assert resp2.json()["totalCoins"] == 27

        resp3 = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp3.json()["hintsRevealed"] == 3
        assert resp3.json()["totalCoins"] == 7

    def test_buy_hint_insufficient_coins(self):
        headers = _register_and_header()
        # No coins earned — buying a hint should fail
        resp = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 0,
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "insufficient_coins"

    def test_buy_hint_max_hints_reached(self):
        headers = _register_and_header()
        # Earn enough coins: 4 correct answers = 40 coins (need 5+10+20=35)
        for idx in range(4):
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct_name = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": correct_name,
            })
        # Buy all 3 hints
        for _ in range(3):
            client.post("/api/v1/quiz/buy-hint", headers=headers, json={
                "levelId": 1, "animalIndex": 5,
            })
        # 4th attempt should fail
        resp = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "max_hints_reached"

    def test_buy_hint_invalid_level(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 999, "animalIndex": 0,
        })
        assert resp.status_code == 400

    def test_buy_hint_no_auth(self):
        resp = client.post("/api/v1/quiz/buy-hint", json={
            "levelId": 1, "animalIndex": 0,
        })
        assert resp.status_code in (401, 403)

    def test_progress_includes_hints_revealed(self):
        headers = _register_and_header()
        # Earn coins and buy a hint
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 1,
        })
        # Check progress includes hintsRevealed
        resp = client.get("/api/v1/users/me/progress", headers=headers)
        assert resp.status_code == 200
        animals = resp.json()["levels"]["1"]
        assert animals[1]["hintsRevealed"] == 1
        assert animals[0]["hintsRevealed"] == 0


class TestRevealLetter:
    """POST /api/v1/quiz/reveal-letter tests."""

    def _earn_coins(self, headers: dict, count: int) -> None:
        """Earn coins by answering animals correctly (10 coins each)."""
        for idx in range(count):
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct_name = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": correct_name,
            })

    def test_reveal_letter_success(self):
        headers = _register_and_header()
        # Earn at least 30 coins
        self._earn_coins(headers, 3)
        # Reveal a letter for animal at index 5
        resp = client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["lettersRevealed"] == 1
        assert data["totalCoins"] == 2

    def test_reveal_letter_insufficient_coins(self):
        headers = _register_and_header()
        # No coins earned
        resp = client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
            "levelId": 1, "animalIndex": 0,
        })
        assert resp.status_code == 402
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "insufficient_coins"

    def test_reveal_letter_max_reveals(self):
        headers = _register_and_header()
        # Earn 90 coins (9 correct answers) to cover 3 reveals at 30 each
        self._earn_coins(headers, 9)
        # Reveal 3 letters
        for i in range(3):
            resp = client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
                "levelId": 1, "animalIndex": 10,
            })
            assert resp.status_code == 200
            assert resp.json()["lettersRevealed"] == i + 1
        # 4th attempt should fail
        resp = client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
            "levelId": 1, "animalIndex": 10,
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "max_reveals_reached"

    def test_reveal_letter_invalid_level(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
            "levelId": 999, "animalIndex": 0,
        })
        assert resp.status_code == 400

    def test_reveal_letter_no_auth(self):
        resp = client.post("/api/v1/quiz/reveal-letter", json={
            "levelId": 1, "animalIndex": 0,
        })
        assert resp.status_code in (401, 403)

    def test_progress_includes_letters_revealed(self):
        headers = _register_and_header()
        # Earn 30 coins and reveal a letter
        self._earn_coins(headers, 3)
        client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
            "levelId": 1, "animalIndex": 4,
        })
        # Check progress includes lettersRevealed
        resp = client.get("/api/v1/users/me/progress", headers=headers)
        assert resp.status_code == 200
        animals = resp.json()["levels"]["1"]
        assert animals[4]["lettersRevealed"] == 1
        assert animals[0]["lettersRevealed"] == 0


class TestPointsScoring:
    """Points scoring tests for POST /api/v1/quiz/answer."""

    def _earn_coins(self, headers: dict, count: int) -> None:
        """Earn coins by answering animals correctly (10 coins each)."""
        for idx in range(count):
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct_name = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": correct_name,
            })

    def test_correct_answer_points_no_assists(self):
        """No hints or letters used: 20 points."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.json()["pointsAwarded"] == 20

    def test_correct_answer_points_one_hint(self):
        """1 hint used: 15 points."""
        headers = _register_and_header()
        # Earn coins first, then buy a hint for animal 5
        self._earn_coins(headers, 1)
        client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        # Now answer animal 5 correctly
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 5, "answer": "wrong",
        })
        correct_name = resp.json()["correctAnswer"]
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 5, "answer": correct_name,
        })
        assert resp.json()["pointsAwarded"] == 15

    def test_correct_answer_points_two_assists(self):
        """1 hint + 1 letter = 2 assists: 10 points."""
        headers = _register_and_header()
        # Earn enough coins (4 correct = 40 coins)
        self._earn_coins(headers, 4)
        # Buy a hint and reveal a letter for animal 5
        client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        client.post("/api/v1/quiz/reveal-letter", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        # Answer animal 5
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 5, "answer": "wrong",
        })
        correct_name = resp.json()["correctAnswer"]
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 5, "answer": correct_name,
        })
        assert resp.json()["pointsAwarded"] == 10

    def test_correct_answer_points_three_plus_assists(self):
        """3+ assists: 5 points."""
        headers = _register_and_header()
        # Earn enough coins (4 correct = 40 coins)
        self._earn_coins(headers, 4)
        # Buy 3 hints for animal 5 (costs 5+10+20=35)
        for _ in range(3):
            client.post("/api/v1/quiz/buy-hint", headers=headers, json={
                "levelId": 1, "animalIndex": 5,
            })
        # Answer animal 5
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 5, "answer": "wrong",
        })
        correct_name = resp.json()["correctAnswer"]
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 5, "answer": correct_name,
        })
        assert resp.json()["pointsAwarded"] == 5

    def test_correct_answer_ad_revealed(self):
        """Ad revealed: 3 points regardless of assists."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane", "adRevealed": True,
        })
        assert resp.json()["pointsAwarded"] == 3

    def test_wrong_answer_zero_points(self):
        """Wrong answer: 0 points."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Tigre",
        })
        assert resp.json()["pointsAwarded"] == 0

    def test_already_guessed_zero_points(self):
        """Already guessed: 0 points on re-submission."""
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.json()["pointsAwarded"] == 0


class TestUserPoints:
    """GET /api/v1/users/me/points tests."""

    def test_get_points_starts_at_zero(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/users/me/points", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["totalPoints"] == 0

    def test_get_points_increases_after_correct_answer(self):
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.get("/api/v1/users/me/points", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["totalPoints"] == 20


class TestUpdateProfile:
    """PATCH /api/v1/users/me/profile tests."""

    def test_update_username(self):
        headers = _register_and_header(username="oldname")
        resp = client.patch("/api/v1/users/me/profile", headers=headers, json={
            "username": "newname",
        })
        assert resp.status_code == 200
        assert resp.json()["username"] == "newname"


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

class TestLeaderboard:
    """GET /api/v1/leaderboard tests."""

    def test_get_leaderboard(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/leaderboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        assert isinstance(data["entries"], list)

    def test_leaderboard_entries_have_total_points(self):
        headers = _register_and_header()
        # Earn some points
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.get("/api/v1/leaderboard", headers=headers)
        data = resp.json()
        assert len(data["entries"]) > 0
        entry = data["entries"][0]
        assert "totalPoints" in entry
        assert "totalCoins" not in entry
        assert "photoUrl" in entry
        assert "currentStreak" in entry

    def test_leaderboard_entry_includes_photo_url(self):
        token = _next_token()
        hint = "https://example.com/leader.png"
        _register(token, username="leader-photo", photo_url=hint)
        headers = _auth_header(token)
        resp = client.get("/api/v1/leaderboard?limit=100", headers=headers)
        assert resp.status_code == 200
        entry = next(e for e in resp.json()["entries"] if e["userId"] == token)
        assert entry["photoUrl"] == hint

    def test_leaderboard_sorted_by_points(self):
        """Users with more points should rank higher."""
        headers_a = _register_and_header(username="user_a")
        headers_b = _register_and_header(username="user_b")
        # user_a answers 2 animals (40 points)
        for idx in range(2):
            resp = client.post("/api/v1/quiz/answer", headers=headers_a, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers_a, json={
                "levelId": 1, "animalIndex": idx, "answer": correct,
            })
        # user_b answers 1 animal (20 points)
        resp = client.post("/api/v1/quiz/answer", headers=headers_b, json={
            "levelId": 1, "animalIndex": 0, "answer": "wrong",
        })
        correct = resp.json()["correctAnswer"]
        client.post("/api/v1/quiz/answer", headers=headers_b, json={
            "levelId": 1, "animalIndex": 0, "answer": correct,
        })
        resp = client.get("/api/v1/leaderboard", headers=headers_a)
        entries = resp.json()["entries"]
        # Find our two users
        points_list = [e["totalPoints"] for e in entries]
        assert points_list == sorted(points_list, reverse=True)

    def test_leaderboard_no_auth(self):
        resp = client.get("/api/v1/leaderboard")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Daily Challenge
# ---------------------------------------------------------------------------

class TestDailyChallenge:
    """Daily challenge endpoint tests."""

    def test_get_today_returns_fixed_10_animals(self):
        headers = _register_and_header()
        resp = client.get("/api/v1/challenge/today", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert len(data["animals"]) == 10
        assert data["completed"] is False
        assert data["score"] is None

    def test_today_is_deterministic_same_date(self):
        headers_a = _register_and_header(username="challenge-a")
        headers_b = _register_and_header(username="challenge-b")
        resp_a = client.get("/api/v1/challenge/today", headers=headers_a)
        resp_b = client.get("/api/v1/challenge/today", headers=headers_b)
        ids_a = [a["id"] for a in resp_a.json()["animals"]]
        ids_b = [a["id"] for a in resp_b.json()["animals"]]
        assert ids_a == ids_b

    def test_answer_correct_updates_score_without_coins(self):
        headers = _register_and_header()
        today = client.get("/api/v1/challenge/today", headers=headers).json()
        first_name = today["animals"][0]["name"]

        resp = client.post("/api/v1/challenge/answer", headers=headers, json={
            "animalIndex": 0,
            "answer": first_name,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["coinsAwarded"] == 0
        assert data["pointsAwarded"] == 20
        assert data["streakBonusCoins"] == 0

    def test_answer_same_index_twice_awards_points_once(self):
        headers = _register_and_header()
        today = client.get("/api/v1/challenge/today", headers=headers).json()
        first_name = today["animals"][0]["name"]

        first = client.post("/api/v1/challenge/answer", headers=headers, json={
            "animalIndex": 0,
            "answer": first_name,
        })
        second = client.post("/api/v1/challenge/answer", headers=headers, json={
            "animalIndex": 0,
            "answer": first_name,
        })
        assert first.json()["pointsAwarded"] == 20
        assert second.json()["pointsAwarded"] == 0

    def test_completing_all_animals_marks_completed(self):
        headers = _register_and_header()
        today = client.get("/api/v1/challenge/today", headers=headers).json()
        for idx, animal in enumerate(today["animals"]):
            client.post("/api/v1/challenge/answer", headers=headers, json={
                "animalIndex": idx,
                "answer": animal["name"],
            })

        after = client.get("/api/v1/challenge/today", headers=headers)
        assert after.status_code == 200
        data = after.json()
        assert data["completed"] is True
        assert data["score"] == 200

    def test_challenge_leaderboard_sorted_by_score(self):
        headers_a = _register_and_header(username="daily_a")
        headers_b = _register_and_header(username="daily_b")

        animals = client.get("/api/v1/challenge/today", headers=headers_a).json()["animals"]
        for idx in range(2):
            client.post("/api/v1/challenge/answer", headers=headers_a, json={
                "animalIndex": idx,
                "answer": animals[idx]["name"],
            })

        client.post("/api/v1/challenge/answer", headers=headers_b, json={
            "animalIndex": 0,
            "answer": animals[0]["name"],
        })

        resp = client.get("/api/v1/challenge/leaderboard?date=today", headers=headers_a)
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) >= 2
        scores = [e["score"] for e in entries]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

class TestAchievements:
    """GET /api/v1/users/me/achievements and achievement unlock tests."""

    def test_get_achievements_empty(self):
        """New user has no unlocked achievements."""
        headers = _register_and_header()
        resp = client.get("/api/v1/users/me/achievements", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["unlocked"] == []
        assert len(data["definitions"]) == 9  # all 9 achievement types

    def test_get_achievements_no_auth(self):
        resp = client.get("/api/v1/users/me/achievements")
        assert resp.status_code in (401, 403)

    def test_answer_response_has_new_achievements_field(self):
        """AnswerResponse always includes newAchievements list."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "wrong",
        })
        assert resp.status_code == 200
        assert "newAchievements" in resp.json()

    def test_first_correct_achievement_unlocked(self):
        """first_correct achievement is awarded on the very first correct answer."""
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.status_code == 200
        assert "first_correct" in resp.json()["newAchievements"]

        ach_resp = client.get("/api/v1/users/me/achievements", headers=headers)
        unlocked_ids = [a["id"] for a in ach_resp.json()["unlocked"]]
        assert "first_correct" in unlocked_ids

    def test_first_correct_not_awarded_twice(self):
        """first_correct should not appear in newAchievements on a second answer."""
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 1, "answer": "Gatto",
        })
        assert "first_correct" not in resp.json()["newAchievements"]

    def test_streak_7_achievement_unlocked(self):
        """streak_7 is awarded when current_streak reaches 7."""
        from app.db.user_store import get_store
        headers = _register_and_header(username="streak7user")
        token = _next_token()
        _register(token, username="streak7direct")
        h = _auth_header(token)

        # Manually set streak to 6 and last_activity_date to yesterday
        from datetime import date, timedelta
        store = get_store()
        store.update_user(token, current_streak=6, last_activity_date=(date.today() - timedelta(days=1)).isoformat())

        resp = client.post("/api/v1/quiz/answer", headers=h, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.status_code == 200
        assert "streak_7" in resp.json()["newAchievements"]

    def test_coins_500_achievement_unlocked(self):
        """coins_500 is awarded when total_coins reaches 500."""
        from app.db.user_store import get_store
        token = _next_token()
        _register(token, username="coinrich")
        h = _auth_header(token)

        # Give user 490 coins so next correct answer tips over 500
        store = get_store()
        store.ensure_progress(token)
        store._coins[token] = 490  # InMemoryUserStore internal; direct set for test

        resp = client.post("/api/v1/quiz/answer", headers=h, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.status_code == 200
        assert "coins_500" in resp.json()["newAchievements"]

    def test_leaderboard_entry_has_achievements_count(self):
        """Leaderboard entries include achievementsCount field."""
        headers = _register_and_header()
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        resp = client.get("/api/v1/leaderboard", headers=headers)
        assert resp.status_code == 200
        entry = resp.json()["entries"][0]
        assert "achievementsCount" in entry
        assert isinstance(entry["achievementsCount"], int)

    def test_no_hints_10_achievement(self):
        """no_hints_10 is awarded after 10 consecutive no-hint correct answers."""
        # Use known correct Italian animal names to avoid submitting wrong answers
        # (wrong answers would reset the consecutive counter)
        correct_answers = ["Cane", "Gatto", "Gallina", "Mucca", "Pecora",
                           "Maiale", "Cavallo", "Coniglio", "Anatra", "Topo"]
        headers = _register_and_header()
        for idx, name in enumerate(correct_answers):
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": name,
            })
        assert "no_hints_10" in resp.json()["newAchievements"]

    def test_wrong_answer_resets_no_hints_counter(self):
        """A wrong answer resets the consecutive no-hint counter."""
        headers = _register_and_header()
        # Answer 9 correctly without hints
        for idx in range(9):
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": correct,
            })
        # Submit a wrong answer to reset the counter
        client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 9, "answer": "wronganswer",
        })
        # Submit the 10th correct — counter starts from 1, not 10
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 9, "answer": "wrong",
        })
        correct = resp.json()["correctAnswer"]
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 9, "answer": correct,
        })
        assert "no_hints_10" not in resp.json()["newAchievements"]

    def test_definitions_include_all_expected_ids(self):
        """Achievement definitions include all 9 expected IDs."""
        headers = _register_and_header()
        resp = client.get("/api/v1/users/me/achievements", headers=headers)
        ids = {d["id"] for d in resp.json()["definitions"]}
        expected = {
            "first_correct", "level_perfect", "level_speed",
            "streak_7", "streak_30", "coins_500",
            "all_levels", "daily_10", "no_hints_10",
        }
        assert ids == expected

    def test_level_perfect_achievement(self):
        """level_perfect is awarded when a level is completed with no hints or letters."""
        from app.db.user_store import get_store
        token = _next_token()
        _register(token, username="perfectuser")
        h = _auth_header(token)
        store = get_store()
        store.ensure_progress(token)

        # Complete all animals in level 1 without hints
        correct_answers = ["Cane", "Gatto", "Gallina", "Mucca", "Pecora",
                           "Maiale", "Cavallo", "Coniglio", "Anatra", "Topo",
                           "Orso", "Leone", "Tigre", "Elefante", "Giraffa",
                           "Zebra", "Scimmia", "Pinguino", "Delfino", "Squalo"]
        last_resp = None
        for idx, name in enumerate(correct_answers):
            last_resp = client.post("/api/v1/quiz/answer", headers=h, json={
                "levelId": 1, "animalIndex": idx, "answer": name,
            })
            if not last_resp.json().get("correct"):
                # Get correct name from response and retry
                correct = last_resp.json()["correctAnswer"]
                last_resp = client.post("/api/v1/quiz/answer", headers=h, json={
                    "levelId": 1, "animalIndex": idx, "answer": correct,
                })

        ach_resp = client.get("/api/v1/users/me/achievements", headers=h)
        unlocked_ids = [a["id"] for a in ach_resp.json()["unlocked"]]
        assert "level_perfect" in unlocked_ids

    def test_level_perfect_not_awarded_with_hints(self):
        """level_perfect is NOT awarded when hints were used during the level."""
        from app.db.user_store import get_store
        token = _next_token()
        _register(token, username="hintuser")
        h = _auth_header(token)
        store = get_store()
        store.ensure_progress(token)

        # Answer animal 0 correctly to earn coins
        client.post("/api/v1/quiz/answer", headers=h, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        # Buy a hint for animal 1
        client.post("/api/v1/quiz/buy-hint", headers=h, json={
            "levelId": 1, "animalIndex": 1,
        })
        # Complete the rest of level 1 (use correct answers for remaining animals)
        for idx in range(1, 20):
            resp = client.post("/api/v1/quiz/answer", headers=h, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=h, json={
                "levelId": 1, "animalIndex": idx, "answer": correct,
            })

        ach_resp = client.get("/api/v1/users/me/achievements", headers=h)
        unlocked_ids = [a["id"] for a in ach_resp.json()["unlocked"]]
        assert "level_perfect" not in unlocked_ids

    def test_streak_30_achievement(self):
        """streak_30 is awarded when current_streak reaches 30."""
        from app.db.user_store import get_store
        from datetime import date, timedelta
        token = _next_token()
        _register(token, username="streak30user")
        h = _auth_header(token)
        store = get_store()
        store.update_user(token, current_streak=29, last_activity_date=(date.today() - timedelta(days=1)).isoformat())

        resp = client.post("/api/v1/quiz/answer", headers=h, json={
            "levelId": 1, "animalIndex": 0, "answer": "Cane",
        })
        assert resp.status_code == 200
        assert "streak_30" in resp.json()["newAchievements"]

    def test_all_levels_achievement(self):
        """all_levels is awarded when every level is at least 80% complete."""
        from app.db.user_store import get_store
        from app.services.level_service import get_level_ids, get_level_animal_count
        token = _next_token()
        _register(token, username="alllevelsuser")
        h = _auth_header(token)
        store = get_store()
        store.ensure_progress(token)

        # Pre-set levels 2–6 (or all non-level-1 levels) to 80%+ completion
        level_ids = get_level_ids()
        for lid in level_ids:
            if lid == 1:
                continue
            count = get_level_animal_count(lid)
            needed = int(count * 0.8)
            bools = [True] * needed + [False] * (count - needed)
            store._progress[token][lid] = bools

        # Complete level 1 via API (20 animals)
        for idx in range(20):
            resp = client.post("/api/v1/quiz/answer", headers=h, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=h, json={
                "levelId": 1, "animalIndex": idx, "answer": correct,
            })

        ach_resp = client.get("/api/v1/users/me/achievements", headers=h)
        unlocked_ids = [a["id"] for a in ach_resp.json()["unlocked"]]
        assert "all_levels" in unlocked_ids

    def test_daily_10_achievement(self):
        """daily_10 is awarded after completing 10 daily challenges."""
        from app.db.user_store import get_store
        token = _next_token()
        _register(token, username="daily10user")
        h = _auth_header(token)
        store = get_store()
        store.update_user(token, daily_challenges_completed=9)

        # Complete one daily challenge
        today = client.get("/api/v1/challenge/today", headers=h).json()
        for idx, animal in enumerate(today["animals"]):
            client.post("/api/v1/challenge/answer", headers=h, json={
                "animalIndex": idx,
                "answer": animal["name"],
            })

        ach_resp = client.get("/api/v1/users/me/achievements", headers=h)
        unlocked_ids = [a["id"] for a in ach_resp.json()["unlocked"]]
        assert "daily_10" in unlocked_ids

    def test_report_level_speed_achievement(self):
        """POST /users/me/achievements/report with level_speed unlocks it once."""
        headers = _register_and_header()
        resp = client.post("/api/v1/users/me/achievements/report", headers=headers, json={
            "achievementId": "level_speed",
        })
        assert resp.status_code == 200
        assert resp.json()["unlocked"] is True

        # Second call — already unlocked
        resp2 = client.post("/api/v1/users/me/achievements/report", headers=headers, json={
            "achievementId": "level_speed",
        })
        assert resp2.status_code == 200
        assert resp2.json()["unlocked"] is False

    def test_report_invalid_achievement_rejected(self):
        """POST /users/me/achievements/report with an unknown ID returns 400."""
        headers = _register_and_header()
        resp = client.post("/api/v1/users/me/achievements/report", headers=headers, json={
            "achievementId": "first_correct",
        })
        assert resp.status_code == 400
