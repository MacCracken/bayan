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
| [0003](0003-f64-parse-exact-fallback-not-eisel-lemire.md) | The f64 parser falls back to an exact decimal, not Eisel–Lemire | Accepted |
| [0004](0004-json-lookup-states-its-key-type-by-name.md) | A JSON object lookup states its key type in its name; the bare name is deprecated | Accepted |
| [0005](0005-the-data-format-modules-are-carved-out-of-the-stdlib.md) | The data-format modules are carved out of the cyrius stdlib, and bayan owns them | Accepted |
| [0006](0006-legacy-names-are-forwarding-aliases-in-one-last-module.md) | The pre-carve names are forwarding aliases in one module, which comes last | Accepted |
| [0007](0007-per-format-sublibs-beside-the-full-bundle.md) | Each format also ships as its own sublib, beside the full bundle | Accepted |
| [0008](0008-yaml-parses-into-the-json-value-tree.md) | YAML parses into the JSON value tree | Accepted |
| [0009](0009-toml-strings-are-decoded-in-the-parser.md) | TOML strings are decoded in the parser, not by an accessor | Accepted |

0001 and 0002 were written at 1.5.0, alongside `bayan_pdf_*`. They record the
two decisions in that module a future reader is most likely to try to
"simplify" — and in both cases the simplification has a specific, non-obvious
cost. 0003 (1.5.7) is the same kind of record for the f64 parser: the obvious
one-line fix to the reported defect would have left 936 wrong answers in a
390,000-input sample. 0004 (1.5.10) records why bayan's JSON object lookup
was deprecated rather than fixed in place: the in-place fix the filing
proposed would silently break every caller passing a non-literal C string.

0005–0009 were written at 1.6.1, after the fact, for decisions made between
1.0.0 and 1.5.3 that had no record but the CHANGELOG: the carve (0005), the
`_compat` aliases (0006), the per-format sublibs (0007), yaml parsing into the
json tree (0008) and decoding TOML strings in the parser (0009). Each gives the
release that made the decision and marks any alternative the record does not
mention. 0009 matters most for what comes next: its reasoning is the case for
yaml's escapes on the roadmap (1.8.0).
