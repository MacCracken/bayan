# bayan — Roadmap

> The open work, in release order. State lives in [`state.md`](state.md); what shipped, and why,
> lives in [`CHANGELOG.md`](../../CHANGELOG.md). An item is deleted from this file in the release
> that ships it, and its CHANGELOG entry is the record.
>
> The slots are a sequence, not a promise: one can move, split or merge when a filing or a cyrius
> pin changes what comes first. A 1.6.x patch changes no public signature and no answer to valid
> input. A minor names, up front, the change a consumer has to make.
>
> Cleaned 2026-10-15 (1.6.0): every finished section was removed (the pin moves to 6.6.6, 6.7.5,
> 6.7.9 and 6.7.11, the 6.6.13 / 6.6.16 follow-ups, YAML, PDF, M0 and the scaffold's empty M1 / M2).
> The 6.6.6 by-value `Str` analysis, the one part with no other home, is now
> [architecture note 001](../architecture/001-str-parameters-are-handles.md).
> 1.6.1 (2026-10-15) shipped its slot whole and removed it; its two kept cyml delimiter answers
> joined 1.7.0.
> 1.6.2 (2026-10-15) shipped its slot whole and removed it. So did 1.7.0, whose cyml line rule also
> covers the end of a region and a last line with no newline; it added 1.7.1 and a 1.8.0 item.

## 1.7.1 — patch: csv's allocation refusals

- **`src/csv.cyr` does not check its allocations the way the other modules now do** (Known gap 16,
  found while 1.7.0 rewrote the parser). `bayan_csv_escape` stores through an unchecked `alloc`,
  so a refusal writes to address 0. `bayan_csv_parse_line` answers a refused field copy with the
  fields it has so far, a short row a caller cannot tell from a real one. `bayan_csv_write_line`
  passes a refused escape's 0 to `strlen`. Return 0 on every refusal instead, and prove it with an
  every-allocation-point sweep, as 1.5.13 did for TOML and 1.6.1 for cyml. A patch: no answer to
  input changes, only what a refusal returns.

## 1.8.0 — minor: yaml decodes escapes; cyml reads CRLF lines

- **Double-quoted yaml scalars keep their `\` escapes verbatim** (`src/yaml.cyr:20`, `:371`: "no
  \-escape decoding — the toml convention"). That convention ended in 1.5.3, when toml started
  decoding in the parser, the only place that knows which quote produced a string (mneme's filing,
  [archived](issues/archived/2026-08-22-mneme-toml-basic-strings-not-unescaped.md), named yaml too).
  Pick the oracle before writing the code, as toml has `tomllib`. cyml needs nothing here: it returns
  its headers as raw TOML spans and decodes no values itself.
- **cyml: a CR does not end a line** (Known gap 17). `[[entries]]\r\n` and `---\r\n` are text, so a
  `.cyml` saved with CRLF line endings parses to no entries and one block of header text: neither
  its markers nor its `---` lines are seen, and nothing reports it. TOML allows CRLF, so the headers
  would be fine; only the two line tests are not. 1.7.0 settled what a marker or delimiter line is;
  let `\r\n` end one too. Check it as 1.7.0 did: a line-by-line Python model of the rule (rebuilt;
  1.7.0's was scratch) against the parser at every prefix of random documents, now with CRLF.

## 1.9.0 — minor: `bayan_markdown_*`

The data-format parser that remains on bayan's list. mneme hand-rolls a markdown subset until it
exists. Together with `bayan_pdf_wrap` it gives the whole "notes to a laid-out PDF" path, and the
layout API that PDF lacks needs this AST.

- **Scope:** `bayan_markdown_parse(src)` → AST (headings, paragraphs, lists, code blocks and spans,
  links, images, emphasis, blockquotes, thematic breaks), the GFM extensions (tables, task lists,
  strikethrough, autolinks) behind a flag, and `bayan_markdown_to_html`. Consider opt-in
  `[[wiki-links]]` for note-taking consumers. Use per-call parser state and a depth cap from day one,
  as yaml did.
- **Acceptance:** round-trips a CommonMark spec fixture subset, with the cut-off between what is
  rejected and what is accepted documented. Folds into `cyrius/lib/bayan.cyr` through the bundle, as
  every module does.

## 1.10.0 — minor: public names typed

Both items break source: a consumer's code can stop compiling. Before this release, check the
names against the other folds in cyrius `lib/`. A `const` beside a same-named `var` in another
fold is a hard error.

- **Public constants as `const`:** `JTAG_*`, `TOML_K_*`, `JSON_K_*` (new at 1.7.0), `JS_EV_*` and the
  public `PDF_*`, about 55 top-level `var`s. A `const` has no storage, so `&NAME` or an assignment stops compiling.
- **`: bool` on the 27 public predicates** (`bayan_*_is_*` / `_has_*`, e.g.
  `bayan_toml_pair_is_array`). A `: bool` return is type-checked, so integer use at a call site
  can stop compiling.

## 1.11.0 — minor: TOML into the tagged tree; one lookup key type

- **`bayan_toml_v_parse`** into json's value tree, the way yaml already parses. 1.5.4 gave dotted
  keys and inline tables real answers inside the flat model, so this is less urgent than it was. It
  is still the right shape for the surface, and it is the answer to the next item.
- **The two flat lookups disagree on their key type** (Known gap 7). `bayan_json_get` needs a
  `Str`, `bayan_toml_get` a cstring, and the wrong one is a silent "not found". The fix is
  ADR 0004's: name the key type in the function and deprecate the bare name. `bayan_toml_get`'s key
  should also carry `: cstring`, so the named-`Str` diagnostic can fire.
- **The two subset edges the flat model cannot express** (Known gap 1). A dotted key whose quoted
  segment contains a dot (`a."b.c".d`) joins into a name indistinguishable from `a.b.c.d`, and a
  `[[array-of-tables]]` under a dotted parent is not merged with a same-named sibling. A tree keeps
  the segments apart, so both get an answer there. In the flat API they stay documented.

## 1.12.0 — the frozen surface

These are the open half of the criteria the scaffold set for a stable surface. The met half: a
reference-coverage floor of 100 in CI, the benchmarks, the fuzz harnesses, and a complete CHANGELOG.

- **A security audit pass** written to `docs/audit/YYYY-MM-DD-audit.md`, covering every parser that
  reads untrusted input. Its fixes ship as patches.
- **Every exported symbol documented and tested.** Then the public API is called frozen, and later
  changes follow the deprecate-then-remove path.
- (Not bayan's work, but part of the criterion: one downstream consumer green on the frozen
  surface.)

## Gated on cyrius — no slot until the gate opens

- **The SAX callbacks and the Flate hooks → traits**, once cyrius ships checked `dyn`. Today both
  are hand-rolled fn-pointer dispatch, and [ADR 0001](../adr/0001-flate-via-hooks-not-a-sankoch-dependency.md)
  explains why Flate is a hook.

## Out of scope

This list keeps work from being added by accident.

- **PDF encryption.** Detected and rejected with a specific message. Even "empty user password"
  documents need the full standard security handler (MD5/RC4/SHA-256/AES-CBC), which is `sigil`'s
  domain. Pulling it in would recreate the module-ordering hazard in the cyrius fold that the Flate
  hooks were designed to avoid.
- **PDF rendering.** bayan writes and reads PDF structure and text. Rasterising a page is a
  different problem and belongs with the image/graphics stack.
- **`LZWDecode` and the image codecs** (`DCTDecode`, `JPXDecode`, `CCITTFaxDecode`,
  `JBIG2Decode`). Rejected by name rather than silently passed through, because returning
  still-encoded bytes as "text" is the silent-wrong-answer shape this library refuses.
- **Full YAML 1.2.** The subset is documented, and everything outside it is rejected loudly.
