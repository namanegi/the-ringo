# Architecture

## Product boundary

the-ringo is a learning engine, not a hosted content service. It owns the
learner's durable state and deterministic policies while allowing an LLM to
produce flexible language content.

```text
                    +-------------------+
                    |   Learning Core   |
                    | planner/scheduler |
                    | validator/events  |
                    +---------+---------+
                              |
              +---------------+---------------+
              |                               |
      AgentBridge                        ModelProvider
   host calls the CLI                app calls the model
              |                               |
    Codex/other desktop agent          API or local model
```

These interfaces are intentionally separate. A desktop agent is usually the
orchestrator, so treating it as a callable model provider would reverse the
actual control flow.

## Responsibilities

### Learning Core

- select due and new concepts;
- enforce prerequisite and step-size policies;
- validate structured exercise and grading payloads;
- update mastery and review schedules;
- append immutable learning events;
- expose machine-readable commands.

### AgentBridge

- teach a host agent when and how to call the CLI;
- request structured content from the host model;
- present exercises and explanations to the learner;
- submit validated outcomes back to the core.

The first bridge is the root `SKILL.md` file.

### ModelProvider

- generate structured exercises and explanations for an app-owned session;
- grade answers that cannot be checked deterministically;
- expose model identity and capability metadata.

No provider implementation belongs in the foundation slice.

## Persistence

`.ringo/state.sqlite3` is the local source of truth. The initial schema contains
metadata, one learner profile, and an append-only event log. Later migrations
will add concepts, exercises, attempts, and memory state without making chat
history authoritative.

Properties we preserve:

- schema versioning;
- idempotent initialization;
- transactional writes;
- JSON event payloads with stable event identifiers;
- no credentials in learner state;
- exportability before cloud synchronization exists.

## Planned learning loop

```text
select target -> request exercise -> validate -> present
      ^                                      |
      |                                      v
update schedule <- record event <- grade <- answer
```

Objective answers should be graded by code first. Free-form answers may be
graded by a model, but model identity, rubric, confidence, and raw feedback must
be retained so the result can be reviewed.

## Near-term slices

1. Foundation: CLI, state, protocol, and Skill contract.
2. Curriculum graph: concepts, prerequisites, and a minimal language pack.
3. Learning loop: exercise contracts, attempts, and deterministic scheduling.
4. Agent experience: complete Skill workflow and golden session fixtures.
5. TUI: a polished local interface using the same core.
6. Providers: OpenAI-compatible and local-model adapters.

