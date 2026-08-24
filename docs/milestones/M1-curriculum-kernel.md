# M1 — Curriculum Kernel

## Outcome

the-ringo can load a compact, customizable curriculum pack and expose its
ordered concepts to a desktop agent. The core understands prerequisites without
owning a large vocabulary or question bank.

Branch: `milestone/m1-curriculum-kernel`

## Steps

### M1.1 — Curriculum objects

Introduce the smallest useful object model for a concept and curriculum.
Validate identifiers, duplicate concepts, missing prerequisites, and cycles.
Keep serialization concerns outside the objects.

### M1.2 — TOML pack loader and starter pack

Add a standard-library TOML loader and one deliberately small Japanese starter
pack. The pack is demonstration content, not a canonical course. Do not add a
generic plugin system or language-specific subclasses.

### M1.3 — Catalog command

Add `ringo catalog` with compact human output and `--json` output suitable for an
agent. Add only focused tests for loading and ordering behavior, then update the
README quick start.

## Acceptance

- `ringo catalog --json` returns a stable prerequisite-respecting order;
- a custom pack path can be supplied without changing Python code;
- invalid references and cycles fail with a useful message;
- the starter pack stays small enough to understand by reading one file.

## Out of scope

Scheduling, generated exercises, grading, broad language coverage, and TUI work.

