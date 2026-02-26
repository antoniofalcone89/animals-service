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


def _get_admin_user_profile(uid: str) -> dict[str, str | None] | None:
    """Return user profile from Firebase Auth Admin SDK, or None if unavailable."""
    if is_mock_mode():
        return None

    try:
        record = firebase_auth.get_user(uid, app=get_firebase_app())
        return {
            "email": record.email,
            "photo_url": record.photo_url,
        }
    except Exception as e:
        logger.warning("Failed to fetch Firebase user record for %s: %s", uid, e)
        return None


def get_user_photo_url(uid: str) -> str | None:
    """Return the Firebase Auth photo URL for a user, if available."""
    profile = _get_admin_user_profile(uid)
    if profile is None:
        return None
    return profile.get("photo_url")


# ---------------------------------------------------------------------------
# User storage — delegated to UserStore
# ---------------------------------------------------------------------------

def create_user(
    uid: str,
    email: str | None,
    username: str,
    photo_url: str | None = None,
) -> dict:
    """Create a new user profile.

    Raises ``ValueError`` if a profile for *uid* already exists.
    """
    admin_profile = _get_admin_user_profile(uid)
    resolved_email = email
    resolved_photo_url = photo_url

    if admin_profile is not None:
        if admin_profile.get("email") is not None:
            resolved_email = admin_profile["email"]
        if admin_profile.get("photo_url") is not None:
            resolved_photo_url = admin_profile["photo_url"]

    return get_store().create_user(uid, resolved_email, username, resolved_photo_url)


def get_user(uid: str) -> dict | None:
    """Return user profile by UID."""
    return get_store().get_user(uid)


def update_user(uid: str, **fields) -> dict | None:
    """Update user profile fields and return the updated document."""
    return get_store().update_user(uid, **fields)


def get_all_users() -> dict[str, dict]:
    """Return all user profiles (for leaderboard)."""
    return get_store().get_all_users()
