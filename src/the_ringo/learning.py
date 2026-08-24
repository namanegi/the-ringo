"""The small deterministic learning loop used by agents and the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .curriculum import Concept
from .memory import MemoryState, ReviewOutcome, Scheduler
from .pack import CurriculumPack
from .state import LocalState


@dataclass(frozen=True, slots=True)
class StudyTarget:
    """The next useful concept and why it was selected."""

    concept: Concept
    reason: str


class LearningService:
    """Coordinate curriculum selection, scheduling, and local persistence."""

    def __init__(
        self,
        pack: CurriculumPack,
        state: LocalState,
        scheduler: Scheduler,
    ) -> None:
        self.pack = pack
        self.state = state
        self.scheduler = scheduler

    def next_target(self, now: datetime) -> StudyTarget | None:
        """Choose a due review, or the first prerequisite-ready unseen concept."""
        curriculum = self.pack.curriculum
        memories = {
            concept.identifier: self.state.get_memory(concept.identifier)
            for concept in curriculum.ordered_concepts
        }

        for concept in curriculum.ordered_concepts:
            memory = memories[concept.identifier]
            if memory.due_at is not None and memory.due_at <= now:
                return StudyTarget(concept, "review")

        for concept in curriculum.ordered_concepts:
            memory = memories[concept.identifier]
            if (
                memory.due_at is not None
                or memory.last_outcome is not None
                or memory.streak > 0
            ):
                continue
            if all(
                memories[prerequisite].streak > 0
                for prerequisite in concept.prerequisites
            ):
                return StudyTarget(concept, "new")
        return None

    def record(
        self,
        concept_id: str,
        outcome: ReviewOutcome,
        now: datetime,
    ) -> MemoryState:
        """Schedule and persist an outcome for a known concept."""
        if concept_id not in self.pack.curriculum.concepts:
            raise ValueError(f"unknown concept: {concept_id!r}")
        current = self.state.get_memory(concept_id)
        updated = self.scheduler.review(current, outcome, now)
        self.state.save_memory(updated)
        return updated
