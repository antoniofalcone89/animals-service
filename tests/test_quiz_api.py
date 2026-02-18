"""Tests for the Quiz Academy API endpoints (auth, levels, quiz, users, leaderboard).

In mock auth mode (no FIREBASE_CREDENTIALS set), any non-empty Bearer token is
accepted and the token value is used as the user ID.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Counter for unique mock user tokens across test runs
_uid_counter = 0


def _next_token() -> str:
    """Return a unique mock Bearer token / uid for each test."""
    global _uid_counter
    _uid_counter += 1
    return f"mock-uid-{_uid_counter}"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(token: str, username: str = "testuser") -> dict:
    """Register a user profile and return the response body."""
    resp = client.post(
        "/api/v1/auth/register",
        headers=_auth_header(token),
        json={"username": username},
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
        assert data["coinsAwarded"] == 10
        assert data["totalCoins"] == 10
        assert data["correctAnswer"] == "Cane"

    def test_correct_answer_english(self):
        headers = {**_register_and_header(), "Accept-Language": "en"}
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Dog",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["coinsAwarded"] == 10

    def test_wrong_answer(self):
        headers = _register_and_header()
        resp = client.post("/api/v1/quiz/answer", headers=headers, json={
            "levelId": 1, "animalIndex": 0, "answer": "Gatto",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is False
        assert data["coinsAwarded"] == 0
        assert data["correctAnswer"] == "Cane"

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


class TestBuyHint:
    """POST /api/v1/quiz/buy-hint tests."""

    def test_buy_hint_success(self):
        headers = _register_and_header()
        # Earn 10 coins via a correct answer
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
        assert data["totalCoins"] == 5
        # Verify coins via GET /users/me/coins
        resp2 = client.get("/api/v1/users/me/coins", headers=headers)
        assert resp2.json()["totalCoins"] == 5

    def test_buy_hint_escalating_cost(self):
        headers = _register_and_header()
        # Earn 35 coins (answer 4 animals correctly: 4 * 10 = 40 coins)
        for idx in range(4):
            # Get the correct Italian name for each animal
            resp = client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": "wrong",
            })
            correct_name = resp.json()["correctAnswer"]
            client.post("/api/v1/quiz/answer", headers=headers, json={
                "levelId": 1, "animalIndex": idx, "answer": correct_name,
            })
        # Now have 40 coins. Buy 3 hints for animal 5: costs 5, 10, 20
        resp1 = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp1.json()["hintsRevealed"] == 1
        assert resp1.json()["totalCoins"] == 35  # 40 - 5

        resp2 = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp2.json()["hintsRevealed"] == 2
        assert resp2.json()["totalCoins"] == 25  # 35 - 10

        resp3 = client.post("/api/v1/quiz/buy-hint", headers=headers, json={
            "levelId": 1, "animalIndex": 5,
        })
        assert resp3.json()["hintsRevealed"] == 3
        assert resp3.json()["totalCoins"] == 5  # 25 - 20

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

    def test_leaderboard_no_auth(self):
        resp = client.get("/api/v1/leaderboard")
        assert resp.status_code in (401, 403)
