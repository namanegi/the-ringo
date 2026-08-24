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

    def is_compatible_extension(self, newer: CoursePlan) -> bool:
        """Return whether *newer* preserves this plan and only adds content."""
        if (self.goal != newer.goal or self.pack.identifier != newer.pack.identifier
                or self.pack.title != newer.pack.title
                or self.pack.language != newer.pack.language):
            return False
        for concept in self.pack.curriculum.ordered_concepts:
            replacement = newer.pack.curriculum.concepts.get(concept.identifier)
            if replacement != concept:
                return False
        return len(newer.competencies) >= len(self.competencies)

    def has_same_pack(self, pack: CurriculumPack) -> bool:
        return (
            self.pack.identifier == pack.identifier
            and self.pack.title == pack.title
            and self.pack.language == pack.language
            and self.pack.curriculum.ordered_concepts == pack.curriculum.ordered_concepts
        )

    def is_same_as(self, other: CoursePlan) -> bool:
        return self.goal == other.goal and self.has_same_pack(other.pack)
