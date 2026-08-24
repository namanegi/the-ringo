from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from the_ringo import __version__
from the_ringo.course import CoursePlan
from the_ringo.learning import (
    CompetencyProgress,
    GoalProgress,
    LearningService,
    ProgressSnapshot,
    StudyTarget,
)
from the_ringo.goal import LearningGoal
from the_ringo.memory import ReviewOutcome, Scheduler
from the_ringo.pack import CurriculumPack, CurriculumPackError, CurriculumPackLoader
from the_ringo.preferences import LearnerPreferences
from the_ringo.state import LocalState, StateConflictError
from the_ringo.session import StudySession

PROTOCOL = {
    "protocol_version": 1,
    "application_version": __version__,
    "capabilities": [
        "local_state",
        "learner_initialization",
        "diagnostics",
        "curriculum_catalog",
        "learning_loop",
        "learner_preferences",
        "progress_status",
        "active_learning_goal",
        "bounded_study_session",
        "goal_bound_course_plan",
        "attempt_evidence",
        "goal_checkpoint",
    ],
    "commands": {
        "init": "Initialize one local learner profile.",
        "doctor": "Inspect local state and runtime health.",
        "catalog": "List the ordered concepts in a curriculum pack.",
        "next": "Choose the next concept to study.",
        "record": "Record a review outcome and optional activity evidence for a concept.",
        "configure": "View or update learner preferences.",
        "status": "Summarize learner progress and the next useful concept.",
        "protocol": "Describe implemented machine-facing capabilities.",
        "goal": "View or set the active learning goal.",
        "session": "Start, resume, stop, or inspect the bounded study session.",
        "course": "Apply or inspect the active goal-bound course plan.",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ringo",
        description="Local-first, agent-driven language learning.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing local .ringo state (default: current directory).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize learner state.")
    init_parser.add_argument("--native-language", required=True)
    init_parser.add_argument("--target-language", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Inspect local state.")
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")

    catalog_parser = subparsers.add_parser(
        "catalog", help="List concepts in a curriculum pack."
    )
    catalog_parser.add_argument("--json", action="store_true", dest="as_json")
    catalog_parser.add_argument(
        "--pack",
        type=Path,
        help="Custom TOML pack path, relative to the project root.",
    )

    next_parser = subparsers.add_parser("next", help="Choose the next concept.")
    next_parser.add_argument("--json", action="store_true", dest="as_json")
    next_parser.add_argument("--pack", type=Path, help="Custom TOML pack path.")

    record_parser = subparsers.add_parser(
        "record", help="Record a concept review outcome."
    )
    record_parser.add_argument("concept_id")
    record_parser.add_argument(
        "--outcome",
        choices=[outcome.value for outcome in ReviewOutcome],
        required=True,
    )
    record_parser.add_argument("--pack", type=Path, help="Custom TOML pack path.")

    configure_parser = subparsers.add_parser(
        "configure", help="View or update learner preferences."
    )
    configure_parser.add_argument("--daily-items", type=int)
    configure_parser.add_argument("--new-content-ratio", type=float)
    configure_parser.add_argument("--explanation-style")

    status_parser = subparsers.add_parser(
        "status", help="Show learner progress and the next useful concept."
    )
    status_parser.add_argument("--json", action="store_true", dest="as_json")
    status_parser.add_argument("--pack", type=Path, help="Custom TOML pack path.")

    goal_parser = subparsers.add_parser("goal", help="View or set the active goal.")
    goal_parser.add_argument("--set", dest="statement", help="Set the active goal.")
    goal_parser.add_argument("--json", action="store_true", dest="as_json")

    session_parser = subparsers.add_parser(
        "session", help="Start, resume, stop, or inspect a study session."
    )
    session_parser.add_argument("action", nargs="?", choices=("start", "stop"))
    session_parser.add_argument("--items", type=int)
    session_parser.add_argument("--json", action="store_true", dest="as_json")

    course_parser = subparsers.add_parser(
        "course", help="Apply or inspect the active course plan."
    )
    record_parser.add_argument("--activity-key")
    course_parser.add_argument("action", nargs="?", choices=("apply",))
    course_parser.add_argument("pack_path", nargs="?")
    course_parser.add_argument("--json", action="store_true", dest="as_json")

    subparsers.add_parser("protocol", help="Print the agent-facing protocol.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    state = LocalState(root / ".ringo" / "state.sqlite3")

    try:
        if args.command == "init":
            profile = state.initialize(
                native_language=args.native_language,
                target_language=args.target_language,
            )
            print(
                json.dumps(
                    {
                        "initialized": True,
                        "profile": {
                            "native_language": profile.native_language,
                            "target_language": profile.target_language,
                            "created_at": profile.created_at,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        if args.command == "doctor":
            report = state.inspect()
            if args.as_json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                status = "ready" if report["initialized"] else "not initialized"
                print(f"the-ringo {__version__}: {status}")
                print(f"state: {report['database_path']}")
            return 0

        if args.command == "configure":
            current = state.get_preferences()
            preferences = LearnerPreferences(
                daily_items=(
                    args.daily_items
                    if args.daily_items is not None
                    else current.daily_items
                ),
                new_content_ratio=(
                    args.new_content_ratio
                    if args.new_content_ratio is not None
                    else current.new_content_ratio
                ),
                explanation_style=(
                    args.explanation_style
                    if args.explanation_style is not None
                    else current.explanation_style
                ),
            )
            if any(
                value is not None
                for value in (
                    args.daily_items,
                    args.new_content_ratio,
                    args.explanation_style,
                )
            ):
                state.save_preferences(preferences)
            print(json.dumps(_preferences_json(preferences), ensure_ascii=False, indent=2))
            return 0

        if args.command == "goal":
            goal = state.get_goal()
            if args.statement is not None:
                goal = state.set_goal(LearningGoal(args.statement))
            result = {"active_goal": goal.statement if goal is not None else None}
            if args.as_json or args.statement is not None:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(result["active_goal"] or "none")
            return 0

        if args.command == "session":
            if args.action == "start":
                session = state.start_session(args.items)
            elif args.action == "stop":
                if args.items is not None:
                    raise ValueError("--items is only valid with session start")
                session = state.stop_session()
            else:
                if args.items is not None:
                    raise ValueError("--items is only valid with session start")
                session = state.get_session()
            result = _session_json(session)
            if args.as_json or args.action is not None:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(_session_text(session))
            return 0

        if args.command == "course":
            if args.action == "apply":
                if args.pack_path is None:
                    raise ValueError("course apply requires a TOML pack path")
                pack_path = _resolve_pack_path(root, Path(args.pack_path))
                pack = CurriculumPackLoader().load(pack_path)
                profile = state.get_profile()
                goal = state.get_goal()
                if goal is None:
                    raise StateConflictError("set a learning goal before applying a course")
                if pack.language != profile.target_language:
                    raise StateConflictError(
                        "course pack language must match learner target language"
                    )
                plan = state.save_course_plan(CoursePlan(goal, pack))
            else:
                plan = state.get_course_plan()
            result = _course_json(plan)
            if args.as_json or args.action is not None:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(result["pack"]["title"] if result is not None else "none")
            return 0

        if args.command == "status":
            snapshot = LearningService(
                _load_pack(root, args.pack, state), state, Scheduler(),
                use_course_plan=args.pack is None,
            ).snapshot(datetime.now(UTC))
            if args.as_json:
                print(
                    json.dumps(
                        _snapshot_json(snapshot, state.get_course_plan()),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(_snapshot_text(snapshot))
            return 0

        if args.command == "catalog":
            pack = _load_pack(root, args.pack, state)
            concepts = [
                {
                    "identifier": concept.identifier,
                    "title": concept.title,
                    "prerequisites": list(concept.prerequisites),
                }
                for concept in pack.curriculum.ordered_concepts
            ]
            if args.as_json:
                print(
                    json.dumps(
                        {
                            "id": pack.identifier,
                            "title": pack.title,
                            "language": pack.language,
                            "concepts": concepts,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(f"{pack.title} [{pack.language}] ({pack.identifier})")
                for index, concept in enumerate(concepts, start=1):
                    print(f"{index}. {concept['identifier']} — {concept['title']}")
            return 0

        if args.command in {"next", "record"}:
            pack = _load_pack(root, args.pack, state)
            service = LearningService(
                pack, state, Scheduler(), use_course_plan=args.pack is None
            )
            now = datetime.now(UTC)
            if args.command == "next":
                target = service.next_target(now)
                action = service.next_action(now)
                result = _target_json(target)
                if action is not None:
                    result = {
                        "next_action": action.value,
                        "goal_progress": _goal_progress_json(
                            service.goal_progress()
                        ),
                        "target": result,
                    }
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                memory = service.record(
                    args.concept_id, ReviewOutcome(args.outcome), now,
                    args.activity_key,
                )
                print(
                    json.dumps(
                        {
                            "concept_id": memory.concept_id,
                            "interval_days": memory.interval_days,
                            "due_at": memory.due_at.isoformat()
                            if memory.due_at is not None
                            else None,
                            "streak": memory.streak,
                            "last_outcome": memory.last_outcome.value
                            if memory.last_outcome is not None
                            else None,
                            "session": _session_json(state.get_session()),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            return 0

        if args.command == "protocol":
            print(json.dumps(PROTOCOL, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    except (
        OSError,
        RuntimeError,
        ValueError,
        StateConflictError,
        CurriculumPackError,
    ) as error:
        print(f"ringo: error: {error}", file=sys.stderr)
        return 2

    return 1


def _resolve_pack_path(root: Path, pack_path: Path) -> Path:
    return (pack_path if pack_path.is_absolute() else root / pack_path).resolve()


def _load_pack(
    root: Path, requested_path: Path | None, state: LocalState
) -> CurriculumPack:
    if requested_path is None:
        plan = state.get_course_plan()
        if plan is not None:
            return plan.pack
        pack_path = root / Path("packs") / "ja-starter.toml"
    else:
        pack_path = _resolve_pack_path(root, requested_path)
    return CurriculumPackLoader().load(pack_path)


def _preferences_json(preferences: LearnerPreferences) -> dict[str, object]:
    return {
        "daily_items": preferences.daily_items,
        "new_content_ratio": preferences.new_content_ratio,
        "explanation_style": preferences.explanation_style,
    }


def _target_json(target: StudyTarget | None) -> dict[str, object] | None:
    if target is None:
        return None
    return {
        "identifier": target.concept.identifier,
        "title": target.concept.title,
        "prerequisites": list(target.concept.prerequisites),
        "reason": target.reason,
        "activity_keys": list(target.activity_keys),
        "coverage": target.coverage,
        "required_coverage": target.required_coverage,
    }


def _snapshot_json(
    snapshot: ProgressSnapshot, plan: CoursePlan | None = None
) -> dict[str, object]:
    return {
        "as_of": snapshot.as_of.isoformat(),
        "learner": {
            "native_language": snapshot.profile.native_language,
            "target_language": snapshot.profile.target_language,
        },
        "pack": {
            "id": snapshot.pack.identifier,
            "title": snapshot.pack.title,
            "language": snapshot.pack.language,
        },
        "progress": {
            "started": snapshot.started_concepts,
            "total": snapshot.total_concepts,
        },
        "due_reviews": snapshot.due_reviews,
        "preferences": _preferences_json(snapshot.preferences),
        "course_plan": _course_json(plan),
        "next": _target_json(snapshot.next_target),
        "next_action": (
            snapshot.next_action.value if snapshot.next_action is not None else None
        ),
        "goal_progress": _goal_progress_json(snapshot.goal_progress),
        "session": _session_json(snapshot.session),
    }


def _course_json(plan: CoursePlan | None) -> dict[str, object] | None:
    if plan is None:
        return None
    return {
        "goal": plan.goal.statement,
        "pack": {
            "id": plan.pack.identifier,
            "title": plan.pack.title,
            "language": plan.pack.language,
        },
        "competencies": list(plan.competencies),
    }


def _goal_progress_json(
    progress: GoalProgress | None,
) -> dict[str, object] | None:
    if progress is None:
        return None
    competencies = [_competency_progress_json(item) for item in progress.competencies]
    return {
        "goal": progress.goal,
        "complete": progress.complete,
        "required_coverage": (
            progress.competencies[0].required_coverage
            if progress.competencies
            else None
        ),
        "gaps": list(progress.gaps),
        "competencies": competencies,
    }


def _competency_progress_json(
    progress: CompetencyProgress,
) -> dict[str, object]:
    return {
        "identifier": progress.identifier,
        "title": progress.title,
        "activity_keys": list(progress.activity_keys),
        "good_activity_keys": list(progress.good_activity_keys),
        "coverage": progress.coverage,
        "required_coverage": progress.required_coverage,
        "gap": progress.gap,
        "complete": progress.complete,
    }


def _snapshot_text(snapshot: ProgressSnapshot) -> str:
    learner = (
        f"{snapshot.profile.native_language} → "
        f"{snapshot.profile.target_language}"
    )
    preferences = snapshot.preferences
    next_line = "none"
    if snapshot.next_target is not None:
        target = snapshot.next_target
        next_line = f"{target.concept.identifier} — {target.concept.title} ({target.reason})"
    return "\n".join(
        (
            f"the-ringo — {learner}",
            f"pack: {snapshot.pack.title} [{snapshot.pack.identifier}]",
            f"progress: {snapshot.started_concepts}/{snapshot.total_concepts} concepts started",
            f"reviews due: {snapshot.due_reviews}",
            "preferences: "
            f"{preferences.daily_items}/day · "
            f"{preferences.new_content_ratio:.0%} new · "
            f"{preferences.explanation_style}",
            f"next: {next_line}",
            f"session: {_session_text(snapshot.session)}",
        )
    )


def _session_json(session: StudySession | None) -> dict[str, object] | None:
    if session is None:
        return None
    return {
        "id": session.session_id,
        "goal": session.goal.statement,
        "agreed_items": session.agreed_item_count,
        "completed_items": session.completed_count,
        "remaining_items": session.remaining_count,
        "status": session.status.value,
    }


def _session_text(session: StudySession | None) -> str:
    if session is None:
        return "none"
    return (
        f"{session.status.value} — {session.completed_count}/"
        f"{session.agreed_item_count} items · {session.goal.statement}"
    )
