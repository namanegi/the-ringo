from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from the_ringo.memory import MemoryState, ReviewOutcome
from the_ringo.preferences import LearnerPreferences

SCHEMA_VERSION = 3


class StateConflictError(RuntimeError):
    """Raised when initialization conflicts with persisted learner state."""


@dataclass(frozen=True, slots=True)
class LearnerProfile:
    native_language: str
    target_language: str
    created_at: str


class LocalState:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self, native_language: str, target_language: str) -> LearnerProfile:
        native_language = _require_language_tag(native_language, "native language")
        target_language = _require_language_tag(target_language, "target language")

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            existing = self._read_profile(connection)
            if existing is not None:
                requested = (native_language, target_language)
                persisted = (existing.native_language, existing.target_language)
                if requested != persisted:
                    raise StateConflictError(
                        "learner state already exists for "
                        f"{existing.native_language} -> {existing.target_language}"
                    )
                return existing

            created_at = _utc_now()
            profile = LearnerProfile(
                native_language=native_language,
                target_language=target_language,
                created_at=created_at,
            )
            connection.execute(
                """
                INSERT INTO learner_profile (
                    singleton, native_language, target_language, created_at
                ) VALUES (1, ?, ?, ?)
                """,
                (native_language, target_language, created_at),
            )
            self._write_preferences(connection, LearnerPreferences())
            self._append_event(
                connection,
                kind="learner_initialized",
                payload={
                    "native_language": native_language,
                    "target_language": target_language,
                },
            )
            return profile

    def get_preferences(self) -> LearnerPreferences:
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            if self._read_profile(connection) is None:
                raise RuntimeError("learner state is not initialized")
            row = connection.execute(
                """
                SELECT daily_items, new_content_ratio, explanation_style
                FROM learner_preferences WHERE singleton = 1
                """
            ).fetchone()
        if row is None:
            return LearnerPreferences()
        return LearnerPreferences(row[0], row[1], row[2])

    def save_preferences(self, preferences: LearnerPreferences) -> LearnerPreferences:
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            if self._read_profile(connection) is None:
                raise RuntimeError("learner state is not initialized")
            self._write_preferences(connection, preferences)
            return preferences

    def inspect(self) -> dict[str, Any]:
        if not self.database_path.exists():
            return {
                "initialized": False,
                "database_path": str(self.database_path.resolve()),
                "schema_version": None,
                "profile": None,
                "event_count": 0,
                "preferences": None,
            }

        with self._connect() as connection:
            self._create_schema(connection)
            profile = self._read_profile(connection)
            event_count = connection.execute(
                "SELECT COUNT(*) FROM event_log"
            ).fetchone()[0]
            return {
                "initialized": profile is not None,
                "database_path": str(self.database_path.resolve()),
                "schema_version": SCHEMA_VERSION,
                "profile": asdict(profile) if profile is not None else None,
                "event_count": event_count,
                "preferences": (
                    self._read_preferences(connection)
                    if profile is not None
                    else None
                ),
            }

    def get_memory(self, concept_id: str) -> MemoryState:
        """Return a concept's memory state, or an unseen state if absent."""
        if not concept_id.strip():
            raise ValueError("concept id must not be empty")
        if not self.database_path.exists():
            return MemoryState.unseen(concept_id)

        with self._connect() as connection:
            self._create_schema(connection)
            row = connection.execute(
                """
                SELECT concept_id, interval_days, due_at, streak, last_outcome
                FROM memory_state WHERE concept_id = ?
                """,
                (concept_id,),
            ).fetchone()
        if row is None:
            return MemoryState.unseen(concept_id)
        return MemoryState(
            concept_id=row[0],
            interval_days=row[1],
            due_at=_parse_datetime(row[2]),
            streak=row[3],
            last_outcome=ReviewOutcome(row[4]) if row[4] is not None else None,
        )

    def save_memory(self, state: MemoryState) -> None:
        """Persist memory and its compact review event in one transaction."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            connection.execute(
                """
                INSERT INTO memory_state (
                    concept_id, interval_days, due_at, streak, last_outcome
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(concept_id) DO UPDATE SET
                    interval_days = excluded.interval_days,
                    due_at = excluded.due_at,
                    streak = excluded.streak,
                    last_outcome = excluded.last_outcome
                """,
                (
                    state.concept_id,
                    state.interval_days,
                    _format_datetime(state.due_at),
                    state.streak,
                    state.last_outcome.value if state.last_outcome else None,
                ),
            )
            self._append_event(
                connection,
                kind="review_recorded",
                payload={
                    "concept_id": state.concept_id,
                    "outcome": state.last_outcome.value
                    if state.last_outcome is not None
                    else None,
                    "interval_days": state.interval_days,
                    "streak": state.streak,
                },
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learner_profile (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                native_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_log (
                event_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        version_row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        version = int(version_row[0]) if version_row is not None else 1
        if version == 1:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_state (
                    concept_id TEXT PRIMARY KEY,
                    interval_days INTEGER NOT NULL CHECK (interval_days >= 0),
                    due_at TEXT,
                    streak INTEGER NOT NULL CHECK (streak >= 0),
                    last_outcome TEXT
                )
                """
            )
            version = 2
        if version == 2:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_preferences (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    daily_items INTEGER NOT NULL CHECK (daily_items BETWEEN 1 AND 100),
                    new_content_ratio REAL NOT NULL
                        CHECK (new_content_ratio BETWEEN 0 AND 1),
                    explanation_style TEXT NOT NULL
                )
                """
            )
            if connection.execute(
                "SELECT 1 FROM learner_profile WHERE singleton = 1"
            ).fetchone() is not None:
                LocalState._write_preferences(connection, LearnerPreferences())
            version = 3
        if version != SCHEMA_VERSION:
            raise RuntimeError(f"unsupported state schema version: {version}")
        connection.execute(
            """
            INSERT INTO metadata (key, value) VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(SCHEMA_VERSION),),
        )

    @staticmethod
    def _read_profile(connection: sqlite3.Connection) -> LearnerProfile | None:
        row = connection.execute(
            """
            SELECT native_language, target_language, created_at
            FROM learner_profile WHERE singleton = 1
            """
        ).fetchone()
        if row is None:
            return None
        return LearnerProfile(
            native_language=row[0],
            target_language=row[1],
            created_at=row[2],
        )

    @staticmethod
    def _read_preferences(connection: sqlite3.Connection) -> dict[str, object]:
        row = connection.execute(
            """
            SELECT daily_items, new_content_ratio, explanation_style
            FROM learner_preferences WHERE singleton = 1
            """
        ).fetchone()
        preferences = (
            LearnerPreferences(*row) if row is not None else LearnerPreferences()
        )
        return {
            "daily_items": preferences.daily_items,
            "new_content_ratio": preferences.new_content_ratio,
            "explanation_style": preferences.explanation_style,
        }

    @staticmethod
    def _write_preferences(
        connection: sqlite3.Connection, preferences: LearnerPreferences
    ) -> None:
        connection.execute(
            """
            INSERT INTO learner_preferences (
                singleton, daily_items, new_content_ratio, explanation_style
            ) VALUES (1, ?, ?, ?)
            ON CONFLICT(singleton) DO UPDATE SET
                daily_items = excluded.daily_items,
                new_content_ratio = excluded.new_content_ratio,
                explanation_style = excluded.explanation_style
            """,
            (
                preferences.daily_items,
                preferences.new_content_ratio,
                preferences.explanation_style,
            ),
        )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection, kind: str, payload: dict[str, Any]
    ) -> None:
        connection.execute(
            """
            INSERT INTO event_log (event_id, kind, occurred_at, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                kind,
                _utc_now(),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )


def _require_language_tag(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if any(character.isspace() for character in normalized):
        raise ValueError(f"{label} must be a language tag without spaces")
    return normalized


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
    return value.astimezone(UTC).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("stored datetime must be timezone-aware UTC")
    return parsed.astimezone(UTC)
