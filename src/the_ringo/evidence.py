from __future__ import annotations

from dataclasses import dataclass

from .goal import LearningGoal
from .memory import ReviewOutcome


@dataclass(frozen=True, slots=True)
class AttemptEvidence:
    """The smallest durable proof that one activity was attempted."""

    goal: LearningGoal
    concept_id: str
    activity_key: str
    outcome: ReviewOutcome
    session_id: str | None = None

    def __post_init__(self) -> None:
        key = self.activity_key.strip()
        if not key:
            raise ValueError("activity key must not be empty")
        if len(key) > 120:
            raise ValueError("activity key must be 120 characters or fewer")
        if any(character.isspace() for character in key):
            raise ValueError("activity key must not contain whitespace")
        object.__setattr__(self, "activity_key", key)
        if self.session_id is not None and not self.session_id.strip():
            raise ValueError("session id must not be empty")
