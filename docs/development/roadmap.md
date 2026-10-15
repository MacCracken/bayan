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

## 1.6.1 — patch: the rest of the cyml scans, refusals, cleanups

- **cyml: the `---` searches hop line to line.** Three delimiter searches still call `_cyml_is_delim`
  at every byte: the single-entry search and each entry's search in `bayan_cyml_parse`, and
  `bayan_cyml_split`. That is the shape 1.6.0 removed from the marker scan. It was left out of 1.6.0
  because an entry's header is short, so this is a small share of a parse. Use 1.6.0's method: the
  previous parser as a scratch oracle, every prefix of random token documents, mutants checked.
- **cyml: `bayan_cyml_parse` returns 0 when an allocation is refused.** The doc, the single-entry
  array, each entry and the multi-entry array are all used unchecked, so the parse faults when memory
  runs out (the module header has said so since 1.5.3; Known gap 9). Prove it with an
  every-allocation-point refusal sweep, as 1.5.13 did for TOML.
- **Flag loops → `loop`.** The five `var go = 1; while (go == 1)` scans (`src/toml.cyr` ×3,
  `src/json.cyr`, `src/cyml.cyr`) become `loop { … break; }`. No behaviour change.
- **`src/u128.cyr`: the comment above `_u128_lshr64` says `>>` sign-extends.** It is a logical shift
  on every backend (measured at 1.5.10: `-16 >> 2` is `0x3ffffffffffffffc`). Known gap 13.
- **A guard against including the vendored `lib/bayan.cyr`.** It is bayan's own fold, and every
  `lib sync --full` puts it back. It defines every symbol `src/` does, from an older release (Known
  gap 4). Add a CI step that fails when anything in `src/`, `tests/` or `scripts/` includes it.
- **The ADRs never written** (Known gap 5): the carve, the `_compat` aliases, the sublib split,
  yaml parsing into json's tree, and 1.5.3's choice to decode in the parser. The last is the
  strongest: its reasoning carries over to yaml (1.8.0).

## 1.6.2 — patch: aarch64 128-by-64 division

- **`bayan_u128_div` / `_mod` / `_divmod` on aarch64 are bit-serial** for a 64-bit divisor (Known
  gap 11). 1.5.10 gave mulmod its own asm and left these: no mulmod path reaches them now.
  aarch64 has no 128/64 divide instruction. Use two-digit Algorithm D over `udiv`, the shape of
  1.5.10's mulmod block, with the same checks (re-assembled from mnemonics, branches read on their
  labels, a correction-bound proof in the comment). `tests/mulmod_speed.cyr`'s method gates the cost.

## 1.7.0 — minor: output that is silently wrong

Each item changes what a public function returns, so each gets its own CHANGELOG entry naming the
defect, and the release's header says what a consumer should re-check.

- **csv: RFC 4180** (Known gap 10). A trailing empty field is dropped (`a,` parses to one field, so
  a round trip loses a column). Records end in LF where the RFC says CRLF. A CR in a field does not
  trigger quoting. Oracle: Python's `csv` module.
- **`bayan_json_build` quotes every value and escapes nothing** (Known gap 14). A number comes back
  as a string, a nested value as a quoted span, and a `"` or `\` inside a value makes invalid JSON.
  `bayan_json_build(bayan_json_parse(doc))` should be valid JSON with the same values.
- **cyml: adjacent `[[entries]]` markers.** `[[entries]]\n[[entries]]\nid=2\n---\nB\n` parses as
  one entry whose header begins with the second marker (since 1.5.1, and pinned at 1.6.0 so that
  changing it is a decision). Decide whether the first marker is an empty entry. If it is, the skip
  after a match has to stop on the marker's own newline. The empty entry's header bounds also need
  checking, because its header would start past its end.

## 1.8.0 — minor: yaml decodes escapes

- **Double-quoted yaml scalars keep their `\` escapes verbatim** (`src/yaml.cyr:20`, `:371`: "no
  \-escape decoding — the toml convention"). That convention ended in 1.5.3, when toml started
  decoding in the parser, the only place that knows which quote produced a string (mneme's filing,
  [archived](issues/archived/2026-08-22-mneme-toml-basic-strings-not-unescaped.md), named yaml too).
  Pick the oracle before writing the code, as toml has `tomllib`. cyml needs nothing here: it returns
  its headers as raw TOML spans and decodes no values itself.

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

- **Public constants as `const`:** `JTAG_*`, `TOML_K_*`, `JS_EV_*` and the public `PDF_*`, about
  50 top-level `var`s. A `const` has no storage, so `&NAME` or an assignment stops compiling.
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
