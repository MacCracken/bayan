# Architecture notes

Non-obvious constraints, quirks, and invariants that a reader cannot derive from the code alone. Numbered chronologically — never renumber.

Not decisions (those live in [`../adr/`](../adr/)) and not guides (those live in [`../guides/`](../guides/)). An item here describes *how the world is*, not *what we chose* or *how to do something*.

## Items

- [001 — A `: Str` parameter is a handle, and three PDF constructors keep it](001-str-parameters-are-handles.md) (1.6.0; the analysis was made at the 6.6.6 pin, 1.5.7)
- [002 — A program holds one copy of each bayan module that declares a `const`](002-one-copy-of-each-module-per-program.md) (1.10.0, measured on 6.7.16)

Add the next as `003-kebab-case-title.md`. Do not write entries for decisions — those are ADRs.
