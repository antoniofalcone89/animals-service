"""Pluggable user storage: in-memory for dev/test, Firestore for production.

``get_store()`` returns a singleton whose concrete type depends on whether
the app is running in mock mode.
"""

import abc
import logging
from datetime import date, datetime, timedelta, timezone

from google.cloud import firestore
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
    ) -> tuple[int, int, int, int, str | None, int]:
        """Atomically mark an animal as guessed and award coins + points.

        Returns ``(coins_awarded, total_coins, total_points, current_streak, last_activity_date, streak_bonus_coins)``.
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

    @abc.abstractmethod
    def get_daily_challenge(
        self, uid: str, challenge_date: str, challenge_size: int,
    ) -> dict:
        """Return persisted daily challenge state for user/date."""

    @abc.abstractmethod
    def submit_daily_challenge_answer(
        self,
        uid: str,
        challenge_date: str,
        animal_index: int,
        points_awarded: int,
        challenge_size: int,
    ) -> tuple[int, int, bool, datetime | None]:
        """Persist a daily challenge answer.

        Returns ``(points_awarded_now, total_score, completed, completed_at)``.
        """

    @abc.abstractmethod
    def get_daily_challenge_leaderboard(self, challenge_date: str) -> list[dict]:
        """Return leaderboard rows for a specific challenge date."""

    @abc.abstractmethod
    def unlock_achievement(self, uid: str, achievement_id: str) -> bool:
        """Unlock an achievement. Returns True if newly unlocked, False if already set."""

    @abc.abstractmethod
    def get_achievements(self, uid: str) -> list[dict]:
        """Return list of ``{id, unlocked_at}`` for all unlocked achievements."""

    @abc.abstractmethod
    def get_achievements_count(self, uid: str) -> int:
        """Return count of unlocked achievements for a user."""

    @abc.abstractmethod
    def reset_user_game_data(self, uid: str) -> bool:
        """Reset gameplay state (levels, badges, points, and related counters).

        Returns ``True`` when user exists and reset is applied, else ``False``.
        """


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
        self._daily_challenges: dict[str, dict[str, dict]] = {}
        self._achievements: dict[str, dict[str, datetime]] = {}

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
            "total_answers": 0,
            "total_correct": 0,
            "total_hints_used": 0,
            "total_letters_used": 0,
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
                "achievements_count": len(self._achievements.get(uid, {})),
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
    ) -> tuple[int, int, int, int, str | None, int]:
        progress = self._ensure_progress(uid)
        level_progress = progress.get(level_id)
        if level_progress is None or animal_index >= len(level_progress):
            raise ValueError("invalid level/index")

        streak_bonus_coins = 0
        coins_awarded = 0
        if not level_progress[animal_index]:
            level_progress[animal_index] = True
            user_data = self._users.get(uid)
            if user_data is not None:
                today_iso = datetime.now(timezone.utc).date().isoformat()
                was_first_correct_today = user_data.get("last_activity_date") != today_iso
                next_streak, next_date = _compute_streak_after_first_correct(
                    user_data.get("last_activity_date"),
                    int(user_data.get("current_streak", 0) or 0),
                    datetime.now(timezone.utc).date(),
                )
                user_data["current_streak"] = next_streak
                user_data["last_activity_date"] = next_date
                user_data["total_correct"] = int(user_data.get("total_correct", 0) or 0) + 1

                if was_first_correct_today:
                    streak_bonus_coins = min(next_streak * 2, 20)

            coins_awarded = coins_per_correct + streak_bonus_coins
            self._coins[uid] = self._coins.get(uid, 0) + coins_awarded
            self._points[uid] = self._points.get(uid, 0) + points_awarded

        user_data = self._users.get(uid) or {}
        return (
            coins_awarded,
            self._coins.get(uid, 0),
            self._points.get(uid, 0),
            int(user_data.get("current_streak", 0) or 0),
            user_data.get("last_activity_date"),
            streak_bonus_coins,
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
        user_data = self._users.get(uid)
        if user_data is not None:
            user_data["total_hints_used"] = int(user_data.get("total_hints_used", 0) or 0) + 1
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
        user_data = self._users.get(uid)
        if user_data is not None:
            user_data["total_letters_used"] = int(user_data.get("total_letters_used", 0) or 0) + 1
        return level_letters[animal_index], self._coins[uid]

    def get_letters(self, uid: str) -> dict[int, list[int]]:
        return self._ensure_letters(uid)

    def count_completed(self, uid: str) -> int:
        progress = self._ensure_progress(uid)
        return sum(1 for bools in progress.values() if bools and all(bools))

    def _ensure_daily_challenge(
        self, uid: str, challenge_date: str, challenge_size: int,
    ) -> dict:
        by_user = self._daily_challenges.setdefault(uid, {})
        state = by_user.get(challenge_date)
        if state is None:
            state = {
                "answered": [False] * challenge_size,
                "score": 0,
                "completed_at": None,
            }
            by_user[challenge_date] = state
            return state

        answered = state.get("answered", [])
        if len(answered) != challenge_size:
            if len(answered) < challenge_size:
                answered = answered + [False] * (challenge_size - len(answered))
            else:
                answered = answered[:challenge_size]
            state["answered"] = answered

        state.setdefault("score", 0)
        state.setdefault("completed_at", None)
        return state

    def get_daily_challenge(
        self, uid: str, challenge_date: str, challenge_size: int,
    ) -> dict:
        state = self._ensure_daily_challenge(uid, challenge_date, challenge_size)
        return {
            "answered": list(state["answered"]),
            "score": int(state.get("score", 0) or 0),
            "completed_at": state.get("completed_at"),
        }

    def submit_daily_challenge_answer(
        self,
        uid: str,
        challenge_date: str,
        animal_index: int,
        points_awarded: int,
        challenge_size: int,
    ) -> tuple[int, int, bool, datetime | None]:
        state = self._ensure_daily_challenge(uid, challenge_date, challenge_size)
        answered = state["answered"]
        if animal_index >= len(answered):
            raise ValueError("invalid challenge/index")

        points_now = 0
        if not answered[animal_index]:
            answered[animal_index] = True
            points_now = points_awarded
            state["score"] = int(state.get("score", 0) or 0) + points_now

        completed = all(answered)
        if completed and state.get("completed_at") is None:
            state["completed_at"] = datetime.now(timezone.utc)

        return points_now, int(state.get("score", 0) or 0), completed, state.get("completed_at")

    def get_daily_challenge_leaderboard(self, challenge_date: str) -> list[dict]:
        rows: list[dict] = []
        for uid, by_date in self._daily_challenges.items():
            state = by_date.get(challenge_date)
            if state is None:
                continue
            rows.append({
                "user_id": uid,
                "score": int(state.get("score", 0) or 0),
                "completed_at": state.get("completed_at"),
            })
        return rows

    def unlock_achievement(self, uid: str, achievement_id: str) -> bool:
        achs = self._achievements.setdefault(uid, {})
        if achievement_id in achs:
            return False
        achs[achievement_id] = datetime.now(timezone.utc)
        logger.info("Achievement unlocked for %s: %s", uid, achievement_id)
        return True

    def get_achievements(self, uid: str) -> list[dict]:
        achs = self._achievements.get(uid, {})
        return [{"id": k, "unlockedAt": v.isoformat()} for k, v in achs.items()]

    def get_achievements_count(self, uid: str) -> int:
        return len(self._achievements.get(uid, {}))

    def reset_user_game_data(self, uid: str) -> bool:
        user_data = self._users.get(uid)
        if user_data is None:
            return False

        self._progress[uid] = _empty_progress()
        self._coins[uid] = 0
        self._points[uid] = 0
        self._hints[uid] = {
            lid: [0] * get_level_animal_count(lid)
            for lid in get_level_ids()
        }
        self._letters[uid] = {
            lid: [0] * get_level_animal_count(lid)
            for lid in get_level_ids()
        }
        self._daily_challenges.pop(uid, None)
        self._achievements.pop(uid, None)

        user_data["current_streak"] = 0
        user_data["last_activity_date"] = None
        user_data["consecutive_no_hint_correct"] = 0
        user_data["total_coins"] = 0
        user_data["total_points"] = 0
        user_data["total_answers"] = 0
        user_data["total_correct"] = 0
        user_data["total_hints_used"] = 0
        user_data["total_letters_used"] = 0
        return True


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------

class FirestoreUserStore(UserStore):
    """Firestore-backed store using ``users/{uid}`` documents."""

    COLLECTION = "users"
    CHALLENGE_COLLECTION = "challenges"

    def _ref(self, uid: str) -> DocumentReference:
        return get_firestore_client().collection(self.COLLECTION).document(uid)

    def _challenge_ref(self, uid: str, challenge_date: str) -> DocumentReference:
        return (
            get_firestore_client()
            .collection(self.CHALLENGE_COLLECTION)
            .document(uid)
            .collection("dates")
            .document(challenge_date)
        )

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
            "total_answers": 0,
            "total_correct": 0,
            "total_hints_used": 0,
            "total_letters_used": 0,
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
            raw_progress = data.get("progress", {})
            data["progress"] = {int(k): v for k, v in raw_progress.items()}
            data["achievements_count"] = len(data.get("achievements", {}))
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
    ) -> tuple[int, int, int, int, str | None, int]:
        ref = self._ref(uid)
        db = get_firestore_client()

        @firestore_transaction
        def _update(transaction: Transaction) -> tuple[int, int, int, int, str | None, int]:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            progress = data.get("progress", {})
            level_key = str(level_id)
            level_progress = progress.get(level_key, [False] * get_level_animal_count(level_id))
            if animal_index >= len(level_progress):
                raise ValueError("invalid animal_index")

            streak_bonus_coins = 0
            coins_awarded = 0
            actual_points = 0
            if not level_progress[animal_index]:
                level_progress[animal_index] = True
                coins_awarded = coins_per_correct
                actual_points = points_awarded

            next_streak = int(data.get("current_streak", 0) or 0)
            next_date = data.get("last_activity_date")
            if coins_awarded > 0:
                today_iso = datetime.now(timezone.utc).date().isoformat()
                was_first_correct_today = next_date != today_iso
                next_streak, next_date = _compute_streak_after_first_correct(
                    next_date,
                    next_streak,
                    datetime.now(timezone.utc).date(),
                )
                if was_first_correct_today:
                    streak_bonus_coins = min(next_streak * 2, 20)

            coins_awarded += streak_bonus_coins
            total_coins = data.get("total_coins", 0) + coins_awarded
            total_points = data.get("total_points", 0) + actual_points

            transaction.update(ref, {
                f"progress.{level_key}": level_progress,
                "total_coins": total_coins,
                "total_points": total_points,
                "current_streak": next_streak,
                "last_activity_date": next_date,
                "total_correct": firestore.Increment(1),
            })
            return coins_awarded, total_coins, total_points, next_streak, next_date, streak_bonus_coins

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
                "total_hints_used": firestore.Increment(1),
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
                "total_letters_used": firestore.Increment(1),
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

    def get_daily_challenge(
        self, uid: str, challenge_date: str, challenge_size: int,
    ) -> dict:
        snap = self._challenge_ref(uid, challenge_date).get()
        if not snap.exists:
            return {
                "answered": [False] * challenge_size,
                "score": 0,
                "completed_at": None,
            }

        data = snap.to_dict() or {}
        answered = data.get("answered", [])
        if len(answered) != challenge_size:
            if len(answered) < challenge_size:
                answered = answered + [False] * (challenge_size - len(answered))
            else:
                answered = answered[:challenge_size]

        return {
            "answered": answered,
            "score": int(data.get("score", 0) or 0),
            "completed_at": data.get("completed_at"),
        }

    def submit_daily_challenge_answer(
        self,
        uid: str,
        challenge_date: str,
        animal_index: int,
        points_awarded: int,
        challenge_size: int,
    ) -> tuple[int, int, bool, datetime | None]:
        ref = self._challenge_ref(uid, challenge_date)
        db = get_firestore_client()

        @firestore_transaction
        def _update(transaction: Transaction) -> tuple[int, int, bool, datetime | None]:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            answered = data.get("answered", [False] * challenge_size)
            if len(answered) != challenge_size:
                if len(answered) < challenge_size:
                    answered = answered + [False] * (challenge_size - len(answered))
                else:
                    answered = answered[:challenge_size]

            if animal_index >= len(answered):
                raise ValueError("invalid challenge/index")

            points_now = 0
            score = int(data.get("score", 0) or 0)
            if not answered[animal_index]:
                answered[animal_index] = True
                points_now = points_awarded
                score += points_now

            completed = all(answered)
            completed_at = data.get("completed_at")
            if completed and completed_at is None:
                completed_at = datetime.now(timezone.utc)

            transaction.set(ref, {
                "answered": answered,
                "score": score,
                "completed_at": completed_at,
            }, merge=True)
            return points_now, score, completed, completed_at

        return _update(db.transaction())

    def unlock_achievement(self, uid: str, achievement_id: str) -> bool:
        ref = self._ref(uid)
        db = get_firestore_client()

        @firestore_transaction
        def _unlock(transaction: Transaction) -> bool:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            achievements = data.get("achievements", {})
            if achievement_id in achievements:
                return False
            now = datetime.now(timezone.utc)
            transaction.update(ref, {f"achievements.{achievement_id}": now})
            logger.info("Achievement unlocked for %s: %s", uid, achievement_id)
            return True

        return _unlock(db.transaction())

    def get_achievements(self, uid: str) -> list[dict]:
        snap = self._ref(uid).get()
        if not snap.exists:
            return []
        data = snap.to_dict() or {}
        achievements = data.get("achievements", {})
        return [
            {
                "id": k,
                "unlockedAt": v.isoformat() if isinstance(v, datetime) else str(v),
            }
            for k, v in achievements.items()
        ]

    def get_achievements_count(self, uid: str) -> int:
        snap = self._ref(uid).get()
        if not snap.exists:
            return 0
        return len((snap.to_dict() or {}).get("achievements", {}))

    def get_daily_challenge_leaderboard(self, challenge_date: str) -> list[dict]:
        rows: list[dict] = []
        db = get_firestore_client()
        # Stream all date docs across all users; filter by date in Python.
        # Path structure: challenges/{uid}/dates/{date}
        for doc in db.collection_group("dates").stream():
            path_parts = doc.reference.path.split("/")
            if (
                len(path_parts) != 4
                or path_parts[0] != self.CHALLENGE_COLLECTION
                or path_parts[2] != "dates"
                or path_parts[3] != challenge_date
            ):
                continue
            uid = path_parts[1]
            data = doc.to_dict() or {}
            rows.append({
                "user_id": uid,
                "score": int(data.get("score", 0) or 0),
                "completed_at": data.get("completed_at"),
            })
        return rows

    def reset_user_game_data(self, uid: str) -> bool:
        ref = self._ref(uid)
        snap = ref.get()
        if not snap.exists:
            return False

        progress = {str(lid): [False] * get_level_animal_count(lid) for lid in get_level_ids()}
        hints = {str(lid): [0] * get_level_animal_count(lid) for lid in get_level_ids()}
        letters = {str(lid): [0] * get_level_animal_count(lid) for lid in get_level_ids()}

        ref.update({
            "progress": progress,
            "hints": hints,
            "letters": letters,
            "total_coins": 0,
            "total_points": 0,
            "current_streak": 0,
            "last_activity_date": None,
            "achievements": {},
            "consecutive_no_hint_correct": 0,
            "total_answers": 0,
            "total_correct": 0,
            "total_hints_used": 0,
            "total_letters_used": 0,
        })

        db = get_firestore_client()
        batch = db.batch()
        count = 0
        for doc in db.collection(self.CHALLENGE_COLLECTION).document(uid).collection("dates").stream():
            batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = db.batch()
        if count % 400 != 0:
            batch.commit()

        return True


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
