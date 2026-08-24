from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

