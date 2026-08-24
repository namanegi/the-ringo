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
uv run ringo catalog
uv run ringo catalog --json
uv run ringo doctor --json
uv run ringo protocol
```

The initialization command creates `.ringo/state.sqlite3`. That directory is
ignored by Git and must not contain API keys.

## Current status

The repository currently contains the M1 curriculum-kernel slice:

- a local SQLite state store;
- idempotent learner initialization;
- a validated, prerequisite-aware curriculum object model;
- a TOML curriculum-pack loader with a small Japanese starter pack;
- `ringo catalog` with human and agent-friendly JSON output;
- CLI diagnostics and a machine-readable protocol description;
- the desktop-agent skill contract;
- architecture notes and tests.

Exercise generation, scheduling, grading, additional language packs, and the TUI
are the next implementation slices. A custom pack can be inspected with
`uv run ringo catalog --pack path/to/pack.toml`; relative paths are resolved
from the selected project root. See [`docs/architecture.md`](docs/architecture.md).
The scoped delivery plan lives in [`docs/milestones/`](docs/milestones/README.md).

## Development

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
