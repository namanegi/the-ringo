from __future__ import annotations

from dataclasses import dataclass

from .goal import LearningGoal
from .pack import CurriculumPack


@dataclass(frozen=True, slots=True)
class CoursePlan:
    """A goal-bound view of one validated curriculum pack."""

    goal: LearningGoal
    pack: CurriculumPack

    @property
    def competencies(self) -> tuple[str, ...]:
        return tuple(
            concept.identifier for concept in self.pack.curriculum.ordered_concepts
        )
