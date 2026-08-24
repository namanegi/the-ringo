# M2 — Learning Loop

## Outcome

the-ringo can choose a useful next concept, record a compact learning outcome,
and persist enough memory state to make the next session different. The loop is
deterministic; the desktop agent remains responsible for teaching and semantic
judgment.

Branch: `milestone/m2-learning-loop`

## Steps

### M2.1 — Memory and scheduling objects

Model one concept's memory state and a small scheduler with three outcomes:
`again`, `hard`, and `good`. Prefer transparent interval rules over a configurable
algorithm framework.

### M2.2 — Learning records in local state

Persist concept memory and append attempt events using the existing SQLite
store. Add only columns required by the scheduler. Keep migrations explicit and
small.

### M2.3 — Learning service and CLI loop

Introduce a cohesive service that combines curriculum, state, and scheduling.
Add `ringo next --json` and `ringo record` so an agent can complete a full turn.
Protect the end-to-end state transition with a small number of tests.

## Acceptance

- unseen prerequisite-ready concepts are introduced in curriculum order;
- due reviews take priority over new concepts;
- recording an outcome changes the next review state transactionally;
- the CLI returns stable JSON and clear errors for unknown concepts.

## Out of scope

Model calls, automatic semantic grading, complex spaced-repetition math, and
session-length optimization.

