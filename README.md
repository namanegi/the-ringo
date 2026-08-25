# the-ringo

> Agentic content. Deterministic learning state.

**the-ringo** is a local-first language-learning engine designed to be driven by
desktop agents, API models, or local models without depending on a hosted course
backend.

The model may generate exercises, explanations, and semantic feedback. The
repository remains the authority for learner state, scheduling, validation, and
progress history.

## Why this shape

- **Local-first:** learner data stays in an ignored `.ringo/` directory.
- **Agent-friendly:** a desktop agent can follow `SKILL.md` and call the CLI.
- **Provider-agnostic:** future app-owned model integrations live behind a
  separate provider boundary.
- **Inspectible:** state transitions are deterministic and testable.
- **Small by default:** the foundation uses only the Python standard library at
  runtime.

## Execution modes

```text
Agent-hosted (MVP)                 App-hosted (later)

User                              User
  |                                 |
Desktop agent                     the-ringo TUI
  |                                 |
SKILL.md -> ringo CLI             ModelProvider
              |                     |
              +---- Learning Core --+
                         |
                    local state
```

In agent-hosted mode, the agent owns the conversation and calls `ringo`; it is
an `AgentBridge`, not a model API. In app-hosted mode, the application owns the
conversation and calls a `ModelProvider`.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run ringo init --native-language zh-CN --target-language ja
uv run ringo configure --daily-items 12 --new-content-ratio 0.3 --explanation-style "brief, example-first, and encouraging"
uv run ringo goal --set "Prepare for a Japanese business interview"
uv run ringo goal --json
uv run ringo course --json
uv run ringo session --json
uv run ringo catalog
uv run ringo catalog --json
uv run ringo status
uv run ringo status --json
uv run ringo doctor --json
uv run ringo protocol
```

The initialization command creates `.ringo/state.sqlite3`. That directory is
ignored by Git and must not contain API keys.

Then point a desktop agent at `SKILL.md` and ask it to begin learning. The agent
will confirm the goal and question count, create a small local course plan when
needed, and resume unfinished sessions from CLI state.

## Current status

The repository currently contains the M1–M5 goal-driven learning loop:

- a local SQLite state store;
- idempotent learner initialization;
- a validated, prerequisite-aware curriculum object model;
- a TOML curriculum-pack loader with a small Japanese starter pack;
- `ringo catalog` with human and agent-friendly JSON output;
- CLI diagnostics and a machine-readable protocol description;
- persistent scheduling, preferences, and compact `ringo status` output;
- durable learning goals and bounded resumable sessions;
- agent-authored, validated competency plans without a stored question bank;
- compact activity evidence, progression guards, and explainable goal closure;
- the desktop-agent skill contract;
- architecture notes and tests.

M5 passed its isolated clean-room Agent role play and release gate on
2026-08-25. The current `0.1.0` package version is the MVP release candidate;
see the [M5 closeout report](docs/acceptance/M5-closeout.md).

The desktop agent still owns exercise generation, explanation, and semantic
grading. A standalone TUI and model-provider adapters remain later slices.
`ringo status --json` exposes the learner, course, session, competency evidence,
and `continue`, `expand`, or `complete` next action. A custom goal plan can be
imported with `uv run ringo course apply path/to/pack.toml`; a deliberate legacy
override remains available through `--pack`. See
[`docs/architecture.md`](docs/architecture.md).
The scoped delivery plan lives in [`docs/milestones/`](docs/milestones/README.md).

## Development

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
