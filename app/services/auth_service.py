"""Authentication service backed by Firebase Admin SDK.

When ``FIREBASE_CREDENTIALS`` is set, tokens are verified against Firebase.
Otherwise the service runs in **mock auth mode** for local development and
testing — any non-empty Bearer token is accepted, and the token value itself
is used as the user ID.
"""

import logging
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firebase initialisation (lazy — runs once on first verify_token call)
# ---------------------------------------------------------------------------
_firebase_app: firebase_admin.App | None = None
_mock_mode: bool = False
_initialized: bool = False


def _ensure_initialized() -> None:
    """Initialise Firebase on first use. Falls back to mock mode."""
    global _firebase_app, _mock_mode, _initialized
    if _initialized:
        return
    _initialized = True

    if settings.FIREBASE_CREDENTIALS:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialised")
    else:
        _mock_mode = True
        logger.warning(
            "FIREBASE_CREDENTIALS not set — running in mock auth mode. "
            "Set FIREBASE_CREDENTIALS to a service-account JSON path for production."
        )


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

def verify_token(token: str) -> dict | None:
    """Verify a Bearer token and return decoded claims.

    Returns a dict with ``uid``, ``email``, and ``name`` keys, or *None*
    when the token is invalid / expired.
    """
    _ensure_initialized()

    if _mock_mode:
        return _verify_mock_token(token)

    try:
        decoded = firebase_auth.verify_id_token(token, app=_firebase_app)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email", ""),
            "name": decoded.get("name", ""),
        }
    except Exception as e:
        logger.warning("Firebase token verification failed: %s", e)
        return None


def _verify_mock_token(token: str) -> dict | None:
    """Accept any non-empty token in mock mode. The value *is* the uid."""
    if not token:
        return None
    return {"uid": token, "email": f"{token}@mock.local", "name": ""}


# ---------------------------------------------------------------------------
# User storage — TODO: Replace with Firestore
# ---------------------------------------------------------------------------
_users: dict[str, dict] = {}  # uid -> user data


def create_user(uid: str, email: str, username: str) -> dict:
    """Create a new user profile.

    Raises ``ValueError`` if a profile for *uid* already exists.

    TODO: Replace with Firestore ``set('users/{uid}', ...)``.
    """
    if uid in _users:
        raise ValueError("user_already_exists")

    now = datetime.now(timezone.utc)
    user_data = {
        "id": uid,
        "username": username,
        "email": email,
        "total_coins": 0,
        "created_at": now,
    }
    _users[uid] = user_data
    logger.info("Created user profile for %s", uid)
    return user_data


def get_user(uid: str) -> dict | None:
    """Return user profile by UID.

    TODO: Replace with Firestore ``get('users/{uid}')``.
    """
    return _users.get(uid)


def update_user(uid: str, **fields) -> dict | None:
    """Update user profile fields and return the updated document.

    TODO: Replace with Firestore ``update('users/{uid}', ...)``.
    """
    user_data = _users.get(uid)
    if user_data is None:
        return None
    user_data.update(fields)
    return user_data


def get_all_users() -> dict[str, dict]:
    """Return all user profiles (for leaderboard).

    TODO: Replace with a Firestore query ordered by totalCoins.
    """
    return _users
