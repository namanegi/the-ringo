import unittest
from datetime import UTC, datetime, timedelta, timezone

from the_ringo.memory import MemoryState, ReviewOutcome, Scheduler


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scheduler = Scheduler()
        self.start = datetime(2026, 1, 1, tzinfo=UTC)
        self.state = MemoryState.unseen("ja.greetings")

    def test_good_starts_one_day_then_doubles(self) -> None:
        first = self.scheduler.review(self.state, ReviewOutcome.GOOD, self.start)
        second = self.scheduler.review(
            first, ReviewOutcome.GOOD, self.start + timedelta(days=1)
        )

        self.assertEqual(first.interval_days, 1)
        self.assertEqual(first.due_at, self.start + timedelta(days=1))
        self.assertEqual(second.interval_days, 2)
        self.assertEqual(second.streak, 2)

    def test_hard_advances_one_day_and_resets_streak(self) -> None:
        state = self.scheduler.review(self.state, ReviewOutcome.GOOD, self.start)

        next_state = self.scheduler.review(
            state, ReviewOutcome.HARD, self.start + timedelta(days=1)
        )

        self.assertEqual(next_state.interval_days, 2)
        self.assertEqual(next_state.streak, 0)
        self.assertEqual(next_state.last_outcome, ReviewOutcome.HARD)

    def test_again_is_due_immediately_and_does_not_mutate_state(self) -> None:
        next_state = self.scheduler.review(
            self.state, ReviewOutcome.AGAIN, self.start
        )

        self.assertEqual(next_state.due_at, self.start)
        self.assertEqual(next_state.interval_days, 0)
        self.assertEqual(self.state.last_outcome, None)

    def test_state_rejects_naive_datetime(self) -> None:
        with self.assertRaises(ValueError):
            MemoryState("ja.greetings", due_at=datetime(2026, 1, 1))

        with self.assertRaises(ValueError):
            MemoryState(
                "ja.greetings",
                due_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1))),
            )

        with self.assertRaises(ValueError):
            self.scheduler.review(self.state, ReviewOutcome.GOOD, datetime.now())


if __name__ == "__main__":
    unittest.main()
