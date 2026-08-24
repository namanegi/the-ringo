# M3 — Agent Experience

## Outcome

A user can clone the repository, initialize a learner, point a compatible
desktop agent at the Skill, and run a short persistent study flow. Human-facing
status output feels polished while the machine contract stays compact.

Branch: `milestone/m3-agent-experience`

## Steps

### M3.1 — Focused learner preferences

Add only preferences that immediately affect an agent-hosted lesson: daily item
count, new-content ratio, and explanation style. Represent them as one cohesive
value object and expose a small `ringo configure` command.

### M3.2 — Complete the Skill workflow

Teach the desktop agent to inspect state, request the next concept, generate one
exercise, evaluate the answer, and record one outcome. Include concise JSON
examples and recovery behavior without embedding a giant tutoring prompt.

### M3.3 — Fancy compact status and end-to-end polish

Add `ringo status` with a dependency-free, readable terminal summary and a JSON
variant. Tighten onboarding and README instructions, then run a fresh-directory
end-to-end check.

## Acceptance

- configuration is optional and has sensible defaults;
- `SKILL.md` describes only commands that exist;
- `ringo status` shows learner, progress, due work, and the next useful action;
- no credentials or generated learner data are committed;
- the complete core remains easy to inspect and customize.

## Out of scope

Hosted accounts, cloud sync, voice, streak gamification, CI matrices, and a full
screen TUI. Those should be justified by real usage after this milestone.
