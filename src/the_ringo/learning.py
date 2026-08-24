"""The small deterministic learning loop used by agents and the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .curriculum import Concept
from .course import CoursePlan
from .evidence import AttemptEvidence
from .memory import MemoryState, ReviewOutcome, Scheduler
from .pack import CurriculumPack
from .preferences import LearnerPreferences
from .state import LearnerProfile, LocalState
from .session import SessionStatus, StudySession


@dataclass(frozen=True, slots=True)
class StudyTarget:
    """The next useful concept and why it was selected."""

    concept: Concept
    reason: str
    activity_keys: tuple[str, ...] = ()
    coverage: int = 0
    required_coverage: int | None = None


class EvidencePolicy:
    """Small, explainable default mastery policy for a goal plan."""

    SUCCESSFUL_ACTIVITIES_REQUIRED = 2


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
    session: StudySession | None
    as_of: datetime


class LearningService:
    """Coordinate curriculum selection, scheduling, and local persistence."""

    def __init__(
        self,
        pack: CurriculumPack,
        state: LocalState,
        scheduler: Scheduler,
        use_course_plan: bool = True,
    ) -> None:
        self.pack = pack
        self.state = state
        self.scheduler = scheduler
        self.use_course_plan = use_course_plan

    def next_target(self, now: datetime) -> StudyTarget | None:
        """Choose a due review, new concept, or started practice target."""
        curriculum = self.pack.curriculum
        plan = self.state.get_course_plan() if self.use_course_plan else None
        if plan is not None and plan.has_same_pack(self.pack):
            return self._next_goal_target(plan, now)
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

    def _next_goal_target(self, plan: CoursePlan, now: datetime) -> StudyTarget | None:
        goal = plan.goal
        evidence = self.state.get_attempt_evidence(goal)
        attempted_keys = {
            concept.identifier: tuple(dict.fromkeys(
                item.activity_key for item in evidence
                if item.concept_id == concept.identifier
            ))
            for concept in plan.pack.curriculum.ordered_concepts
        }
        good_keys = {
            concept.identifier: tuple(dict.fromkeys(
                item.activity_key for item in evidence
                if item.concept_id == concept.identifier
                and item.outcome is ReviewOutcome.GOOD
            ))
            for concept in plan.pack.curriculum.ordered_concepts
        }
        memories = {
            concept.identifier: self.state.get_memory(concept.identifier)
            for concept in plan.pack.curriculum.ordered_concepts
        }
        candidates: list[tuple[str, Concept]] = []
        for concept in plan.pack.curriculum.ordered_concepts:
            if len(good_keys[concept.identifier]) >= EvidencePolicy.SUCCESSFUL_ACTIVITIES_REQUIRED:
                continue
            memory = memories[concept.identifier]
            if memory.due_at is not None and memory.due_at <= now:
                candidates.append(("review", concept))
        if not candidates:
            for concept in plan.pack.curriculum.ordered_concepts:
                if attempted_keys[concept.identifier]:
                    continue
                memory = memories[concept.identifier]
                if memory.last_outcome is None and all(
                    memories[prerequisite].streak > 0
                    for prerequisite in concept.prerequisites
                ):
                    candidates.append(("new", concept))
        if not candidates:
            for concept in plan.pack.curriculum.ordered_concepts:
                if len(good_keys[concept.identifier]) < EvidencePolicy.SUCCESSFUL_ACTIVITIES_REQUIRED and (
                    memories[concept.identifier].last_outcome is not None
                    or all(
                        memories[prerequisite].streak > 0
                        for prerequisite in concept.prerequisites
                    )
                ):
                    candidates.append(("practice", concept))
        if not candidates:
            return None
        recent = self.state.recent_attempt_concepts(goal, 2)
        if len(recent) == 2 and recent[0] == recent[1]:
            alternatives = [item for item in candidates if item[1].identifier != recent[0]]
            candidates = alternatives or candidates
        reason, concept = candidates[0]
        return StudyTarget(
            concept, reason, attempted_keys[concept.identifier],
            len(good_keys[concept.identifier]), EvidencePolicy.SUCCESSFUL_ACTIVITIES_REQUIRED,
        )

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
            session=self.state.get_session(),
            as_of=now,
        )

    def record(
        self,
        concept_id: str,
        outcome: ReviewOutcome,
        now: datetime,
        activity_key: str | None = None,
    ) -> MemoryState:
        """Schedule and persist an outcome for a known concept."""
        if concept_id not in self.pack.curriculum.concepts:
            raise ValueError(f"unknown concept: {concept_id!r}")
        current = self.state.get_memory(concept_id)
        updated = self.scheduler.review(current, outcome, now)
        plan = self.state.get_course_plan() if self.use_course_plan else None
        evidence = None
        if plan is not None and plan.has_same_pack(self.pack):
            if activity_key is None:
                raise ValueError("--activity-key is required when an active course plan is used")
            session = self.state.get_session()
            evidence = AttemptEvidence(
                goal=plan.goal,
                session_id=(
                    session.session_id
                    if session is not None and session.status is SessionStatus.ACTIVE
                    else None
                ),
                concept_id=concept_id,
                activity_key=activity_key,
                outcome=outcome,
            )
        self.state.save_review(updated, evidence)
        return updated
