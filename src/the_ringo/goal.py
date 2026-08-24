from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LearningGoal:
    """The learner's one active, human-readable purpose."""

    statement: str

    def __post_init__(self) -> None:
        normalized = self.statement.strip()
        if not normalized:
            raise ValueError("learning goal must not be empty")
        if len(normalized) > 500:
            raise ValueError("learning goal must be 500 characters or fewer")
        object.__setattr__(self, "statement", normalized)
