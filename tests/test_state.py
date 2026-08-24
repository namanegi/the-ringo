from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from the_ringo.memory import MemoryState, ReviewOutcome
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


if __name__ == "__main__":
    unittest.main()
