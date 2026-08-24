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
from the_ringo.course import CoursePlan
from the_ringo.curriculum import Concept, Curriculum
from the_ringo.goal import LearningGoal
from the_ringo.pack import CurriculumPack
from the_ringo.preferences import LearnerPreferences
from the_ringo.session import SessionStatus, StudySession

SCHEMA_VERSION = 6


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

    def get_goal(self) -> LearningGoal | None:
        """Return the active goal, if the learner has set one."""
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            if self._read_profile(connection) is None:
                raise RuntimeError("learner state is not initialized")
            row = connection.execute(
                "SELECT statement FROM active_goal WHERE singleton = 1"
            ).fetchone()
        return LearningGoal(row[0]) if row is not None else None

    def set_goal(self, goal: LearningGoal) -> LearningGoal:
        """Set the active goal without disturbing existing learning state."""
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            if self._read_profile(connection) is None:
                raise RuntimeError("learner state is not initialized")
            previous = connection.execute(
                "SELECT statement FROM active_goal WHERE singleton = 1"
            ).fetchone()
            if previous is not None and previous[0] == goal.statement:
                return goal
            connection.execute(
                """
                INSERT INTO active_goal (singleton, statement)
                VALUES (1, ?)
                ON CONFLICT(singleton) DO UPDATE SET statement = excluded.statement
                """,
                (goal.statement,),
            )
            self._append_event(
                connection,
                kind=("learning_goal_set" if previous is None else "learning_goal_changed"),
                payload={
                    "statement": goal.statement,
                    "previous_statement": previous[0] if previous is not None else None,
                },
            )
        return goal

    def save_course_plan(self, plan: CoursePlan) -> CoursePlan:
        """Persist the one active, goal-bound course plan."""
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            profile = self._read_profile(connection)
            goal = self._read_goal(connection)
            if profile is None:
                raise RuntimeError("learner state is not initialized")
            if goal is None or goal != plan.goal:
                raise StateConflictError(
                    "course plan must match the active learning goal"
                )
            if profile.target_language != plan.pack.language:
                raise StateConflictError(
                    "course pack language must match learner target language"
                )
            payload = _course_plan_payload(plan)
            connection.execute(
                """
                INSERT INTO active_course_plan (singleton, payload_json)
                VALUES (1, ?)
                ON CONFLICT(singleton) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (json.dumps(payload, ensure_ascii=False, sort_keys=True),),
            )
            self._append_event(connection, "course_plan_applied", payload)
        return plan

    def get_course_plan(self) -> CoursePlan | None:
        """Load and validate the active plan against the current goal/profile."""
        if not self.database_path.exists():
            return None
        with self._connect() as connection:
            self._create_schema(connection)
            row = connection.execute(
                "SELECT payload_json FROM active_course_plan WHERE singleton = 1"
            ).fetchone()
            if row is None:
                return None
            payload = json.loads(row[0])
            goal = self._read_goal(connection)
            profile = self._read_profile(connection)
        if goal is None or payload["goal"] != goal.statement:
            raise StateConflictError(
                "active course plan does not match the active learning goal; "
                "apply a course plan for the current goal"
            )
        concepts = tuple(
            Concept(
                item["identifier"], item["title"], tuple(item["prerequisites"])
            )
            for item in payload["concepts"]
        )
        pack = CurriculumPack(
            payload["pack_id"], payload["pack_title"], payload["language"],
            Curriculum(concepts),
        )
        if tuple(item["identifier"] for item in payload["concepts"]) != tuple(
            concept.identifier for concept in pack.curriculum.ordered_concepts
        ):
            raise StateConflictError("active course plan pack has changed; re-apply it")
        if profile is not None and pack.language != profile.target_language:
            raise StateConflictError(
                "active course plan language does not match learner target language"
            )
        return CoursePlan(goal, pack)

    def get_session(self) -> StudySession | None:
        """Return the current or most recently completed session."""
        if not self.database_path.exists():
            return None
        with self._connect() as connection:
            self._create_schema(connection)
            if self._read_profile(connection) is None:
                return None
            return self._read_session(connection)

    def start_session(self, item_count: int | None = None) -> StudySession:
        """Start a bounded session, or resume the existing active one."""
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            if self._read_profile(connection) is None:
                raise RuntimeError("learner state is not initialized")
            goal = self._read_goal(connection)
            if goal is None:
                raise StateConflictError("set a learning goal before starting a session")
            current = self._read_session(connection)
            if current is not None and current.status is SessionStatus.ACTIVE:
                if item_count is not None and item_count != current.agreed_item_count:
                    raise StateConflictError(
                        "an active session already exists with "
                        f"{current.agreed_item_count} items"
                    )
                return current
            if item_count is None:
                preference_row = connection.execute(
                    "SELECT daily_items FROM learner_preferences WHERE singleton = 1"
                ).fetchone()
                count = (
                    preference_row[0]
                    if preference_row is not None
                    else LearnerPreferences().daily_items
                )
            else:
                count = item_count
            session = StudySession(str(uuid.uuid4()), goal, count)
            self._write_session(connection, session)
            self._append_event(
                connection, "study_session_started", {
                    "session_id": session.session_id,
                    "goal": goal.statement,
                    "agreed_item_count": count,
                }
            )
            return session

    def stop_session(self) -> StudySession:
        """Stop the active session while preserving its progress."""
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            session = self._read_session(connection)
            if session is None:
                raise StateConflictError("no study session exists")
            stopped = session.stop()
            if stopped != session:
                self._write_session(connection, stopped)
                self._append_event(
                    connection, "study_session_stopped", {"session_id": session.session_id}
                )
            return stopped

    def get_profile(self) -> LearnerProfile:
        """Return the initialized learner profile."""
        if not self.database_path.exists():
            raise RuntimeError("learner state is not initialized")
        with self._connect() as connection:
            self._create_schema(connection)
            profile = self._read_profile(connection)
        if profile is None:
            raise RuntimeError("learner state is not initialized")
        return profile

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
                "active_goal": None,
                "course_plan": None,
                "session": None,
            }

        with self._connect() as connection:
            self._create_schema(connection)
            profile = self._read_profile(connection)
            event_count = connection.execute(
                "SELECT COUNT(*) FROM event_log"
            ).fetchone()[0]
            goal = self._read_goal(connection)
            session = self._read_session(connection)
            plan_row = connection.execute(
                "SELECT payload_json FROM active_course_plan WHERE singleton = 1"
            ).fetchone()
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
                "active_goal": goal.statement if goal is not None else None,
                "course_plan": json.loads(plan_row[0]) if plan_row is not None else None,
                "session": _session_json(session),
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
            self._write_memory_and_event(connection, state)

    def save_review(self, state: MemoryState) -> StudySession | None:
        """Persist a review and advance an active session in one transaction."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            self._write_memory_and_event(connection, state)
            session = self._read_session(connection)
            if session is None or session.status is not SessionStatus.ACTIVE:
                return session
            advanced = session.advance()
            self._write_session(connection, advanced)
            self._append_event(
                connection, "study_session_advanced", {
                    "session_id": session.session_id,
                    "completed_count": advanced.completed_count,
                    "status": advanced.status.value,
                }
            )
            return advanced

    @staticmethod
    def _write_memory_and_event(
        connection: sqlite3.Connection, state: MemoryState
    ) -> None:
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
        LocalState._append_event(
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
        if version == 3:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_goal (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    statement TEXT NOT NULL CHECK (length(trim(statement)) > 0)
                )
                """
            )
            version = 4
        if version == 4:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS study_session (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    session_id TEXT NOT NULL,
                    goal_statement TEXT NOT NULL CHECK (length(trim(goal_statement)) > 0),
                    agreed_item_count INTEGER NOT NULL CHECK (agreed_item_count BETWEEN 1 AND 100),
                    completed_count INTEGER NOT NULL CHECK (completed_count BETWEEN 0 AND agreed_item_count),
                    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'stopped'))
                )
                """
            )
            version = 5
        if version == 5:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_course_plan (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    payload_json TEXT NOT NULL
                )
                """
            )
            version = 6
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
    def _read_goal(connection: sqlite3.Connection) -> LearningGoal | None:
        row = connection.execute(
            "SELECT statement FROM active_goal WHERE singleton = 1"
        ).fetchone()
        return LearningGoal(row[0]) if row is not None else None

    @staticmethod
    def _read_session(connection: sqlite3.Connection) -> StudySession | None:
        row = connection.execute(
            """SELECT session_id, goal_statement, agreed_item_count,
                      completed_count, status
               FROM study_session WHERE singleton = 1"""
        ).fetchone()
        if row is None:
            return None
        return StudySession(
            row[0], LearningGoal(row[1]), row[2], row[3], SessionStatus(row[4])
        )

    @staticmethod
    def _write_session(connection: sqlite3.Connection, session: StudySession) -> None:
        connection.execute(
            """
            INSERT INTO study_session (
                singleton, session_id, goal_statement, agreed_item_count,
                completed_count, status
            ) VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(singleton) DO UPDATE SET
                session_id = excluded.session_id,
                goal_statement = excluded.goal_statement,
                agreed_item_count = excluded.agreed_item_count,
                completed_count = excluded.completed_count,
                status = excluded.status
            """,
            (session.session_id, session.goal.statement, session.agreed_item_count,
             session.completed_count, session.status.value),
        )

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


def _session_json(session: StudySession | None) -> dict[str, object] | None:
    if session is None:
        return None
    return {
        "id": session.session_id,
        "goal": session.goal.statement,
        "agreed_items": session.agreed_item_count,
        "completed_items": session.completed_count,
        "remaining_items": session.remaining_count,
        "status": session.status.value,
    }


def _course_plan_payload(plan: CoursePlan) -> dict[str, object]:
    return {
        "goal": plan.goal.statement,
        "pack_id": plan.pack.identifier,
        "pack_title": plan.pack.title,
        "language": plan.pack.language,
        "concepts": [
            {
                "identifier": concept.identifier,
                "title": concept.title,
                "prerequisites": list(concept.prerequisites),
            }
            for concept in plan.pack.curriculum.ordered_concepts
        ],
    }
