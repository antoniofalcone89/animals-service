"""Firebase Admin SDK and Firestore client initialisation.

Lazy-initialised on first use.  When ``FIREBASE_CREDENTIALS`` is not set the
module enters **mock mode** — no real Firebase/Firestore calls are made.

``FIREBASE_CREDENTIALS`` accepts either a **file path** to a service-account
JSON file or the **raw JSON string** itself (useful for container secrets).
"""

import json
import logging

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (lazy init)
# ---------------------------------------------------------------------------
_firebase_app: firebase_admin.App | None = None
_firestore_client = None  # google.cloud.firestore_v1.client.Client | None
_mock_mode: bool = False
_initialized: bool = False


def _load_credentials(value: str) -> credentials.Certificate:
    """Build a Certificate from a file path or inline JSON string."""
    stripped = value.strip()
    if stripped.startswith("{"):
        return credentials.Certificate(json.loads(stripped))
    return credentials.Certificate(stripped)


def _ensure_initialized() -> None:
    """Initialise Firebase + Firestore on first use."""
    global _firebase_app, _firestore_client, _mock_mode, _initialized
    if _initialized:
        return
    _initialized = True

    if settings.FIREBASE_CREDENTIALS:
        try:
            cred = _load_credentials(settings.FIREBASE_CREDENTIALS)
            _firebase_app = firebase_admin.initialize_app(cred)
            _firestore_client = firestore.client(app=_firebase_app)
            logger.info("Firebase Admin SDK + Firestore initialised")
        except Exception as e:
            _mock_mode = True
            logger.warning(
                "Failed to initialise Firebase (%s) — falling back to mock mode.", e
            )
    else:
        _mock_mode = True
        logger.warning(
            "FIREBASE_CREDENTIALS not set — running in mock mode. "
            "Set FIREBASE_CREDENTIALS to a service-account JSON path or raw JSON string for production."
        )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_mock_mode() -> bool:
    """Return *True* when running without real Firebase credentials."""
    _ensure_initialized()
    return _mock_mode


def get_firebase_app() -> firebase_admin.App | None:
    """Return the initialised Firebase app (or *None* in mock mode)."""
    _ensure_initialized()
    return _firebase_app


def get_firestore_client():
    """Return the Firestore client (or *None* in mock mode)."""
    _ensure_initialized()
    return _firestore_client
