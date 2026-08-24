# M5 — Course Progression and Closure

## Outcome

An agent can turn the active goal into a small validated competency plan, provide
varied progressive practice, decide whether the goal has evidence of mastery,
and finish with a useful next-course proposal.

Branch: `milestone/m5-course-progression`

## Steps

### M5.1 — Goal-shaped course plan

Introduce a compact `CoursePlan` composed of required competencies. Let the agent
draft or extend it while the core validates identifiers, ordering, prerequisites,
and scope. Reuse the curriculum graph instead of building a second framework.

### M5.2 — Evidence-aware progression

Record only the activity key and outcome needed to distinguish practice evidence.
Teach target selection to balance due work, unmet competencies, and a small
repetition guard. Return `expand` when the plan lacks useful coverage rather than
practising one concept indefinitely.

### M5.3 — Goal check and next proposal

Add an explainable default mastery policy, session-end gap reporting, and the
machine-readable next action `continue`, `expand`, or `complete`. Update the Skill
so the agent presents either the next session or a few goal-shaped follow-up
course proposals.

## Acceptance

- a business-interview plan covers multiple interview competencies;
- a six-question lesson uses at least three eligible competencies and respects
  the repetition guard;
- question count completion and goal completion remain distinct;
- every goal decision cites persisted evidence;
- an exhausted incomplete plan requests expansion;
- a completed goal ends cleanly and produces follow-up proposals;
- the functional acceptance scenarios pass in an isolated Luna role play.

## Out of scope

A hosted content backend, stored generated question banks, embeddings, elaborate
rubrics, voice, provider adapters, and heavy end-to-end infrastructure.

