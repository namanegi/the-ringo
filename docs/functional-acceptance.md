# Functional acceptance

the-ringo is accepted as a learning product through observable study behavior,
not only through command coverage. Unit tests protect deterministic state; an
isolated Luna role play verifies that the Skill produces a coherent lesson.

## Default learning contract

When the learner does not request a custom method, the product must provide this
closed loop:

```text
goal -> session contract -> progressive practice -> evidence -> goal check
  ^                                                        |
  +---------------- next-course proposal ------------------+
```

The default policy is intentionally small:

1. Confirm and persist one active learning goal.
2. Confirm a concrete question count, defaulting to `daily_items`.
3. Resume the same bounded session across agent tasks until the count is met or
   the learner stops it.
4. Select due work first, then unmet goal competencies, while avoiding immediate
   repetition when another useful target exists.
5. Record compact evidence for each attempt: competency, activity key, and
   outcome. Do not store a generated question bank.
6. Completion of a question count ends the session, not necessarily the goal.
   A goal completes only when every required competency has successful evidence
   from distinct activities under the default mastery policy.
7. End every session with either the remaining gaps and a recommended next
   session, or a small set of follow-up course proposals when the goal is met.
8. If the current plan cannot supply useful content before the goal is met,
   request a plan extension instead of repeating one concept forever.

The exact mastery threshold remains customizable. The built-in policy should be
conservative and explainable; the first implementation may use two successful,
distinct activities per required competency.

## Responsibility boundary

| Core guarantees | Agent supplies |
| --- | --- |
| durable goal and session count | natural-language goal clarification |
| validated competency plan | goal-specific course draft |
| target selection and repetition guard | exercises and explanations |
| attempt evidence and mastery decision | semantic grading rationale |
| `continue`, `expand`, or `complete` next action | learner-facing next-course proposals |

The agent may make the experience fancy, but a fresh agent task must be able to
recover every product decision from CLI state.

## Acceptance scenarios

### A. Goal and restart

- A Chinese-speaking learner sets “prepare for a Japanese business interview.”
- A fresh agent task reads the same active goal without chat history.
- Changing the goal is explicit and does not silently erase prior events.

### B. Bounded lesson

- With `daily_items = 6`, the agent proposes six questions and waits for assent.
- An override such as three questions is persisted in the active session.
- The lesson resumes after an agent restart and stops at exactly the agreed
  count unless the learner stops early.

### C. Progressive content

- The business-interview plan covers multiple relevant competencies rather than
  mapping the whole goal to generic greetings.
- A six-question lesson exercises at least three eligible competencies when the
  plan permits it.
- No competency appears more than twice consecutively when another useful target
  is eligible.
- Generated wording may vary; acceptance checks activity keys and progression,
  not exact prose.

### D. Goal evidence and closure

- Finishing six questions alone cannot mark the business-interview goal complete.
- Weak or missing competencies are named at session end.
- Distinct successful evidence for every required competency completes the goal.
- Completion produces follow-up course proposals; incomplete coverage produces
  a recommended next session or an `expand` action.

### E. Continuous supply

- Exhausting current activities before mastery returns a machine-readable plan
  extension request.
- Applying a valid extension makes another useful target available.
- A completed goal does not fall back into endless practice of the same range.

## Lightweight release gate

Each milestone needs only:

- focused tests for new state and selection invariants;
- one clean-room CLI flow;
- one isolated Luna role play using a copied learner database;
- a short PASS/PARTIAL/FAIL matrix with CLI evidence.

Never run role play against the learner's real `.ringo` directory. The original
database's event count and status must be unchanged after acceptance.

## M5 closeout — 2026-08-25

The post-M5 clean-room run passed the release gate. A Luna tutor Agent used an
isolated copy of the learner database, resumed the persisted goal and
preferences, completed a six-question lesson across a simulated Agent-task
restart, and closed the goal with two distinct successful activities for each
of three competencies. The original learner database remained unchanged.

| Capability | Result | Evidence |
| --- | --- | --- |
| target setting | PASS | persisted business-interview goal shaped a three-competency plan |
| question count | PASS | the resumed session stopped at exactly 6/6 |
| continuous lesson | PASS | all six attempts were recorded once across a restart |
| goal attainment | PASS | each competency reached two distinct successful activities |
| next-course proposal | PASS | completion produced three Agent-authored follow-up proposals |
| progressive content | PASS | three competencies appeared in prerequisite order, then varied practice |

Acceptance scenarios A–E and the detailed CLI evidence are recorded in the
[M5 closeout report](acceptance/M5-closeout.md).

## Pre-M4 baseline — 2026-08-25

Before the goal/session and course-progression milestones, an isolated
six-question business-interview role play produced four greetings targets and
two self-introduction targets.

| Capability | Result | Evidence |
| --- | --- | --- |
| target setting | PARTIAL | request influenced prompts, but the goal was not durable |
| question count | PASS | default six was confirmed |
| continuous lesson | PASS | six attempts were recorded without early termination |
| goal attainment | PARTIAL | attempts were graded, but no goal-level decision existed |
| next-course proposal | FAIL | the session ended after the sixth record |
| progressive content | FAIL | greetings repeated four times with little progression |
