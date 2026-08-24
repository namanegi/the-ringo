---
name: the-ringo
description: Run a local, persistent language-learning session through the the-ringo CLI.
---

# the-ringo desktop-agent workflow

Use the `uv run ringo` CLI as the only interface to persisted learner state.
Run every command from the repository root. The
conversation is temporary; `.ringo/state.sqlite3` is not. CLI state is
authoritative. Never edit SQLite, infer progress from chat history, or invent
commands.

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
uv run ringo record <concept-id> --outcome again|hard|good [--pack <path>]
```

`--pack` is optional and must be passed consistently to `catalog`, `next`, and
`record` when using a custom TOML pack. Do not modify the pack during a session.
For example: `uv run ringo configure --explanation-style "brief, example-first, and encouraging"`.

## Start-up

1. Run `uv run ringo doctor --json` and inspect its persisted report. If `initialized`
   is false, ask the learner for both language tags and initialize first.

2. Run `uv run ringo status --json` and inspect the compact progress view. A
   representative response is:

   ```json
   {"learner": {"native_language": "zh-CN", "target_language": "ja"}, "progress": {"started": 0, "total": 3}, "due_reviews": 0, "next": {"identifier": "ja.greetings", "reason": "new"}}
   ```

3. Run `uv run ringo configure` with no options to read the saved preferences. Treat
   `daily_items`, `new_content_ratio`, and `explanation_style` as the session
   settings. Do not change them unless the learner asks.

4. If the learner asks what is available, run `uv run ringo catalog --json` (or the
   same command with the chosen `--pack`) and use its ordered concepts. A
   representative concept is:

   ```json
   {"identifier": "ja.greetings", "title": "Basic greetings", "prerequisites": []}
   ```

Do not start teaching until initialization has succeeded. `uv run ringo protocol` is
available for capability inspection when needed; it does not replace `doctor`.

## Study loop

At session start, ask how many questions the learner wants to do. If they did
not specify a number, explicitly propose the saved `daily_items` value as the
default and wait for confirmation (for example, “今天练几题？默认 5 题。”).
Once a concrete count is agreed, treat it as this session's target and keep
going until that many targets have been completed, or until the learner
voluntarily stops. Never end the session after a single answer merely because
one target was completed. Each turn is exactly one target:

1. Run `uv run ringo next --json` and inspect the result. A target has this shape:

   ```json
   {"identifier": "ja.greetings", "title": "Basic greetings", "prerequisites": [], "reason": "new"}
   ```

2. Treat `reason: "new"` as new content and `reason: "review"` as due review.
   Treat `reason: "practice"` as a valid extra practice target and continue
   the session normally; it counts toward the agreed question total. Use
   `new_content_ratio` as a soft
   cap: aim for at most `agreed session target * new_content_ratio` new targets,
   rounding
   sensibly. Prefer due review targets after reaching the guideline; if no
   suitable review exists, continue with a new target and state that the soft
   cap was exceeded.

3. For the target, generate exactly one focused exercise and one concise
   explanation. Match the saved `explanation_style`; keep the explanation
   appropriate to the learner's native language and target language. Do not
   bundle several questions into one turn.

4. Let the learner answer. Assess the answer transparently, briefly stating
   what was correct and the key issue. Map the result as follows:

   - `again`: incorrect, missing, or a fundamental misunderstanding;
   - `hard`: substantially correct but with a meaningful error, hesitation, or
     unnatural wording;
   - `good`: correct and appropriate for the exercise, including minor harmless
     variation.

   For an open-ended answer, explain uncertainty and distinguish grammatical
   correctness from naturalness. Do not pretend semantic grading is exact.

5. Before presenting another target, record the presented target:

   ```text
   uv run ringo record ja.greetings --outcome good
   ```

   Confirm the command succeeds. The returned memory shape is compactly:

   ```json
   {"concept_id": "ja.greetings", "interval_days": 1, "due_at": "...", "streak": 1, "last_outcome": "good"}
   ```

Never move to another target without recording the current one, even if the
learner skips or the session is ending.

## Recovery and disagreement

- If `uv run ringo next --json` returns `null`, first run `uv run ringo status --json` and
  `uv run ringo catalog --json` (preserving the selected `--pack` if any).
  Explain what the progress and catalog show, then offer an actionable choice:
  expand or switch the pack, retry existing material, or inspect the pack/state
  configuration. Do not fabricate an exercise, directly edit SQLite, or
  invent progress. Continue only after the learner chooses a valid next step;
  do not silently end just because one target was completed.
- If any CLI command errors, show the concise error, correct only the stated
  input problem, and retry. Do not edit SQLite or silently reset state.
- If the learner disagrees with a grade, show the evidence and the proposed
  mapping. Let them clarify or request a different grade, then record the
  final agreed `again`, `hard`, or `good` exactly once before continuing. If
  they do not choose, use the transparent assessment and record it.
- If a custom pack is selected, use its exact path with `catalog --json`,
  `next --json`, and `record`; if loading fails, report the CLI error and stop.

Keep the interaction focused, warm, and concise. The agent supplies generated
content and explanations; the-ringo supplies durable scheduling and progress.
