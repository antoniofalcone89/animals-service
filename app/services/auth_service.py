"""Authentication service backed by Firebase Admin SDK.

When ``FIREBASE_CREDENTIALS`` is set, tokens are verified against Firebase.
Otherwise the service runs in **mock auth mode** for local development and
testing — any non-empty Bearer token is accepted, and the token value itself
is used as the user ID.
"""

import logging

from firebase_admin import auth as firebase_auth

from app.db.firestore import get_firebase_app, is_mock_mode
from app.db.user_store import get_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

def verify_token(token: str) -> dict | None:
    """Verify a Bearer token and return decoded claims.

    Returns a dict with ``uid``, ``email``, and ``name`` keys, or *None*
    when the token is invalid / expired.
    """
    if is_mock_mode():
        return _verify_mock_token(token)

    try:
        decoded = firebase_auth.verify_id_token(token, app=get_firebase_app())
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
# User storage — delegated to UserStore
# ---------------------------------------------------------------------------

def create_user(uid: str, email: str, username: str) -> dict:
    """Create a new user profile.

    Raises ``ValueError`` if a profile for *uid* already exists.
    """
    return get_store().create_user(uid, email, username)


def get_user(uid: str) -> dict | None:
    """Return user profile by UID."""
    return get_store().get_user(uid)


def update_user(uid: str, **fields) -> dict | None:
    """Update user profile fields and return the updated document."""
    return get_store().update_user(uid, **fields)


def get_all_users() -> dict[str, dict]:
    """Return all user profiles (for leaderboard)."""
    return get_store().get_all_users()
