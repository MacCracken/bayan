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
| [0010](0010-markdown-parses-into-a-tree-of-its-own.md) | Markdown parses into a tree of its own | Accepted |
| [0011](0011-markdown-raw-html-is-text.md) | Markdown's raw HTML is text, and its dangerous URLs are dropped | Accepted |
| [0012](0012-public-constants-are-const-and-predicates-return-bool.md) | Public constants are `const`, and public predicates return `: bool` | Accepted |
| [0013](0013-toml-parses-into-the-json-value-tree-strictly.md) | TOML parses into the JSON value tree, strictly, by tomllib's answers | Accepted |
| [0014](0014-the-flat-lookups-name-their-key-type.md) | The flat lookups name their key type too; the bare names are deprecated | Accepted |

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
mention. 0009's reasoning is what 1.8.0 applied to yaml's quoted scalars.

0010 and 0011 were written at 1.9.0, with `bayan_markdown_*`. 0010 is the third
answer to the question 0002 and 0008 answered, whether a new format reuses the
json value tree, and says why markdown does not. 0011 records the cut-off the
roadmap asked to have documented: the part of CommonMark bayan does not
implement, and the safety reason for it.

0012 was written at 1.10.0, with the typed names. It records the rule that decided which names were
typed, by contract rather than by spelling, and so why a few functions whose value is 0 or 1 stay
`i64`.

0013 and 0014 were written at 1.11.0. 0013 is the fourth answer to whether a format reuses the json
value tree, after 0002, 0008 and 0010: TOML does, strictly, with tomllib as its oracle, and a date
is a string that remembers its kind. 0014 applies 0004's decision to the flat lookups, with the
6.7.16 measurement that the `: cstring` diagnostic now reaches every spelling 0004 found silent.
