"""Small, deterministic memory and review-scheduling objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class ReviewOutcome(StrEnum):
    """The compact set of outcomes needed by the learning loop."""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"


@dataclass(frozen=True, slots=True)
class MemoryState:
    """Immutable review state for one concept."""

    concept_id: str
    interval_days: int = 0
    due_at: datetime | None = None
    streak: int = 0
    last_outcome: ReviewOutcome | None = None

    def __post_init__(self) -> None:
        if not self.concept_id.strip():
            raise ValueError("concept id must not be empty")
        if self.interval_days < 0:
            raise ValueError("interval must not be negative")
        if self.streak < 0:
            raise ValueError("streak must not be negative")
        if self.due_at is not None:
            _require_utc(self.due_at)

    @classmethod
    def unseen(cls, concept_id: str) -> MemoryState:
        """Create a concept that has not been reviewed yet."""
        return cls(concept_id=concept_id)


class Scheduler:
    """Apply the fixed, readable interval policy for a review outcome."""

    def review(
        self,
        state: MemoryState,
        outcome: ReviewOutcome,
        now: datetime,
    ) -> MemoryState:
        """Return the next state without mutating the current one."""
        _require_utc(now)
        if not isinstance(outcome, ReviewOutcome):
            raise TypeError("outcome must be a ReviewOutcome")

        if outcome is ReviewOutcome.AGAIN:
            interval_days = 0
            streak = 0
            due_at = now
        elif outcome is ReviewOutcome.HARD:
            interval_days = max(1, state.interval_days + 1)
            streak = 0
            due_at = now + timedelta(days=interval_days)
        else:
            interval_days = max(1, state.interval_days * 2)
            streak = state.streak + 1
            due_at = now + timedelta(days=interval_days)

        return MemoryState(
            concept_id=state.concept_id,
            interval_days=interval_days,
            due_at=due_at,
            streak=streak,
            last_outcome=outcome,
        )


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
