from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from the_ringo import __version__
from the_ringo.state import LocalState, StateConflictError

PROTOCOL = {
    "protocol_version": 1,
    "application_version": __version__,
    "capabilities": ["local_state", "learner_initialization", "diagnostics"],
    "commands": {
        "init": "Initialize one local learner profile.",
        "doctor": "Inspect local state and runtime health.",
        "protocol": "Describe implemented machine-facing capabilities.",
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

        if args.command == "protocol":
            print(json.dumps(PROTOCOL, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    except (OSError, ValueError, StateConflictError) as error:
        print(f"ringo: error: {error}", file=sys.stderr)
        return 2

    return 1

