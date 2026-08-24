from __future__ import annotations

import tempfile
import unittest
import sqlite3
from datetime import UTC, datetime
from dataclasses import FrozenInstanceError
from pathlib import Path

from the_ringo.memory import MemoryState, ReviewOutcome
from the_ringo.goal import LearningGoal
from the_ringo.preferences import LearnerPreferences
from the_ringo.state import LocalState, StateConflictError


class LocalStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / ".ringo" / "state.sqlite3"
        self.state = LocalState(database_path)

    def test_inspect_reports_uninitialized_state(self) -> None:
        report = self.state.inspect()

        self.assertFalse(report["initialized"])
        self.assertEqual(report["event_count"], 0)

    def test_initialize_is_idempotent(self) -> None:
        first = self.state.initialize("zh-CN", "ja")
        second = self.state.initialize("zh-CN", "ja")

        self.assertEqual(first, second)
        report = self.state.inspect()
        self.assertTrue(report["initialized"])
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["profile"]["target_language"], "ja")

    def test_initialize_rejects_conflicting_profile(self) -> None:
        self.state.initialize("zh-CN", "ja")

        with self.assertRaises(StateConflictError):
            self.state.initialize("en", "fr")

    def test_learning_goal_is_immutable_and_same_goal_is_idempotent(self) -> None:
        self.state.initialize("zh-CN", "ja")
        goal = LearningGoal("  商务面试常用日语  ")

        with self.assertRaises(FrozenInstanceError):
            goal.statement = "changed"  # type: ignore[misc]

        self.assertIsNone(self.state.get_goal())
        self.state.set_goal(goal)
        self.state.set_goal(LearningGoal("商务面试常用日语"))
        self.assertEqual(self.state.get_goal(), goal)
        self.assertEqual(self.state.inspect()["event_count"], 2)

    def test_switching_goal_preserves_memory_and_appends_one_event(self) -> None:
        self.state.initialize("zh-CN", "ja")
        memory = MemoryState(
            concept_id="ja.greetings",
            interval_days=2,
            due_at=datetime(2026, 8, 25, 12, tzinfo=UTC),
            streak=1,
            last_outcome=ReviewOutcome.GOOD,
        )
        self.state.save_memory(memory)
        self.state.set_goal(LearningGoal("商务面试常用日语"))
        before_switch = self.state.inspect()["event_count"]

        self.state.set_goal(LearningGoal("日本客户会议表达"))

        self.assertEqual(self.state.get_memory(memory.concept_id), memory)
        self.assertEqual(self.state.inspect()["event_count"], before_switch + 1)
        self.assertEqual(self.state.get_goal().statement, "日本客户会议表达")

    def test_v3_database_migrates_without_losing_events_or_memory(self) -> None:
        self.state.initialize("zh-CN", "ja")
        memory = MemoryState(
            concept_id="ja.greetings",
            due_at=datetime(2026, 8, 25, 12, tzinfo=UTC),
            last_outcome=ReviewOutcome.AGAIN,
        )
        self.state.save_memory(memory)
        event_count = self.state.inspect()["event_count"]

        connection = sqlite3.connect(self.state.database_path)
        try:
            connection.execute(
                "UPDATE metadata SET value = '3' WHERE key = 'schema_version'"
            )
            connection.execute("DROP TABLE active_goal")
            connection.commit()
            self.assertEqual(
                connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()[0],
                "3",
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'active_goal'"
                ).fetchone()
            )
        finally:
            connection.close()

        self.assertIsNone(self.state.get_goal())
        self.assertEqual(self.state.inspect()["schema_version"], 4)
        self.assertEqual(self.state.inspect()["event_count"], event_count)
        self.assertEqual(self.state.get_memory(memory.concept_id), memory)

    def test_memory_round_trip_and_unseen_default(self) -> None:
        unseen = self.state.get_memory("ja.greetings")
        self.assertEqual(unseen, MemoryState.unseen("ja.greetings"))

        expected = MemoryState(
            concept_id="ja.greetings",
            interval_days=2,
            due_at=datetime(2026, 8, 25, 12, tzinfo=UTC),
            streak=1,
            last_outcome=ReviewOutcome.GOOD,
        )
        self.state.save_memory(expected)

        self.assertEqual(self.state.get_memory("ja.greetings"), expected)
        self.assertEqual(self.state.inspect()["event_count"], 1)

    def test_memory_and_event_roll_back_together(self) -> None:
        expected = MemoryState(
            concept_id="ja.greetings",
            due_at=datetime(2026, 8, 25, 12, tzinfo=UTC),
            last_outcome=ReviewOutcome.AGAIN,
        )
        original_append_event = LocalState._append_event

        def fail_append_event(*args: object, **kwargs: object) -> None:
            raise RuntimeError("event write failed")

        LocalState._append_event = staticmethod(fail_append_event)
        self.addCleanup(
            setattr, LocalState, "_append_event", staticmethod(original_append_event)
        )
        with self.assertRaisesRegex(RuntimeError, "event write failed"):
            self.state.save_memory(expected)

        self.assertEqual(
            self.state.get_memory("ja.greetings"),
            MemoryState.unseen("ja.greetings"),
        )
        self.assertEqual(self.state.inspect()["event_count"], 0)

    def test_preferences_default_and_partial_update_persist(self) -> None:
        self.state.initialize("zh-CN", "ja")

        self.assertEqual(self.state.get_preferences(), LearnerPreferences())

        updated = LearnerPreferences(
            new_content_ratio=0.5,
            explanation_style="  Explain with examples.  ",
        )
        self.state.save_preferences(updated)

        self.assertEqual(self.state.get_preferences(), updated)
        self.assertEqual(self.state.inspect()["preferences"]["daily_items"], 10)
        self.assertEqual(updated.explanation_style, "Explain with examples.")


if __name__ == "__main__":
    unittest.main()
