"""The small deterministic learning loop used by agents and the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .curriculum import Concept
from .course import CoursePlan
from .evidence import AttemptEvidence
from .goal import LearningGoal
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


class NextAction(StrEnum):
    """The one machine-facing decision at a goal checkpoint."""

    CONTINUE = "continue"
    EXPAND = "expand"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class CompetencyProgress:
    """Persisted evidence summarized for one planned competency."""

    identifier: str
    title: str
    evidence: tuple[AttemptEvidence, ...]
    activity_keys: tuple[str, ...]
    good_activity_keys: tuple[str, ...]
    required_coverage: int

    @property
    def coverage(self) -> int:
        return len(self.good_activity_keys)

    @property
    def gap(self) -> int:
        return max(0, self.required_coverage - self.coverage)

    @property
    def complete(self) -> bool:
        return self.gap == 0


@dataclass(frozen=True, slots=True)
class GoalProgress:
    """Immutable goal-level view derived solely from the active plan/evidence."""

    goal: str
    competencies: tuple[CompetencyProgress, ...]

    @property
    def complete(self) -> bool:
        return bool(self.competencies) and all(
            competency.complete for competency in self.competencies
        )

    @property
    def gaps(self) -> tuple[str, ...]:
        return tuple(
            competency.identifier
            for competency in self.competencies
            if not competency.complete
        )


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
    goal_progress: GoalProgress | None = None
    next_action: NextAction | None = None


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
        if (
            self.use_course_plan
            and self._active_goal() is not None
            and plan is None
        ):
            return None
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

    def goal_progress(self, plan: CoursePlan | None = None) -> GoalProgress | None:
        """Summarize distinct successful activities for the active goal plan."""
        if not self.use_course_plan:
            return None
        plan = plan or self.state.get_course_plan()
        if plan is None:
            return None
        evidence = self.state.get_attempt_evidence(plan.goal)
        competencies = []
        for concept in plan.pack.curriculum.ordered_concepts:
            concept_evidence = [
                item for item in evidence if item.concept_id == concept.identifier
            ]
            activity_keys = tuple(dict.fromkeys(
                item.activity_key for item in concept_evidence
            ))
            good_keys = tuple(dict.fromkeys(
                item.activity_key
                for item in concept_evidence
                if item.outcome is ReviewOutcome.GOOD
            ))
            competencies.append(
                CompetencyProgress(
                    concept.identifier,
                    concept.title,
                    tuple(concept_evidence),
                    activity_keys,
                    good_keys,
                    EvidencePolicy.SUCCESSFUL_ACTIVITIES_REQUIRED,
                )
            )
        return GoalProgress(plan.goal.statement, tuple(competencies))

    def next_action(self, now: datetime) -> NextAction | None:
        """Decide whether the agent should teach, extend, or close the goal."""
        if not self.use_course_plan:
            return None
        if self._active_goal() is None:
            return None
        plan = self.state.get_course_plan()
        if plan is None:
            return NextAction.EXPAND
        progress = self.goal_progress(plan)
        if progress is not None and progress.complete:
            return NextAction.COMPLETE
        return (
            NextAction.CONTINUE
            if self.next_target(now) is not None
            else NextAction.EXPAND
        )

    def _active_goal(self) -> LearningGoal | None:
        try:
            return self.state.get_goal()
        except RuntimeError as error:
            if str(error) == "learner state is not initialized":
                return None
            raise

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
            goal_progress=self.goal_progress(),
            next_action=self.next_action(now),
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
