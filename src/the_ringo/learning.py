"""The small deterministic learning loop used by agents and the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .curriculum import Concept
from .memory import MemoryState, ReviewOutcome, Scheduler
from .pack import CurriculumPack
from .preferences import LearnerPreferences
from .state import LearnerProfile, LocalState


@dataclass(frozen=True, slots=True)
class StudyTarget:
    """The next useful concept and why it was selected."""

    concept: Concept
    reason: str


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    """Immutable, presentation-ready learner progress at one UTC instant."""

    profile: LearnerProfile
    pack: CurriculumPack
    started_concepts: int
    total_concepts: int
    due_reviews: int
    preferences: LearnerPreferences
    next_target: StudyTarget | None
    as_of: datetime


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
        """Choose a due review, new concept, or started practice target."""
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

        started = [
            (index, concept, memories[concept.identifier])
            for index, concept in enumerate(curriculum.ordered_concepts)
            if memories[concept.identifier].last_outcome is not None
        ]
        if started:
            _, concept, _ = min(
                started,
                key=lambda item: (
                    item[2].due_at is not None,
                    item[2].due_at if item[2].due_at is not None else now,
                    item[0],
                ),
            )
            return StudyTarget(concept, "practice")
        return None

    def snapshot(self, now: datetime) -> ProgressSnapshot:
        """Build the compact status view from persisted state and the pack."""
        memories = [
            self.state.get_memory(concept.identifier)
            for concept in self.pack.curriculum.ordered_concepts
        ]
        return ProgressSnapshot(
            profile=self.state.get_profile(),
            pack=self.pack,
            started_concepts=sum(memory.last_outcome is not None for memory in memories),
            total_concepts=len(memories),
            due_reviews=sum(
                memory.due_at is not None and memory.due_at <= now
                for memory in memories
            ),
            preferences=self.state.get_preferences(),
            next_target=self.next_target(now),
            as_of=now,
        )

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
