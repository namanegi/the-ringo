from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .goal import LearningGoal


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class StudySession:
    """The small, resumable contract for one bounded study session."""

    session_id: str
    goal: LearningGoal
    agreed_item_count: int
    completed_count: int = 0
    status: SessionStatus = SessionStatus.ACTIVE

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session id must not be empty")
        if not 1 <= self.agreed_item_count <= 100:
            raise ValueError("session item count must be between 1 and 100")
        if not 0 <= self.completed_count <= self.agreed_item_count:
            raise ValueError("completed count must be within the session item count")
        if (
            self.status is SessionStatus.ACTIVE
            and self.completed_count >= self.agreed_item_count
        ):
            raise ValueError("active session must have remaining items")
        if (
            self.status is SessionStatus.COMPLETED
            and self.completed_count != self.agreed_item_count
        ):
            raise ValueError("completed session must have no remaining items")

    @property
    def remaining_count(self) -> int:
        return self.agreed_item_count - self.completed_count

    def advance(self) -> "StudySession":
        if self.status is not SessionStatus.ACTIVE:
            raise ValueError("session is not active")
        completed = self.completed_count + 1
        return StudySession(
            self.session_id,
            self.goal,
            self.agreed_item_count,
            completed,
            (SessionStatus.COMPLETED
             if completed == self.agreed_item_count
             else SessionStatus.ACTIVE),
        )

    def stop(self) -> "StudySession":
        if self.status is not SessionStatus.ACTIVE:
            return self
        return StudySession(
            self.session_id,
            self.goal,
            self.agreed_item_count,
            self.completed_count,
            SessionStatus.STOPPED,
        )
