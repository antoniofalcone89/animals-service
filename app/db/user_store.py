"""Pluggable user storage: in-memory for dev/test, Firestore for production.

``get_store()`` returns a singleton whose concrete type depends on whether
the app is running in mock mode.
"""

import abc
import logging
from datetime import date, datetime, timedelta, timezone

from google.cloud.firestore_v1 import DocumentReference, Transaction

from app.db.firestore import get_firestore_client, is_mock_mode
from app.services.level_service import get_level_animal_count, get_level_ids

logger = logging.getLogger(__name__)


def _empty_progress() -> dict[int, list[bool]]:
    """Return fresh progress for every level (all False)."""
    return {
        lid: [False] * get_level_animal_count(lid)
        for lid in get_level_ids()
    }


def _compute_streak_after_first_correct(
    last_activity_date: str | None,
    current_streak: int,
    today: date,
) -> tuple[int, str]:
    """Return updated ``(current_streak, last_activity_date)`` for first daily correct answer."""
    today_iso = today.isoformat()
    if last_activity_date == today_iso:
        return current_streak, today_iso

    try:
        previous = date.fromisoformat(last_activity_date) if last_activity_date else None
    except ValueError:
        previous = None

    if previous == today - timedelta(days=1):
        return max(0, current_streak) + 1, today_iso

    return 1, today_iso


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class UserStore(abc.ABC):
    """Common interface for user persistence."""

    @abc.abstractmethod
    def create_user(
        self,
        uid: str,
        email: str | None,
        username: str,
        photo_url: str | None = None,
    ) -> dict:
        """Create a new user profile. Raises ``ValueError`` if exists."""

    @abc.abstractmethod
    def get_user(self, uid: str) -> dict | None:
        """Return user profile by UID."""

    @abc.abstractmethod
    def update_user(self, uid: str, **fields) -> dict | None:
        """Update profile fields and return the updated document."""

    @abc.abstractmethod
    def get_all_users(self) -> dict[str, dict]:
        """Return all users keyed by UID.

        Each value must include ``username``, ``total_coins``,
        ``total_points``, and ``progress`` (``{level_id: [bool, ...]}``)
        so that callers can compute leaderboard data without extra reads.
        """

    @abc.abstractmethod
    def ensure_progress(self, uid: str) -> dict[int, list[bool]]:
        """Lazy-init and return progress ``{level_id: [bool, ...]}``."""

    @abc.abstractmethod
    def submit_answer_update(
        self, uid: str, level_id: int, animal_index: int,
        coins_per_correct: int, points_awarded: int = 0,
    ) -> tuple[int, int, int, int, str | None]:
        """Atomically mark an animal as guessed and award coins + points.

        Returns ``(coins_awarded, total_coins, total_points, current_streak, last_activity_date)``.
        """

    @abc.abstractmethod
    def get_coins(self, uid: str) -> int:
        """Return total coins for a user."""

    @abc.abstractmethod
    def get_points(self, uid: str) -> int:
        """Return total points for a user."""

    @abc.abstractmethod
    def buy_hint(
        self, uid: str, level_id: int, animal_index: int, hint_costs: list[int],
    ) -> tuple[int, int]:
        """Atomically deduct coins and reveal a hint.

        Returns ``(hints_revealed, total_coins)``.
        Raises ``ValueError("insufficient_coins")`` or ``ValueError("max_hints_reached")``.
        """

    @abc.abstractmethod
    def get_hints(self, uid: str) -> dict[int, list[int]]:
        """Return hints revealed per level ``{level_id: [count, ...]}``."""

    @abc.abstractmethod
    def reveal_letter(
        self, uid: str, level_id: int, animal_index: int, cost: int, max_reveals: int,
    ) -> tuple[int, int]:
        """Atomically deduct coins and reveal a letter.

        Returns ``(letters_revealed, total_coins)``.
        Raises ``ValueError("insufficient_coins")`` or ``ValueError("max_reveals_reached")``.
        """

    @abc.abstractmethod
    def get_letters(self, uid: str) -> dict[int, list[int]]:
        """Return letters revealed per level ``{level_id: [count, ...]}``."""

    @abc.abstractmethod
    def count_completed(self, uid: str) -> int:
        """Return the number of fully-completed levels."""


# ---------------------------------------------------------------------------
# In-memory implementation (mock / test mode)
# ---------------------------------------------------------------------------

class InMemoryUserStore(UserStore):
    """Dict-backed store — identical behaviour to the original code."""

    def __init__(self) -> None:
        self._users: dict[str, dict] = {}
        self._progress: dict[str, dict[int, list[bool]]] = {}
        self._coins: dict[str, int] = {}
        self._points: dict[str, int] = {}
        self._hints: dict[str, dict[int, list[int]]] = {}
        self._letters: dict[str, dict[int, list[int]]] = {}

    def create_user(
        self,
        uid: str,
        email: str | None,
        username: str,
        photo_url: str | None = None,
    ) -> dict:
        if uid in self._users:
            raise ValueError("user_already_exists")
        now = datetime.now(timezone.utc)
        user_data = {
            "id": uid,
            "username": username,
            "email": email,
            "total_coins": 0,
            "created_at": now,
            "photo_url": photo_url,
            "current_streak": 0,
            "last_activity_date": None,
        }
        self._users[uid] = user_data
        logger.info("Created user profile for %s", uid)
        return user_data

    def get_user(self, uid: str) -> dict | None:
        return self._users.get(uid)

    def update_user(self, uid: str, **fields) -> dict | None:
        user_data = self._users.get(uid)
        if user_data is None:
            return None
        user_data.update(fields)
        return user_data

    def get_all_users(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for uid, data in self._users.items():
            result[uid] = {
                **data,
                "total_coins": self._coins.get(uid, 0),
                "total_points": self._points.get(uid, 0),
                "progress": self._ensure_progress(uid),
            }
        return result

    # -- progress / quiz --

    def _ensure_progress(self, uid: str) -> dict[int, list[bool]]:
        if uid not in self._progress:
            self._progress[uid] = _empty_progress()
            self._coins.setdefault(uid, 0)
            self._points.setdefault(uid, 0)
        return self._progress[uid]

    def ensure_progress(self, uid: str) -> dict[int, list[bool]]:
        return self._ensure_progress(uid)

    def submit_answer_update(
        self, uid: str, level_id: int, animal_index: int,
        coins_per_correct: int, points_awarded: int = 0,
    ) -> tuple[int, int, int, int, str | None]:
        progress = self._ensure_progress(uid)
        level_progress = progress.get(level_id)
        if level_progress is None or animal_index >= len(level_progress):
            raise ValueError("invalid level/index")
        coins_awarded = 0
        if not level_progress[animal_index]:
            level_progress[animal_index] = True
            coins_awarded = coins_per_correct
            self._coins[uid] = self._coins.get(uid, 0) + coins_awarded
            self._points[uid] = self._points.get(uid, 0) + points_awarded

            user_data = self._users.get(uid)
            if user_data is not None:
                next_streak, next_date = _compute_streak_after_first_correct(
                    user_data.get("last_activity_date"),
                    int(user_data.get("current_streak", 0) or 0),
                    datetime.now(timezone.utc).date(),
                )
                user_data["current_streak"] = next_streak
                user_data["last_activity_date"] = next_date

        user_data = self._users.get(uid) or {}
        return (
            coins_awarded,
            self._coins.get(uid, 0),
            self._points.get(uid, 0),
            int(user_data.get("current_streak", 0) or 0),
            user_data.get("last_activity_date"),
        )

    def get_coins(self, uid: str) -> int:
        self._ensure_progress(uid)
        return self._coins.get(uid, 0)

    def get_points(self, uid: str) -> int:
        self._ensure_progress(uid)
        return self._points.get(uid, 0)

    def _ensure_hints(self, uid: str) -> dict[int, list[int]]:
        """Lazy-init hints tracking (mirrors _ensure_progress)."""
        if uid not in self._hints:
            self._hints[uid] = {
                lid: [0] * get_level_animal_count(lid)
                for lid in get_level_ids()
            }
        return self._hints[uid]

    def buy_hint(
        self, uid: str, level_id: int, animal_index: int, hint_costs: list[int],
    ) -> tuple[int, int]:
        self._ensure_progress(uid)
        hints = self._ensure_hints(uid)
        level_hints = hints.get(level_id)
        if level_hints is None or animal_index >= len(level_hints):
            raise ValueError("invalid level/index")
        current_count = level_hints[animal_index]
        if current_count >= len(hint_costs):
            raise ValueError("max_hints_reached")
        cost = hint_costs[current_count]
        current_coins = self._coins.get(uid, 0)
        if current_coins < cost:
            raise ValueError("insufficient_coins")
        self._coins[uid] = current_coins - cost
        level_hints[animal_index] = current_count + 1
        return level_hints[animal_index], self._coins[uid]

    def get_hints(self, uid: str) -> dict[int, list[int]]:
        return self._ensure_hints(uid)

    def _ensure_letters(self, uid: str) -> dict[int, list[int]]:
        """Lazy-init letters tracking (mirrors _ensure_hints)."""
        if uid not in self._letters:
            self._letters[uid] = {
                lid: [0] * get_level_animal_count(lid)
                for lid in get_level_ids()
            }
        return self._letters[uid]

    def reveal_letter(
        self, uid: str, level_id: int, animal_index: int, cost: int, max_reveals: int,
    ) -> tuple[int, int]:
        self._ensure_progress(uid)
        letters = self._ensure_letters(uid)
        level_letters = letters.get(level_id)
        if level_letters is None or animal_index >= len(level_letters):
            raise ValueError("invalid level/index")
        current_count = level_letters[animal_index]
        if current_count >= max_reveals:
            raise ValueError("max_reveals_reached")
        current_coins = self._coins.get(uid, 0)
        if current_coins < cost:
            raise ValueError("insufficient_coins")
        self._coins[uid] = current_coins - cost
        level_letters[animal_index] = current_count + 1
        return level_letters[animal_index], self._coins[uid]

    def get_letters(self, uid: str) -> dict[int, list[int]]:
        return self._ensure_letters(uid)

    def count_completed(self, uid: str) -> int:
        progress = self._ensure_progress(uid)
        return sum(1 for bools in progress.values() if bools and all(bools))


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------

class FirestoreUserStore(UserStore):
    """Firestore-backed store using ``users/{uid}`` documents."""

    COLLECTION = "users"

    def _ref(self, uid: str) -> DocumentReference:
        return get_firestore_client().collection(self.COLLECTION).document(uid)

    def create_user(
        self,
        uid: str,
        email: str | None,
        username: str,
        photo_url: str | None = None,
    ) -> dict:
        ref = self._ref(uid)
        snap = ref.get()
        if snap.exists:
            raise ValueError("user_already_exists")
        now = datetime.now(timezone.utc)
        progress = {str(lid): bools for lid, bools in _empty_progress().items()}
        doc = {
            "username": username,
            "email": email,
            "total_coins": 0,
            "total_points": 0,
            "created_at": now,
            "photo_url": photo_url,
            "current_streak": 0,
            "last_activity_date": None,
            "progress": progress,
        }
        ref.set(doc)
        logger.info("Created Firestore user doc for %s", uid)
        return {"id": uid, **doc, "created_at": now}

    def get_user(self, uid: str) -> dict | None:
        snap = self._ref(uid).get()
        if not snap.exists:
            return None
        data = snap.to_dict()
        data["id"] = uid
        return data

    def update_user(self, uid: str, **fields) -> dict | None:
        ref = self._ref(uid)
        snap = ref.get()
        if not snap.exists:
            return None
        ref.update(fields)
        updated = ref.get().to_dict()
        updated["id"] = uid
        return updated

    def get_all_users(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for doc in get_firestore_client().collection(self.COLLECTION).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            # Normalise progress keys to int for callers that expect int keys
            raw_progress = data.get("progress", {})
            data["progress"] = {int(k): v for k, v in raw_progress.items()}
            result[doc.id] = data
        return result

    def ensure_progress(self, uid: str) -> dict[int, list[bool]]:
        ref = self._ref(uid)
        snap = ref.get()
        if not snap.exists:
            progress = _empty_progress()
            ref.set({"progress": {str(k): v for k, v in progress.items()}, "total_coins": 0, "total_points": 0}, merge=True)
            return progress
        raw = snap.to_dict().get("progress", {})
        if not raw:
            progress = _empty_progress()
            ref.update({"progress": {str(k): v for k, v in progress.items()}})
            return progress
        return {int(k): v for k, v in raw.items()}

    def submit_answer_update(
        self, uid: str, level_id: int, animal_index: int,
        coins_per_correct: int, points_awarded: int = 0,
    ) -> tuple[int, int, int, int, str | None]:
        ref = self._ref(uid)
        db = get_firestore_client()

        @firestore_transaction
        def _update(transaction: Transaction) -> tuple[int, int, int, int, str | None]:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            progress = data.get("progress", {})
            level_key = str(level_id)
            level_progress = progress.get(level_key, [False] * get_level_animal_count(level_id))
            if animal_index >= len(level_progress):
                raise ValueError("invalid animal_index")

            coins_awarded = 0
            actual_points = 0
            if not level_progress[animal_index]:
                level_progress[animal_index] = True
                coins_awarded = coins_per_correct
                actual_points = points_awarded

            total_coins = data.get("total_coins", 0) + coins_awarded
            total_points = data.get("total_points", 0) + actual_points

            next_streak = int(data.get("current_streak", 0) or 0)
            next_date = data.get("last_activity_date")
            if coins_awarded > 0:
                next_streak, next_date = _compute_streak_after_first_correct(
                    next_date,
                    next_streak,
                    datetime.now(timezone.utc).date(),
                )

            transaction.update(ref, {
                f"progress.{level_key}": level_progress,
                "total_coins": total_coins,
                "total_points": total_points,
                "current_streak": next_streak,
                "last_activity_date": next_date,
            })
            return coins_awarded, total_coins, total_points, next_streak, next_date

        return _update(db.transaction())

    def get_coins(self, uid: str) -> int:
        snap = self._ref(uid).get()
        if not snap.exists:
            return 0
        return snap.to_dict().get("total_coins", 0)

    def get_points(self, uid: str) -> int:
        snap = self._ref(uid).get()
        if not snap.exists:
            return 0
        return snap.to_dict().get("total_points", 0)

    def buy_hint(
        self, uid: str, level_id: int, animal_index: int, hint_costs: list[int],
    ) -> tuple[int, int]:
        ref = self._ref(uid)
        db = get_firestore_client()

        @firestore_transaction
        def _buy(transaction: Transaction) -> tuple[int, int]:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            hints = data.get("hints", {})
            level_key = str(level_id)
            level_hints = hints.get(level_key, [0] * get_level_animal_count(level_id))
            if animal_index >= len(level_hints):
                raise ValueError("invalid animal_index")
            current_count = level_hints[animal_index]
            if current_count >= len(hint_costs):
                raise ValueError("max_hints_reached")
            cost = hint_costs[current_count]
            total_coins = data.get("total_coins", 0)
            if total_coins < cost:
                raise ValueError("insufficient_coins")
            level_hints[animal_index] = current_count + 1
            new_total = total_coins - cost
            transaction.update(ref, {
                f"hints.{level_key}": level_hints,
                "total_coins": new_total,
            })
            return level_hints[animal_index], new_total

        return _buy(db.transaction())

    def get_hints(self, uid: str) -> dict[int, list[int]]:
        snap = self._ref(uid).get()
        if not snap.exists:
            return {}
        raw = snap.to_dict().get("hints", {})
        return {int(k): v for k, v in raw.items()}

    def reveal_letter(
        self, uid: str, level_id: int, animal_index: int, cost: int, max_reveals: int,
    ) -> tuple[int, int]:
        ref = self._ref(uid)
        db = get_firestore_client()

        @firestore_transaction
        def _reveal(transaction: Transaction) -> tuple[int, int]:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            letters = data.get("letters", {})
            level_key = str(level_id)
            level_letters = letters.get(level_key, [0] * get_level_animal_count(level_id))
            if animal_index >= len(level_letters):
                raise ValueError("invalid level/index")
            current_count = level_letters[animal_index]
            if current_count >= max_reveals:
                raise ValueError("max_reveals_reached")
            total_coins = data.get("total_coins", 0)
            if total_coins < cost:
                raise ValueError("insufficient_coins")
            level_letters[animal_index] = current_count + 1
            new_total = total_coins - cost
            transaction.update(ref, {
                f"letters.{level_key}": level_letters,
                "total_coins": new_total,
            })
            return level_letters[animal_index], new_total

        return _reveal(db.transaction())

    def get_letters(self, uid: str) -> dict[int, list[int]]:
        snap = self._ref(uid).get()
        if not snap.exists:
            return {}
        raw = snap.to_dict().get("letters", {})
        return {int(k): v for k, v in raw.items()}

    def count_completed(self, uid: str) -> int:
        snap = self._ref(uid).get()
        if not snap.exists:
            return 0
        raw = snap.to_dict().get("progress", {})
        return sum(1 for bools in raw.values() if bools and all(bools))


def firestore_transaction(func):
    """Decorator to run *func* inside a Firestore transaction."""
    from google.cloud.firestore_v1 import transactional
    return transactional(func)


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_store: UserStore | None = None


def get_store() -> UserStore:
    """Return the singleton ``UserStore`` instance."""
    global _store
    if _store is None:
        if is_mock_mode():
            logger.info("Using InMemoryUserStore (mock mode)")
            _store = InMemoryUserStore()
        else:
            logger.info("Using FirestoreUserStore")
            _store = FirestoreUserStore()
    return _store
