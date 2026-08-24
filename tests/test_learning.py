from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from the_ringo.curriculum import Concept, Curriculum
from the_ringo.learning import LearningService
from the_ringo.memory import MemoryState, ReviewOutcome, Scheduler
from the_ringo.pack import CurriculumPack
from the_ringo.state import LocalState


class LearningServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        concepts = [
            Concept("first", "First"),
            Concept("second", "Second", ("first",)),
            Concept("third", "Third"),
        ]
        pack = CurriculumPack("test", "Test", "xx", Curriculum(concepts))
        self.state = LocalState(Path(self.temp.name) / "state.sqlite3")
        self.service = LearningService(pack, self.state, Scheduler())
        self.now = datetime(2026, 8, 25, tzinfo=UTC)

    def test_due_review_beats_an_earlier_new_concept(self) -> None:
        self.state.save_memory(
            MemoryState(
                "third",
                due_at=self.now - timedelta(minutes=1),
                last_outcome=ReviewOutcome.AGAIN,
            )
        )
        target = self.service.next_target(self.now)
        self.assertIsNotNone(target)
        self.assertEqual(
            (target.concept.identifier, target.reason), ("third", "review")
        )

    def test_prerequisite_requires_good_streak(self) -> None:
        target = self.service.next_target(self.now)
        self.assertIsNotNone(target)
        self.assertEqual(target.concept.identifier, "first")
        self.state.save_memory(
            MemoryState(
                "first",
                due_at=self.now + timedelta(days=1),
                streak=1,
                last_outcome=ReviewOutcome.GOOD,
            )
        )
        target = self.service.next_target(self.now)
        self.assertIsNotNone(target)
        self.assertEqual(target.concept.identifier, "second")

    def test_record_persists_scheduled_state(self) -> None:
        state = self.service.record("first", ReviewOutcome.GOOD, self.now)
        self.assertEqual(self.state.get_memory("first"), state)
        self.assertEqual(self.state.inspect()["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
