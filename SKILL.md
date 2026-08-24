---
name: the-ringo
description: Use the local the-ringo repository to initialize, inspect, and eventually run persistent language-learning sessions when the user asks to study or manage their learning progress.
---

# the-ringo agent bridge

Use the `ringo` CLI as the sole authority for persistent learner state. The
conversation may be temporary; `.ringo/state.sqlite3` is not.

## Current workflow

1. Run `ringo doctor --json` before relying on learner state.
2. If the project is not initialized, ask for the native and target languages,
   then run `ringo init --native-language <tag> --target-language <tag>`.
3. Run `ringo protocol` to discover the currently implemented capabilities.
4. Do not invent commands or claim that an unlisted capability is implemented.

## State rules

- Never edit `.ringo/state.sqlite3` directly.
- Never store API keys, access tokens, or model credentials in `.ringo`.
- Treat CLI errors as authoritative; report them instead of silently repairing
  state.
- Do not infer progress from chat history when persisted state is available.
- Keep generated content separate from committed language-pack source data.

The current foundation supports setup and diagnostics. Study-session commands
will be added with the learning-loop slice.

