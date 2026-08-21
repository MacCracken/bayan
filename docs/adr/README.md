# Architecture Decision Records

Decisions about bayan — what we chose, the context, and the consequences we accept. Use these when a future reader would reasonably ask *"why did we do it this way?"*

## Conventions

- **Filename**: `NNNN-kebab-case-title.md`, zero-padded to four digits. Never renumber.
- **One decision per ADR.** If a decision supersedes a prior one, add a new ADR and set the old one's status to `Superseded by NNNN`.
- **Status lifecycle**: `Proposed` → `Accepted` → (optionally) `Superseded` or `Deprecated`.
- Use [`template.md`](template.md) as the starting point.

## ADR vs. architecture note vs. guide

| Kind | Lives in | Answers |
|---|---|---|
| ADR | `docs/adr/` | *Why did we choose X over Y?* |
| Architecture note | `docs/architecture/` | *What non-obvious constraint is true about the code?* |
| Guide | `docs/guides/` | *How do I do X?* |

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-flate-via-hooks-not-a-sankoch-dependency.md) | Flate compression via consumer-installed hooks, not a sankoch dependency | Accepted |
| [0002](0002-pdf-objects-do-not-reuse-the-json-value-tree.md) | The PDF object graph does not reuse the JSON value tree | Accepted |

Both were written at 1.5.0, alongside `bayan_pdf_*`. They record the two
decisions in that module a future reader is most likely to try to "simplify" —
and in both cases the simplification has a specific, non-obvious cost.
