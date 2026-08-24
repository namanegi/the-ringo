from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from the_ringo import __version__
from the_ringo.learning import LearningService, ProgressSnapshot, StudyTarget
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
    ],
    "commands": {
        "init": "Initialize one local learner profile.",
        "doctor": "Inspect local state and runtime health.",
        "catalog": "List the ordered concepts in a curriculum pack.",
        "next": "Choose the next concept to study.",
        "record": "Record a review outcome for a concept.",
        "configure": "View or update learner preferences.",
        "status": "Summarize learner progress and the next useful concept.",
        "protocol": "Describe implemented machine-facing capabilities.",
        "goal": "View or set the active learning goal.",
        "session": "Start, resume, stop, or inspect the bounded study session.",
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

        if args.command == "status":
            snapshot = LearningService(
                _load_pack(root, args.pack), state, Scheduler()
            ).snapshot(datetime.now(UTC))
            if args.as_json:
                print(json.dumps(_snapshot_json(snapshot), ensure_ascii=False, indent=2))
            else:
                print(_snapshot_text(snapshot))
            return 0

        if args.command == "catalog":
            pack = _load_pack(root, args.pack)
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
            pack = _load_pack(root, args.pack)
            service = LearningService(pack, state, Scheduler())
            now = datetime.now(UTC)
            if args.command == "next":
                target = service.next_target(now)
                result = None
                if target is not None:
                    result = {
                        "identifier": target.concept.identifier,
                        "title": target.concept.title,
                        "prerequisites": list(target.concept.prerequisites),
                        "reason": target.reason,
                    }
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                memory = service.record(
                    args.concept_id, ReviewOutcome(args.outcome), now
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


def _load_pack(root: Path, requested_path: Path | None) -> CurriculumPack:
    pack_path = requested_path or Path("packs") / "ja-starter.toml"
    if not pack_path.is_absolute():
        pack_path = root / pack_path
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
    }


def _snapshot_json(snapshot: ProgressSnapshot) -> dict[str, object]:
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
        "next": _target_json(snapshot.next_target),
        "session": _session_json(snapshot.session),
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
