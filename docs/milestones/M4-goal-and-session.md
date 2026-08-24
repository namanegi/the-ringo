# M4 — Goal and Session Contract

## Outcome

A learner's purpose and the bounds of the current lesson survive agent-task
boundaries. The CLI, rather than chat history, answers what the learner is
working toward and how many questions remain.

Branch: `milestone/m4-goal-and-session`

## Steps

### M4.1 — Durable active goal

Add one cohesive `LearningGoal` value object and compact CLI operations to read
or set the active goal. Preserve changes as events; do not add accounts, goal
libraries, or speculative profile fields.

### M4.2 — Bounded resumable session

Add a `StudySession` contract containing the active goal, agreed item count,
completed count, and lifecycle state. Starting without an explicit count uses
`daily_items`; an unfinished session is resumed rather than silently replaced.

### M4.3 — Agent workflow and forward test

Expose goal and session progress in compact JSON, update the Skill to recover the
contract on startup, and run an isolated Luna role play across an agent restart.

## Acceptance

- a business-interview goal is available to a fresh agent task;
- the saved default count can be accepted or explicitly overridden;
- every recorded attempt advances the active session exactly once;
- the session stops at its agreed count and reports whether the goal remains open;
- existing concept memory and learner preferences continue to work;
- the diff contains only focused state, domain, CLI, Skill, and invariant tests.

## Out of scope

Automatic course planning, detailed attempt history, mastery rules, generated
question storage, providers, and a TUI.
