# bayan — Roadmap

> Milestone plan through v1.0. State lives in [`state.md`](state.md);
> this file is the sequencing — what ships, in what order, against
> what dependency gates.

## v1.0 criteria

_Define before tagging v0.1.0:_

- [ ] Public API frozen — every exported symbol documented and tested
- [ ] Test coverage adequate for the surface area — `coverage --min 30` holds
      at 36%, but `bigint` (0/20), `cyml` (0/17) and `csv` (0/3) are still
      referenced by no test in bayan's own suite
- [x] Benchmarks captured in [`docs/benchmarks.md`](../benchmarks.md) — 1.5.0
- [x] A real fuzz harness over untrusted input — 1.5.0
- [ ] At least one downstream consumer green — mneme's migration to
      `bayan_pdf_*` is the live one
- [x] CHANGELOG complete from v1.0.0 onward
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

### YAML parsing — `bayan_yaml_*` — ✅ shipped in 1.2.0 (2026-07-16)

Shipped as scoped below: `bayan_yaml_parse*` → the shared `bayan_json_v_*`
tagged value tree, plus `bayan_yaml_frontmatter_split`; per-call state and
the 128 depth cap from day one; every out-of-subset form rejects loudly
(hardened by a pre-release adversarial review — 6 parser bugs fixed and
pinned). Remaining: the two consumers (agnosai definitions, mneme
frontmatter) migrate on their next bayan re-pin / cyrius refold.

Add YAML as another data-format parser alongside `json` / `toml` / `cyml` /
`csv`. Same tokenize → key/value approach as the existing block parsers —
the `toml` / `cyml` machinery (quote stripping, comment skipping, flow-list
`[a, b]` splitting) covers most of the subset that real consumers need.

- **Drivers (two consumers, convergent):**
  - **agnosai** (agent-orchestration port) — definition-file loading behind
    its `definitions` feature. Filed:
    [2026-07-16 issue](issues/2026-07-16-agnosai-yaml-parse-into-tagged-value-tree.md)
    (originally noted only in agnosai's port-plan "Upstream filings" table).
    Its ask fixes the output shape: parse into **the existing `JTAG_*`-tagged
    `bayan_json_v_*` value tree**, not a new YAML AST, so one loader traverses
    one node type across JSON and YAML — the serde-data-model property the
    Rust original has.
  - **mneme** (note-taking port) — notes are Markdown with optional YAML
    frontmatter. mneme hand-rolls a YAML-ish subset in
    `src/core_frontmatter.cyr` (~200 lines: `key: value` lines, one-layer
    quote stripping, flow-list tags, an extras map) — the same interim play as
    its markdown subset. Pairs with the markdown item (`bayan_markdown_*` +
    frontmatter split is the full note-parsing story).

  Both migrate to `bayan_yaml_*` once this lands, so no consumer hand-rolls a
  second one.
- **Scope:** pragmatic YAML subset, not full YAML 1.2 —
  `bayan_yaml_parse(src)` (+ `_a` allocator variant) → `bayan_json_v_*` node
  tree, covering block mappings (`key: value`), nested mappings by
  indentation, block sequences (`- item`), flow sequences (`[a, b, c]`),
  scalars with single/double-quote stripping, and `#` comments. Explicitly
  out: anchors/aliases, tags (`!!`), multi-document streams, block scalars
  (`|` / `>`) unless a consumer needs them. Per-call parser state (thoth
  cursor lesson) and a recursion-depth cap (agnosai JSON filing) from day one.
  Include a `bayan_yaml_frontmatter_split(md)` helper (split `---` fences →
  yaml + body) since frontmatter is a known consumer shape.
- **Acceptance:** parses agnosai definition fixtures and mneme frontmatter
  fixtures into trees the existing `bayan_json_v_*` accessors traverse;
  documented subset boundary (what's rejected vs. silently mis-parsed —
  reject loudly); both downstream consumers green; folds byte-identical into
  `cyrius/lib/bayan.cyr` per the sandhi pattern.

## Post-v1.0 / P2 backlog

_Wanted, but not gating v1.0 — heavier lifts scheduled after the text-format
surface freezes._

### PDF read/write — `bayan_pdf_*` — ✅ shipped in 1.5.0 (2026-08-21)

Shipped as `src/pdf.cyr` — 9,348 lines, 152 public functions. **Writer**:
pages, the standard-14 fonts with AFM metrics derived from Adobe's own data,
text and graphics operators, `/Info`, optional Flate, byte-accurate xref with a
self-check. **Reader**: xref tables and 1.5 xref streams, `/Prev` chains,
object streams, four filters, PNG and TIFF predictors, inherited page
attributes, and text extraction that follows the font — `/ToUnicode` CMaps,
`/Type0` two-byte codes, `/Encoding /Differences`, and the WinAnsi / MacRoman /
Standard base encodings.

Against the acceptance criteria as originally written:

- *"writer output opens in mupdf/poppler and round-trips text"* — met, and
  gated by something stricter. `scripts/pdfcheck.py` validates every xref
  offset against the byte it claims to point at; mupdf and poppler would
  reconstruct a broken table by scanning for `N 0 obj` and hide exactly that
  class of bug.
- *"reader extracts text from its own + a reference PDF"* — met on its own
  output and on `nasmdoc.pdf` (357 pages, 5,706 objects), `glm/manual.pdf`
  (Type0 / Identity-H) and `speex/manual.pdf`.
- *"downstream consumer (mneme) green"* — **outstanding.** mneme still ships
  its hand-roll; the migration is the next step and is what closes the v1.0
  consumer criterion.
- *"folds into `cyrius/lib/bayan.cyr`"* — the bundle is regenerated and
  consumer-checked, but the cyrius refold has not happened yet.

Deliberately **not** in 1.5.0, and each for a stated reason: encryption
(detected and rejected — the standard security handler is `sigil` territory and
would recreate the fold-ordering hazard the Flate hooks exist to avoid);
`LZWDecode` (rejected by name); and a layout/flow API, which wants a markdown
AST that does not exist yet — see the markdown item above.

## Out of scope (for v1.0)

_Capture what's deliberately NOT in scope for v1.0. The list keeps future contributors from adding to v1.0 by accident._

- **PDF encryption.** Detected and rejected with a specific message. Even
  "empty user password" documents need the full standard security handler
  (MD5/RC4/SHA-256/AES-CBC), which is `sigil`'s domain; pulling it in would
  recreate the module-ordering hazard in the cyrius fold that the Flate hooks
  were designed to avoid.
- **PDF rendering.** bayan writes and reads PDF structure and text. Rasterising
  a page is a different problem and belongs with the image/graphics stack.
- **`LZWDecode` and the image codecs** (`DCTDecode`, `JPXDecode`,
  `CCITTFaxDecode`, `JBIG2Decode`). Rejected by name rather than silently
  passed through, because returning still-encoded bytes as "text" is the
  silent-wrong-answer shape this library refuses.
- **Full YAML 1.2.** The subset is documented and everything outside it is
  rejected loudly.
