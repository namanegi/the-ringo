---
name: the-ringo
description: Run a local, persistent language-learning session through the the-ringo CLI.
---

# the-ringo desktop-agent workflow

Use the `uv run ringo` CLI as the only interface to persisted learner state.
Run every command from the repository root. The conversation is temporary;
`.ringo/state.sqlite3` is not. CLI state is authoritative: never edit SQLite,
infer progress from chat history, or invent commands.

## Commands

Only use these commands:

```text
uv run ringo protocol
uv run ringo doctor --json
uv run ringo status --json [--pack <path>]
uv run ringo init --native-language <tag> --target-language <tag>
uv run ringo configure [--daily-items N] [--new-content-ratio R] [--explanation-style <free text>]
uv run ringo catalog --json [--pack <path>]
uv run ringo next --json [--pack <path>]
uv run ringo goal --json
uv run ringo goal --set "<learning goal>"
uv run ringo session --json
uv run ringo session start --items N --json
uv run ringo session stop --json
uv run ringo record <concept-id> --outcome again|hard|good [--pack <path>]
```

`protocol` describes the implemented capabilities; it does not accept
`--json`. `--pack` is optional and must be passed consistently to `status`,
`catalog`, `next`, and `record` when using a custom TOML pack. Do not modify a
pack during a session.

## Start-up and session recovery

1. From the repository root, run `uv run ringo doctor --json`. If `initialized`
   is false, ask for both language tags and run `init` before teaching.
2. Run `uv run ringo status --json`, then `uv run ringo goal --json` and
   `uv run ringo session --json`. Run `uv run ringo configure` to read saved
   preferences, especially `daily_items`, `new_content_ratio`, and
   `explanation_style`.
3. If there is no active goal, ask the learner to confirm a concise learning
   goal, then persist it with `uv run ringo goal --set "..."`. Do not treat a
   chat-only goal as durable.
4. Only `session.status == "active"` is resumable. Tell the learner its goal
   snapshot and remaining count, then resume it without asking for a new
   question count. A `completed` or `stopped` session is a closed recent
   session: briefly summarize it, then enter the new question-count/start flow.
5. Before resuming an active session, compare its goal snapshot with the
   current active goal. If they differ, do not mix them: ask whether to resume
   the old session, or explicitly stop it and start a new session for the
   current goal. Only when there is no active session, or the old one was
   explicitly stopped, ask how many questions to do. If no number was
   specified, propose `daily_items` as the default and wait for confirmation
   (for example: “今天练几题？默认 5 题。”). Start the bounded session with
   `uv run ringo session start --items N --json`.

If the learner wants to change goals during an active session, explain that the
old session has a goal snapshot. Get explicit agreement to end it, run
`uv run ringo session stop --json`, then persist the new goal with
`uv run ringo goal --set "..."`; only after that start a new session. Never
silently mix two goal snapshots.

## Study loop

Repeat until the CLI session reports `completed`, or the learner asks to stop:

1. Run `uv run ringo next --json` and inspect the returned target. A target has
   an identifier, title, prerequisites, and a reason such as `new`, `review`,
   or `practice`.
2. Generate exactly one focused exercise and one concise explanation. Match
   the saved explanation style, use the learner's native language for support,
   and keep the exercise aligned with the active goal and target. Do not bundle
   several questions into one turn.
3. Assess the answer transparently:
   `again` means incorrect or fundamentally misunderstood; `hard` means
   substantially correct with a meaningful error, hesitation, or unnatural
   wording; `good` means correct and appropriate, allowing harmless variation.
   For open answers, distinguish grammatical correctness from naturalness.
4. Record the presented target exactly once before moving on:

   ```text
   uv run ringo record ja.greetings --outcome good
   ```

   Treat the record response's session progress as authoritative. If it is
   still active, continue with the next target; if it is completed, give a
   concise session summary and stop exactly there. Do not maintain a separate
   question counter in chat. If the learner voluntarily stops, run
   `uv run ringo session stop --json` and summarize the saved progress.

`reason: "practice"` is a valid target and counts toward the bounded session.
Use `new_content_ratio` as a soft guideline for balancing new content with
reviews, not as permission to repeat one concept indefinitely. Prefer due
reviews and curriculum-order progression; vary exercise form and context when
the target allows it.

## Completion and next steps

Finishing a bounded session is not the same as mastering the whole goal. After
the CLI session completes, summarize recorded outcomes and current progress.
Use `status --json` and `catalog --json` to identify remaining or next concepts.
Then propose a concrete next course or session: continue the current goal with
the next curriculum concepts, schedule review of weak concepts, or switch to a
new pack/goal. Do not claim the learning goal is achieved solely because the
question count is complete, and do not generate endless questions from the
same small range when the catalog is exhausted.

## Recovery and disagreement

- If `next --json` returns `null`, first run `status --json` and `catalog --json`
  (preserving the selected pack). Explain the persisted state and offer an
  actionable choice: expand or switch the pack, retry existing material, or
  inspect configuration. Do not fabricate an exercise or progress.
- If a CLI command errors, show the concise error, correct only the stated
  input problem, and retry. Do not reset state or edit SQLite.
- If the learner disagrees with a grade, show the evidence and proposed
  mapping. Let them clarify or request a different grade, then record the final
  outcome exactly once before continuing.
- If a custom pack is selected, use its exact path consistently for
  `status`, `catalog`, `next`, and `record`; if loading fails, report the CLI
  error and stop.

Keep the interaction focused, warm, and concise. The agent supplies generated
content, explanations, and grading; the-ringo supplies durable goals, bounded
session state, scheduling, and progress.
