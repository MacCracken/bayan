# bayan — Roadmap

> Milestone plan through v1.0. State lives in [`state.md`](state.md);
> this file is the sequencing — what ships, in what order, against
> what dependency gates.

## v1.0 criteria

_Define before tagging v0.1.0:_

- [ ] Public API frozen — every exported symbol documented and tested
- [ ] Test coverage adequate for the surface area
- [ ] Benchmarks captured in `docs/benchmarks.md`
- [ ] At least one downstream consumer green
- [ ] CHANGELOG complete from v0.1.0 onward
- [ ] Security audit pass (`docs/audit/YYYY-MM-DD-audit.md`)

## Milestones

### M0 — Scaffold (v0.1.0) — ✅ shipped 2026-06-09

- `cyrius init` scaffold landed
- Doc-tree per [first-party-documentation.md](https://github.com/MacCracken/agnosticos/blob/main/docs/development/applications/first-party-documentation.md)
- ADRs / architecture notes / guides / examples folders ready

### M1 — _Title_ (v0.2.0)

_Replace this with the first real milestone. Specify the user-visible change, the dep gates, and the acceptance criteria._

### M2 — _Title_ (v0.3.0)

_…_

### Markdown parsing — `bayan_markdown_*` (planned)

Add CommonMark (+ GFM) markdown as another data-format parser alongside
`json` / `toml` / `cyml` / `csv`. bayan already parses structured text (the
`toml` / `cyml` block + key/value machinery), so a markdown block/inline
parser reuses the same tokenize → AST approach — modest effort, high reuse.

- **Driver:** the **mneme** note-taking / knowledge-base Rust→Cyrius port needs
  a note model + markdown→HTML export. mneme hand-rolls a markdown subset in the
  interim and migrates to `bayan_markdown_*` once this lands, so no consumer
  hand-rolls a second one.
- **Scope:** `bayan_markdown_parse(src) -> AST` (headings, paragraphs, lists,
  code blocks/spans, links, images, emphasis, blockquotes, thematic breaks) +
  GFM extensions (tables, task lists, strikethrough, autolinks) +
  `bayan_markdown_to_html`. Consider opt-in wiki-links (`[[...]]`) for note/PKM
  consumers.
- **Acceptance:** round-trips a CommonMark spec fixture subset; GFM extensions
  behind a flag; downstream consumer (mneme) green; folds byte-identical into
  `cyrius/lib/bayan.cyr` per the sandhi pattern.

## Post-v1.0 / P2 backlog

_Wanted, but not gating v1.0 — heavier lifts scheduled after the text-format
surface freezes._

### PDF read/write — `bayan_pdf_*` (P2)

Add PDF as a document format alongside the text formats — a **writer** first
(the common export need) and a **reader** for text extraction / import. P2 (not
v1.0): it's a much heavier lift than the text parsers (binary object graph, xref
tables, stream filters, font metrics), and its one known consumer (mneme) already
ships a working hand-rolled writer, so there's no v1.0 blocker.

- **Driver:** the **mneme** port needs note→PDF export and (later) PDF→note
  import. mneme currently **hand-rolls a PDF writer** (`io_export_pdf`:
  catalog/pages/font objects + byte-accurate xref, markdown flattened to text
  blocks with word-wrap + pagination; all 8 tests + the API `/export/pdf` green) —
  the same interim play as the markdown subset. It migrates to `bayan_pdf_*` once
  this lands so no consumer maintains a second PDF stack.
- **Scope (writer):** `bayan_pdf_new() -> doc`, page/text/graphics ops, standard
  14 fonts → later embedded TrueType/Type1 fonts (hmtx metrics for wrapping),
  images, `bayan_pdf_to_bytes(doc)`. Reuse a markdown AST (`bayan_markdown_*`) →
  laid-out PDF as the high-level path. **Scope (reader):** `bayan_pdf_parse(bytes)`
  → object graph + `bayan_pdf_extract_text(doc)` (content-stream text ops, stream
  decompression via `bayan`/deflate) — the piece the mneme hand-roll skips entirely.
- **Acceptance:** writer output opens in mupdf/poppler and round-trips text;
  reader extracts text from its own + a reference PDF; downstream consumer (mneme)
  green; folds into `cyrius/lib/bayan.cyr` per the sandhi pattern.

## Out of scope (for v1.0)

_Capture what's deliberately NOT in scope for v1.0. The list keeps future contributors from adding to v1.0 by accident._

- _e.g. Windows support, GUI front-end, etc._
