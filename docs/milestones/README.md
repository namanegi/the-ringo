# Milestones

The implementation is intentionally split into small, vertical milestones.
Each milestone lives on its own branch and is merged through a reviewed pull
request before the next one starts.

Design constraints for every milestone:

- prefer a few cohesive objects over framework-style layers;
- keep diffs short enough to review in one sitting;
- add only tests that protect behavior or a state invariant;
- avoid CI, provider integrations, and speculative schemas;
- keep learner content and policy customizable outside the core;
- preserve the agent-hosted control flow: the agent calls the engine.

## Sequence

1. [M1 — Curriculum Kernel](M1-curriculum-kernel.md)
2. [M2 — Learning Loop](M2-learning-loop.md)
3. [M3 — Agent Experience](M3-agent-experience.md)
4. [M4 — Goal and Session Contract](M4-goal-and-session.md)
5. [M5 — Course Progression and Closure](M5-course-progression.md)

Product-level behavior is governed by the lightweight
[functional acceptance contract](../functional-acceptance.md).
