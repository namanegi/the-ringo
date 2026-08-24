from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from the_ringo.curriculum import Concept, Curriculum
from the_ringo.course import CoursePlan
from the_ringo.goal import LearningGoal
from the_ringo.learning import LearningService, NextAction
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

    def test_hard_result_keeps_prerequisite_available_for_practice(self) -> None:
        self.service.pack = CurriculumPack(
            "test", "Test", "xx", Curriculum(
                [Concept("first", "First"), Concept("second", "Second", ("first",))]
            )
        )
        self.service.record("first", ReviewOutcome.HARD, self.now)

        target = self.service.next_target(self.now)

        self.assertIsNotNone(target)
        self.assertEqual(
            (target.concept.identifier, target.reason), ("first", "practice")
        )

    def test_record_persists_scheduled_state(self) -> None:
        state = self.service.record("first", ReviewOutcome.GOOD, self.now)
        self.assertEqual(self.state.get_memory("first"), state)
        self.assertEqual(self.state.inspect()["event_count"], 1)

    def test_snapshot_summarizes_progress_and_next_target(self) -> None:
        self.state.initialize("zh-CN", "xx")
        snapshot = self.service.snapshot(self.now)
        self.assertEqual((snapshot.started_concepts, snapshot.total_concepts), (0, 3))
        self.assertEqual(snapshot.due_reviews, 0)
        self.assertEqual(snapshot.next_target.concept.identifier, "first")

    def _goal_service(self, concepts: list[Concept]) -> LearningService:
        self.state.initialize("zh-CN", "xx")
        goal = LearningGoal("test goal")
        self.state.set_goal(goal)
        pack = CurriculumPack("plan", "Plan", "xx", Curriculum(concepts))
        self.state.save_course_plan(CoursePlan(goal, pack))
        return LearningService(pack, self.state, Scheduler())

    def test_distinct_good_coverage_and_target_metadata(self) -> None:
        service = self._goal_service([
            Concept("first", "First"), Concept("second", "Second"),
            Concept("third", "Third"),
        ])
        service.record("first", ReviewOutcome.GOOD, self.now, "first-dialogue")
        target = service.next_target(self.now)
        self.assertEqual(target.concept.identifier, "second")
        self.assertEqual(target.coverage, 0)
        self.assertEqual(target.required_coverage, 2)
        service.record("first", ReviewOutcome.GOOD, self.now, "first-dialogue")
        evidence = self.state.get_attempt_evidence(self.state.get_goal(), "first")
        self.assertEqual(
            tuple(item.activity_key for item in evidence if item.outcome is ReviewOutcome.GOOD),
            ("first-dialogue", "first-dialogue"),
        )
        self.assertEqual(len({item.activity_key for item in evidence}), 1)
        service.record("first", ReviewOutcome.GOOD, self.now, "first-roleplay")
        self.assertIsNotNone(service.next_target(self.now))

    def test_repetition_guard_prefers_another_undercovered_competency(self) -> None:
        service = self._goal_service([
            Concept("first", "First"), Concept("second", "Second"),
        ])
        service.record("first", ReviewOutcome.GOOD, self.now, "first-a")
        service.record("first", ReviewOutcome.HARD, self.now, "first-b")
        target = service.next_target(self.now)
        self.assertEqual(target.concept.identifier, "second")

    def test_failed_activity_is_visible_but_does_not_count_as_good_coverage(self) -> None:
        service = self._goal_service([Concept("first", "First")])
        service.record("first", ReviewOutcome.HARD, self.now, "first-translation")
        target = service.next_target(self.now)
        self.assertEqual(target.activity_keys, ("first-translation",))
        self.assertEqual(target.coverage, 0)

    def test_practice_cannot_bypass_locked_prerequisite(self) -> None:
        service = self._goal_service([
            Concept("first", "First"),
            Concept("second", "Second", ("first",)),
        ])
        service.record("first", ReviewOutcome.HARD, self.now, "first-a")
        target = service.next_target(self.now)
        self.assertEqual(target.concept.identifier, "first")

    def test_guard_only_blocks_a_true_third_consecutive_concept(self) -> None:
        service = self._goal_service([
            Concept("first", "First"), Concept("second", "Second"),
        ])
        service.record("first", ReviewOutcome.HARD, self.now, "first-a")
        service.record("second", ReviewOutcome.HARD, self.now, "second-a")
        self.assertEqual(service.next_target(self.now).concept.identifier, "first")
        service.record("first", ReviewOutcome.HARD, self.now, "first-b")
        service.record("first", ReviewOutcome.HARD, self.now, "first-c")
        self.assertEqual(service.next_target(self.now).concept.identifier, "second")

    def test_closed_session_is_not_attached_to_later_evidence(self) -> None:
        service = self._goal_service([
            Concept("first", "First"), Concept("second", "Second"),
        ])
        self.state.start_session(1)
        service.record("first", ReviewOutcome.GOOD, self.now, "first-a")
        self.assertEqual(self.state.get_session().status.value, "completed")
        service.record("second", ReviewOutcome.GOOD, self.now, "second-a")
        evidence = self.state.get_attempt_evidence(self.state.get_goal(), "second")
        self.assertIsNone(evidence[-1].session_id)

    def test_reaching_evidence_threshold_does_not_fallback_to_practice(self) -> None:
        service = self._goal_service([Concept("first", "First")])
        service.record("first", ReviewOutcome.GOOD, self.now, "first-a")
        service.record("first", ReviewOutcome.GOOD, self.now, "first-b")
        self.assertIsNone(service.next_target(self.now))

    def test_goal_decision_is_expand_without_a_plan(self) -> None:
        self.state.initialize("zh-CN", "xx")
        self.state.set_goal(LearningGoal("interview"))

        self.assertIsNone(self.service.next_target(self.now))
        self.assertEqual(self.service.next_action(self.now), NextAction.EXPAND)

    def test_goal_progress_completes_only_on_distinct_good_activities(self) -> None:
        service = self._goal_service([Concept("first", "First")])
        service.record("first", ReviewOutcome.GOOD, self.now, "first-a")
        service.record("first", ReviewOutcome.GOOD, self.now, "first-a")
        progress = service.goal_progress()

        self.assertEqual(progress.competencies[0].coverage, 1)
        self.assertFalse(progress.complete)
        self.assertEqual(service.next_action(self.now), NextAction.CONTINUE)

        service.record("first", ReviewOutcome.GOOD, self.now, "first-b")
        progress = service.goal_progress()
        self.assertTrue(progress.complete)
        self.assertEqual(progress.gaps, ())
        self.assertEqual(service.next_action(self.now), NextAction.COMPLETE)


if __name__ == "__main__":
    unittest.main()
