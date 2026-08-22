# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.5.1] — 2026-08-21

**P-1 security and hardening sweep.** Every module audited under five lenses
(bounds, overflow, termination, byte accounting, silent wrong answers), each
finding handed to a separate reviewer instructed to **refute** it, and each
survivor fixed only after a reproducer measured it. Twenty defects confirmed
and repaired, plus four found by hand while writing the first tests three
modules had ever had.

No API changed. Two behaviours are deliberately stricter and are called out
below, because a caller relying on the old leniency will see a refusal where it
previously got a plausible wrong answer — which is the point.

### The context that made this necessary

Eight of bayan's ten modules were carved byte-identical out of cyrius's stdlib
at 1.0.0. Their tests stayed behind, and `cyrius coverage` reported
`csv 0/3`, `cyml 0/17`, `bigint 0/20` — three modules referenced by no test in
bayan's own suite, on the assumption their coverage still lived upstream. It
did not: bayan has owned that code since the carve, and `lib/csv.cyr` no longer
ships in cyrius at all. **Writing csv's first test found two heap buffer
overflows within the hour.**

The general form, now recorded in `state.md`: a carved module whose tests
stayed behind is not "covered elsewhere", it is uncovered.

### Fixed — memory safety

- **`csv`: two heap buffer overflows (CWE-787).** `bayan_csv_parse_line` gave
  each field a fixed `alloc(1024)` and wrote one byte per input byte with no
  bound — a 4,000-byte field wrote **2,976 bytes past the end**, content and
  length both attacker-controlled. `bayan_csv_write_line` did the same with a
  fixed `alloc(4096)` — **5,912 stray bytes** from a 10 KB row. Both now
  measure before allocating. Mutation-verified: restoring either fixed size
  makes the new regression test report those exact counts.
- **`base64`: a one-byte remote crash.** `bayan_base64_decode("=", 1)` computed
  `out_len = -1`, `alloc(0)` returned 0, and the unconditional terminator wrote
  through address `0xFFFFFFFFFFFFFFFF`. Verified SIGSEGV. Length and alphabet
  are both validated now; non-base64 bytes used to decode as `0xFF` filler.
- **`yaml`: an unchecked allocation.** `bayan_yaml_frontmatter_split_a` wrote
  through the result of `alloc_via` without checking it — an exhausted caller
  arena took SIGSEGV. Every other allocating entry in the module already
  checked.
- **`cyml`: an out-of-bounds read.** `bayan_cyml_doc_entry` was bare pointer
  arithmetic with no bounds check and no null check; a negative index read
  *before* the entry array and returned a garbage pointer the caller then
  dereferenced. Found by the module's first-ever test.

### Fixed — a remote memory-exhaustion DoS

- **`json` allocated the whole remaining document for every string.** The
  decode buffer was sized `len - pos + 1`, where `len` is the document length,
  so heap use was quadratic in input size and nothing is ever freed on a bump
  allocator. Measured: 40 KB of input took **200 MB**; 1 MB took **125 GB of
  heap / 46 GB RSS**. Both parsers shared the helper, so the **streaming**
  parser — whose documented purpose is bounded memory for multi-MB input — was
  the most quadratic path in the module. Now pre-scans for the closing quote
  and sizes from the string's own span: 40 KB of input takes 742 KB, and the
  heap-per-byte ratio is flat instead of growing.

### Fixed — wrong answers

- **`bigint`: `bayan_u256_mul` dropped carries.** The three-term inner sum
  detected overflow with a single comparison, missing the case where
  `lo + carry` wrapped on its own. **220 of 400 random 256-bit products were
  wrong**, and 53 of 100 `mulmod` results under Curve25519's p = 2^255-19.
  Single-limb inputs were all correct, which is exactly why the existing tests
  never saw it. Now verified against 201 vectors from Python's
  arbitrary-precision integers; mutation-verified at 120/201 wrong when the old
  logic is restored.
- **`bigint`: `bayan_u256_mod` reduced by repeated subtraction.** It spun
  **forever** on `p == 0` and needed up to 2^256 iterations for a small p
  (measured: 2.06e7 iterations/second, so `a mod 1` on a 256-bit `a` would not
  finish this century). Replaced with binary long division — 256 steps for any
  input — and `p == 0` now returns `-1`.
- **`json`: the flat parser ignored `\"` escapes, which let a value hide a
  key.** For the valid document `{"note":"hi\"there","admin":"false"}` the
  value ended at the escaped quote and the parser resynchronised mid-value,
  producing `[note]=[hi\]` and `[,]=[false]` — with `admin` gone. A caller
  checking a permission got a silent "not found" reachable through any string
  field.
- **`toml`: an unterminated string swallowed the following lines.** The scan
  ran to the end of the *document* looking for a closing quote, so
  `a = "oops` absorbed the next two lines and silently deleted their keys —
  `admin` and `b` simply absent from a config parse. A basic string may not
  contain a newline, so the newline now terminates it.
- **`json` and `toml` file loaders truncated and reported success.** Fixed
  16 KiB and 256 KiB read buffers, with the cut landing mid-token: a
  52 KB / 2,001-key JSON object parsed to **630 pairs**, and a 300 KB /
  15,000-key TOML file to **13,107** with `is_err_result() == 0`. Both now read
  through a growing builder — no cap remains.
- **`cyml`: `bayan_cyml_expand_value` discarded everything around the
  reference.** `"v${file:VERSION}-beta"` returned `"1.5.0"`, dropping 16 of 21
  bytes; `"https://${env:HOST}/api"` returned the host alone. It now
  substitutes in place and handles multiple references. Expanded text is
  deliberately not re-scanned, so a file containing `${...}` cannot drive an
  expansion loop.
- **`cyml`: a leading blank line hid the first entry.** `_cyml_is_entries`
  tested only for a marker at byte 0 when `pos == 0` and returned, so the
  marker at byte 1 was unreachable — one entry silently folded into the file
  header.
- **`cyml`: the entry scan capped at 256 and truncated silently.** 300
  `[[entries]]` blocks parsed as 256, with 44 gone and no diagnostic. The scan
  is now two-pass (count, allocate exactly, fill), which also retires the fixed
  stack array whose mis-sizing was an out-of-bounds stack write in
  CHANGELOG [6.0.79].
- **`bigint`: `bayan_u256_from_hex` accepted anything.** It truncated
  over-length input to its first 64 characters and treated every non-hex byte
  as a zero digit, so `"hello world"` parsed to a number and `"12-34"` to
  `0x12034`. Both now refuse.
- **`json`: malformed numbers parsed.** A lone `-` became the integer 0
  (`[-,-]` serialised back as `[0,0]`), as did `1.` and `1e`. And `_jp_atoi`
  wrapped silently, so `9223372036854775808` came back as
  `-9223372036854775808` — a value whose **sign** differs from the document's.
  Digits are now required in every position and the i64 range is enforced.
- **`json`: a JSON-pointer index wrapped mod 2^64.** Against a 3-element array,
  `/1` followed by 64 zeros selected element 0. An out-of-range pointer now
  resolves to nothing.
- **`json`: a scalar constructor's OOM was silent.** The parse returned 0 with
  `err_msg` empty, indistinguishable from a parse failure — measured on a real
  arena, 9 of 31 failing capacities reported no error at all.

### Fixed — portability

- **`cyml` used raw x86_64 syscall numbers** (`syscall(2, …)` open,
  `syscall(0, …)` read, `syscall(3, …)` close) for `${file:}` and `${env:}`
  expansion. On another target those numbers are different calls: on agnos the
  "open" returned the process's own pid, the `fd < 0` guard did not fire
  because a pid is positive, and the following "read" **terminated the
  process** (exit status 102 = pid mod 256). Now uses `lib/io.cyr`'s portable
  wrappers, which bayan already depends on.

### Changed — deliberately stricter

Two inputs that used to produce a value now produce a refusal. Both were
divergences rather than mere leniency:

- **`yaml` rejects duplicate mapping keys.** `obj_set` appends, so
  `role: admin` / `role: guest` built a two-entry object where
  `bayan_json_v_obj_get` returned the **first** while the serialiser emitted
  `{"role":"admin","role":"guest"}` and every downstream JSON reader took the
  **last**. Two components reading one document disagreed about a role. YAML
  1.2 makes duplicates an error.
- **`yaml` no longer types an out-of-range integer as an int.**
  `uid: 18446744073709551616` used to become the integer `0`. It now falls
  through to a string, which is what an unrepresentable scalar is. (This one
  came free with the json number fix — yaml delegates to json's scanner.)

### Added — tests for three modules that had none

`csv`, `bigint` and `cyml` had zero references in bayan's own suite. They now
have full groups, alongside a regression guard for every defect above. The
suite is **525 asserts + 19 in `pdf_flate.tcyr`**, up from 452.

### Also

- `scripts/check-widths.py` — verifies the standard-14 font metric tables using
  only the Python stdlib, so the CI gate no longer depends on groff being
  installed. `scripts/gen-widths.py` now discovers groff's font directory
  instead of hardcoding a version path, and fails with an actionable message
  rather than a traceback. This fixed a CI failure introduced in 1.5.0.
- `bayan_toml_get`'s doc comment claimed the key could be a cstring **or** a
  `Str`; it compares with `str_eq_cstr`, so a `Str` yields a silent "not found"
  — the 1.4.1 trap. Comment corrected, and the asymmetry with
  `bayan_json_get` (which takes a `Str`) recorded as a known gap, since
  reconciling them is a breaking change rather than a patch.

## [1.5.0] — 2026-08-21

**PDF read/write — `bayan_pdf_*`.** The roadmap's P2 item lands: a PDF writer
and a PDF reader with text extraction, as `src/pdf.cyr` (9,348 lines, 152
public functions). Its one known consumer, **mneme**, has shipped a hand-rolled
writer since its port; that hand-roll is superseded here, and the defects found
while reading it are what this module is shaped around.

Also in this release: the Cyrius pin moves `6.5.28` → `6.5.33`.

### Added — the writer

- `bayan_pdf_new()` → document, `bayan_pdf_add_page`, the standard-14 fonts,
  text and graphics operators, `/Info` metadata, `bayan_pdf_to_bytes`, and
  `bayan_pdf_write_file`.
- **Every byte offset in the cross-reference table is MEASURED, never
  predicted.** The offset for an object is read off the output builder
  immediately before that object is appended, and `_pdfw_selfcheck` then
  re-reads every recorded offset and confirms it lands on `<n> 0 obj` before
  `to_bytes` returns. mneme predicts offsets from `var offset = 9;` — the
  length of `"%PDF-1.4\n"` — which is correct only until a second header line
  exists. bayan emits the conventional binary-comment line, so the predicted
  constant would have been wrong for every object in the file.
- **Object numbers come from a counter, not closed-form arithmetic.** mneme's
  `4+2p` / `5+2p` scheme is correct today and must be re-derived the moment
  anything — `/Info`, a second font, an `/ID` — is added.
- **Real AFM font metrics.** The standard-14 width tables are derived from
  Adobe's original AFM data (via groff's `afmtodit`-generated metrics) by
  `scripts/gen-widths.py`, which self-verifies against 22 documented spot
  widths, a whole-family monospace check, and a decode round-trip.
- **`/Encoding /WinAnsiEncoding` is declared, and text is transcoded to match.**
  mneme declares no encoding, so viewers fall back to StandardEncoding, where
  only 54 of the 128 high codes exist: `Résumé` renders `RÃ©sumÃ©` and an
  em-dash disappears entirely. Declaring the encoding without transcoding would
  merely change the flavour of mojibake, so bayan does both.
- **A newline inside show-text is rejected**, not silently deleted. A newline
  means "break the run"; accepting and dropping it is a silent content change.
- **`bayan_pdf_write_file` propagates the write failure.** mneme ignores
  `file_write_all`'s return and reports success on a full disk.

### Added — metric text measurement

- `bayan_pdf_text_width` and `bayan_pdf_wrap` lay text out by **measured
  advance width**. mneme wraps at 80 characters, but in a proportional face 80
  characters spans a **4.26× range** — 80 `l` is 195 pt (43% of a 451 pt
  column) while 80 `W` is 831 pt (184%, running 308 pt off a 595 pt page).
  Verified on the release fixture: the widest wrapped line measures 450.2 pt in
  a 451 pt column, and no line overflows.
- WinAnsi transcoding both ways (`bayan_pdf_winansi`, `bayan_pdf_from_winansi`),
  with a strict mode that refuses an unrepresentable codepoint and a substitute
  mode that emits `?`.

### Added — the reader

- `bayan_pdf_parse*` → an object graph, plus `bayan_pdf_extract_text`.
- Classic cross-reference **tables** and PDF-1.5 cross-reference **streams**,
  `/Prev` chains, objects stored inside **object streams**, and PNG **and**
  TIFF predictors.
- Filters: `FlateDecode` (through the hook below), `ASCIIHexDecode`,
  `ASCII85Decode`, `RunLengthDecode`. An unrecognised filter is an error, not a
  pass-through — returning still-encoded bytes as "text" is a silent wrong
  answer.
- **Inherited page attributes** (`/Resources`, `/MediaBox`, `/CropBox`,
  `/Rotate`) are honoured. A reader that consults only the `/Page` dict reports
  a missing `/MediaBox` on a large fraction of real files.
- **Text decoding follows the font**, not a fixed encoding: `/ToUnicode` CMaps
  (`beginbfchar`, `beginbfrange` in both forms, surrogate pairs, ligature
  destinations), `/Type0` composite fonts consuming two-byte codes,
  `/Encoding /Differences` by Adobe glyph name, and the WinAnsi / MacRoman /
  Standard base encodings. Parsed maps are cached per font.

  This is what makes the reader work on modern files. `glm/manual.pdf` uses
  `/Type0` `/Identity-H`; decoding it a byte at a time yields
  `* / 0        0 D Q X D O` where the page reads `GLM 0.9.9 Manual`.
- **`/Encrypt` is detected and rejected** before any string or stream is
  touched. Encryption is out of scope for 1.5.0, and a half-handled encrypted
  file presents ciphertext as text.
- Bounded on five independent axes — object nesting, indirect-reference chains,
  xref `/Prev` sections, page-tree depth, and total inflated bytes — each with
  its own counter and its own message, so a refusal names the bound it hit.

### Added — compression, without a sankoch dependency

`FlateDecode` / `FlateEncode` is reached through consumer-installed function
pointers, `bayan_pdf_set_inflate(&zlib_decompress)` and
`bayan_pdf_set_deflate(&zlib_compress)`. bayan folds INTO cyrius's stdlib, so a
hard `include "lib/sankoch.cyr"` would create a module-ordering hazard in that
fold for a filter many consumers never touch. With no hook installed the writer
emits valid uncompressed output and the reader reports a specific error naming
the missing hook — both paths are tested, the hook-absent one in
`tests/bayan.tcyr` and the hook-present one in `tests/pdf_flate.tcyr`.

`[deps].stdlib` is unchanged and `[lib.pdf]` is a **single-module closure** —
pdf carries its own object graph and its own decimal number emitter, so neither
`json.cyr` nor `dtoa.cyr` rides along.

### Design notes worth keeping

- **No floating point anywhere in the module.** Geometry is integer
  milli-points (1 pt = 1000 mpt) and a PDF real is captured losslessly as
  `(scaled, places)`, so parse and emit are exact inverses and `0.50`
  round-trips as `0.50` rather than normalising to `0.5`. `bayan_f64_to_json`
  is unusable here: it emits exponent notation and the token `null`, both
  invalid PDF number syntax, and both of which compile clean.
- **A separate `bayan_pdf_obj_*` tree rather than reusing `bayan_json_v_*`.**
  PDF has name, indirect-reference, and stream types with no JSON analogue, and
  `JTAG_STR` is documented as decoded UTF-8 while PDF strings are raw bytes.
- **Ten subsystem helper prefixes, never a bare `_pdf_`.** mneme defines 14
  bare `_pdf_*` helpers and will have both files in scope during its migration;
  a duplicate function name in cyrius is only a *warning*, with
  last-definition-wins that rebinds even textually-earlier call sites.

### Added — the acceptance oracle

`scripts/pdfcheck.py` is a strict, stdlib-only PDF validator, and it is the
gate CI runs the writer's output through. It is deliberately stricter than
poppler and mupdf, which reconstruct a broken cross-reference by scanning for
`N 0 obj` and thereby hide exactly the byte-accounting bugs it exists to catch:
every offset is checked against the byte it claims to point at. It was itself
mutation-tested — a corrupted xref offset, a `/Length` off by one, and a stale
`/Size` must each be caught — and that exercise found two bugs in the oracle
before it was trusted: a `\s*endstream` match that let an off-by-one `/Length`
slide through, and a tuple/int comparison that crashed on any PDF-1.5 file.

`scripts/gen-pdf-fixtures.py` generates the checked-in fixtures — the `ref-*`
ones must parse and the `bad-*` ones must be refused, and CI asserts BOTH
directions. A validator that quietly goes lenient passes every happy-path check
ever written; the polarity assertion is the only step that would notice.

**Font metrics are verified without needing groff.** `scripts/gen-widths.py`
*derives* the tables from groff's afmtodit-generated Adobe metrics, so it needs
groff installed — the wrong dependency for a gate, and it broke CI on the first
run for exactly that reason: a hardcoded `/usr/share/groff/<version>/` path
that existed only on the authoring machine. Two changes:

- the generator now **discovers** groff's font directory across the usual
  roots instead of pinning a version, and fails with an actionable message
  rather than a `FileNotFoundError` traceback;
- `scripts/check-widths.py` is new and is what CI actually gates on. It decodes
  the tables straight out of `src/pdf.cyr` and checks them against documented
  Adobe Core-14 widths and Python's own `cp1252` codec — no groff, no network,
  stdlib only. The byte-for-byte regeneration diff still runs, but only where
  groff is present, and is skipped rather than failed when it is not: groff's
  absence says nothing about whether the tables are right.

The checker is mutation-tested — corrupting a width, filling one of the five
undefined CP1252 codes, truncating a table, and breaking the WinAnsi block are
each caught. It also found its own first bug on contact with real data: it
applied the undefined-codes rule to Symbol and ZapfDingbats, which are symbolic
faces carrying their own built-in encodings where those codes are real glyphs.

### Fixed before release — an adversarial review of the new module

`src/pdf.cyr` was reviewed under five lenses (bounds, overflow, termination,
byte accounting, silent wrong answers) with every finding handed to a separate
agent instructed to **refute** it. Eighteen candidate defects; ten survived
refutation with a reproducer, and all ten are fixed here. Recording them
because "the parser passed its tests" and "the parser is safe on hostile input"
are different claims, and only the first was true before this pass.

- **A near-i64-max `/Length` segfaulted the reader.** The reach check was
  `start + n > len`. The number lexer admits values up to 9223372036854775799
  (its range guard runs *before* the multiply-accumulate), so `start + n`
  wrapped to a large **negative** i64 — neither `n < 0` nor `> len` — the guard
  passed, and `load8(buf + e)` then read about 9.2 exabytes below the buffer.
  Reproduced as a SIGSEGV from a 428-byte file, with the wrapped value visible
  in the backtrace. Now compared by subtraction (`n > len - start`), which
  cannot overflow because `start <= len` always holds.
  **Mutation-verified**: restoring the additive form makes the new
  `bad-huge-length.pdf` fixture crash the process again.
- **The object-stream memo was keyed on the document pointer alone.**
  `alloc_reset()` rewinds the bump allocator and a `PdfDoc` is the first thing a
  parse allocates, so document *addresses* are recycled and a second document
  could be handed a freed record whose vec and Str words now held unrelated
  bytes. Documents now carry a monotonic generation stamp that the key includes.
  The decompression budget already defended against exactly this recycling; the
  memo had been given the same rationale in a comment but not the same guard.
- **`/XRefStm` chains bypassed `_PDF_MAX_XREF`.** The hybrid-reference path
  recurses `_pdfx_read_table` → `_pdfx_read_section` → `_pdfx_read_table`
  without passing through the `/Prev` loop that holds the counter, so one of
  the two chains was bounded and the other exhausted the native stack. Now
  bounded on the shared visited-set length, which covers both chains.
- **Indirect `/Length` chains recursed without bound.** Every
  `_pdfp_resolve_d` call site passes a literal depth of 0 and its visited set
  is per-call, so neither survived the trip back through `_pdfp_stream_a`;
  `k 0 obj<</Length k+1 0 R>>` repeated N times recursed N deep. Bounded by a
  per-document re-entry counter.
- **The page-tree walk was exponential.** `_PDF_MAX_TREE` caps *depth* and the
  cycle set is *path*-scoped — correct for a node that reaches itself, useless
  for a node reached down many distinct paths. Thirty `/Pages` nodes each
  listing the same kid twice is 2^30 visits at depth 30: inside every existing
  bound and indistinguishable from a hang. Now carries a total-work budget.
- **The cross-reference table grew by exact request.** `_pdfx_alloc_table` is
  called once per subsection and nothing is freed, so a table of N one-entry
  subsections allocated O(N²) bytes — tens of gigabytes from a 1 MB file.
  Growth is now geometric, with the allocated capacity tracked separately from
  the logical `/Size` so a resolve still cannot reach past what the trailer
  declares.
- **`/ToUnicode` `bfrange` had no cumulative work budget.** Each entry may span
  65,536 codes and the outer loop admitted 65,536 entries, so a ~2 KB
  compressed CMap could drive ~4e9 map writes.
- **The writer's depth cap never fired through a stream.** `_pdfw_obj` forwarded
  `depth` on every composite arm except `PTAG_STREAM`, which hard-coded it, so
  a stream whose own dictionary referenced the stream recursed until the stack
  died. Now forwarded like every other arm.
- **`bayan_pdf_raw_op`'s comment described behaviour the code did not have** —
  it claimed a `q` inside a literal string was not matched, when delimiters
  make `(a q b)` tokenise as `a`, `q`, `b` and be refused. The refusal is the
  safe direction and is kept deliberately; the comment now says so, rather than
  a string-aware lexer being added inside a safety check.

Two reviewer findings were **refuted** and deliberately not changed: the writer
does not leak partial output on a failed content operator (the failure fires
before anything is appended), and the shared empty `Str` is not a dangling
pointer.

### Changed (toolchain)

- **Cyrius pin `6.5.28` → `6.5.33`**, with `cyrius lib sync --full`. `lib/`
  matches the **release tarball** exactly — 0 of 108 files differ — verified by
  comparing the trees rather than trusting the sync's exit code, and against
  the released tarball rather than `~/.cyrius`, which on a machine that also
  develops cyrius can carry unreleased in-flight edits at the same version
  number. (This time the local snapshot and the release agreed.)

## [1.4.2] — 2026-08-19

Toolchain + CI release. No behavioural change: the compiled smoke binary is
**byte-identical** (sha256 `9c5e4c3d…`) before and after every source edit
below. What did change is that the project now *checks* considerably more of
itself, and two of the new checks immediately found something.

### Changed (toolchain)

- **Cyrius pin `6.5.16` → `6.5.28`**, with `cyrius lib sync --full` run against
  it. `lib/` matches the pinned snapshot **exactly — 0 of 108 files differ**,
  confirmed by comparing the trees rather than trusting the sync's exit code
  (see the 1.4.0 note on why: that time `--full` exited 0 and still left five
  files stale). Build and test now emit neither the shadow-lib nor the
  pin-drift warning.
- **`lib/` grew 99 → 108 files.** The 6.5.28 snapshot adds `unicode/` (7 files —
  `_decode` / `categories` / `casefold` / `normalize` plus their generated data
  tables), `async_macos.cyr`, and `thread_macos.cyr`; 48 existing modules were
  refreshed, six of which bayan had been shadowing at older versions
  (`sakshi` 2.4.7, `sigil` 3.12.2, `sandhi` 1.9.8, `vani` 1.1.2,
  `sankoch` 2.7.6, and bayan's own fold at 1.3.0).
- **The `6.5.4` → `6.5.16` step was never recorded.** 1.4.0 shipped on `6.5.4`;
  commit `97a3476` ("lang bump", 2026-08-10) moved the pin to `6.5.16` with no
  CHANGELOG entry and no `state.md` refresh. Noting it here so the history is
  contiguous: the span this release actually crosses is `6.5.4` → `6.5.28`.

### Fixed

- **`src/toml.cyr` no longer builds with warnings.** `_toml_parse_str` and
  `_toml_parse_multiline_q` both return a `Str` (`str_new` / `str_from`) but
  were declared `: i64`, so every assignment into the `Str`-typed `value` drew
  an `assigning non-pointer to typed pointer` warning — three of them, at 257 /
  261 / 266, present since the multiline parser was parameterized. Annotating
  the two helpers (and the `_toml_parse_multiline` back-compat wrapper) `: Str`
  clears all three. **Diagnostic only, and proven so**: the compiled binary is
  byte-for-byte identical to the pre-annotation build. Same shape as the 1.4.1
  `cstring` annotation, and both helpers are file-private with call sites only
  inside `toml.cyr`.
- **Lint is clean across all 12 `src/` files** (was 1 warning + 1 untracked
  deferral). The >120-char `cyml_split` forwarding shim in `_compat.cyr` is
  wrapped; the `\uXXXX` in `json.cyr`'s doc comment — read by the deferral
  scanner as an `XXX` marker — carries `#skip-lint: \u-escape notation, not a
  deferral`, matching how `lib/sigil.cyr` handles the identical false positive.
- **`tests/bayan.tcyr` is canonically formatted.** 21 continuation lines sat at
  column 0; `cyrius fmt` indents them to 2. Whitespace only — still 292 asserts,
  still green. It had gone unnoticed because `cyrius audit` scopes fmt to `src`.

### Added — CI now confirms the whole project

`.github/workflows/ci.yml` went from 4 steps (install / deps / build / test) to
a full gate. The new checks, and why each one is a gate rather than a printout:

| Gate | Notes |
|---|---|
| Toolchain pin resolves with no drift | every gate below is worthless if it measured the wrong compiler |
| Version consistent across `VERSION` / manifest / CHANGELOG / all 9 dist headers | |
| `lib/` matches the pinned snapshot exactly | the tree diff, per the standing 1.4.0 rule |
| Format — `src/` **and** `tests/` | `cyrius audit` only covers `src/`; the drift above was in `tests/` |
| Lint — zero warnings, zero untracked deferrals | `cyrius lint` always exits 0, so the gate reads its report, not `$?` |
| Include-dependency audit (`cyrius vet`) | fails on any untrusted / missing dep |
| Build — **zero compiler warnings** | `cyrius build` only *warns* on bad pointer typing, lib/ shadowing and pin drift; `--strict` does not cover them, so the warning text is the gate |
| Smoke exits 42 | |
| Test | |
| Fuzz · bench harness · `cyrius coverage --min 30` | a floor that ratchets up, never down |
| **Distribution ×3** | see below |

`release.yml` gains a CHANGELOG-entry check alongside the existing tag/VERSION
check, and both workflows lost the `|| true` that let a half-finished toolchain
install pass as success.

**Both workflows now install via the upstream installer** rather than
untarring a release by hand:

```sh
curl -sSf .../cyrius/main/scripts/install.sh | CYRIUS_VERSION="$pin" sh
```

The hand-rolled step (inherited from the original scaffold, and still present
in ganita) laid the toolchain down at `~/.cyrius/{bin,lib}` as real
directories. 6.5.28's `cyrius deps` requires the snapshot at
`~/.cyrius/versions/<pin>/lib` specifically and errors with *"pins version
6.5.28 but it is not installed"* — CI's first red. The installer creates
`versions/<pin>/{bin,lib}` and symlinks `~/.cyrius/{bin,lib}` at them, which is
what every path-sensitive command expects; the `lib/`-vs-snapshot gate compares
against `versions/<pin>/lib` for the same reason. The pipe carries
`set -eo pipefail` — without it a failed download pipes empty input to `sh`,
`sh` exits 0, and the install silently no-ops.


**The three distribution gates**, since `dist/` is what bayan actually ships:

1. `cyrius distlib --all --check` — the bundles are regenerable from `src/`.
2. Regenerating leaves no tree diff — the *committed* bundles are what a fresh
   regeneration produces, sidecars included.
3. `scripts/consumer-check.sh` (new) — every bundle compiles for a downstream
   repo that supplies **only** the leaves its `.deps` sidecar declares.

Gate 3 has to build with `cyrius build --no-deps`. Without it, `cyrius build`
auto-prepends everything in bayan's own `[deps].stdlib`, so a consumer missing
a declared leaf still compiles and the check passes vacuously — verified by
deleting leaves from a sidecar one at a time and watching all eight still
report clean.

### Found by the new gates

- **Two sublib sidecars under-declare their dependencies.** With `--no-deps` in
  place, `bayan-toml` fails on `memcpy` / `memeq` / `fmt_int_buf` / `fmt_int`
  and `bayan-cyml` on `fmt_int`. `cyrius distlib` generates each sidecar from
  the leaves *bayan's* code touches and does not close over the stdlib's own —
  `lib/str.cyr` calls memcpy/memeq/fmt_int with no include lines at all,
  `lib/result.cyr` calls fmt_int, `lib/io.cyr` calls memcpy. Verified minimal
  fix: `bayan-toml` needs `+string +fmt`, `bayan-cyml` needs `+fmt`. The
  compiler reports these as *warnings*, so a consumer following the sidecar
  gets a green build and a broken binary. Filed as
  [2026-08-19](docs/development/issues/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md)
  — the sidecars are generated, so bayan cannot fix it in-repo. The two are
  carried in the script's `EXPECTED_FAIL` list, which **fails if either starts
  passing**, so the exemption cannot outlive the bug.
- **`dist/` must be generated by the PINNED toolchain, and briefly wasn't.**
  The first cut of this release regenerated `dist/` with a local `cyrius` that
  self-reports `6.5.28` but is actually a **`.29`-in-flight build** — it carries
  the two 2026-08-18 distlib profile-sidecar fixes
  (`distlib-named-profile-sidecar-from-sit`,
  `distlib-profile-sidecar-empty-under-auto-prepend`). Those emit `syscalls`
  into the `bayan-cyml` / `bayan-json` / `bayan-toml` / `bayan-yaml` sidecars
  and write an empty `dist/bayan-u128.deps`. **Released 6.5.28 emits neither**,
  so `distlib --all --check` on CI reported four bundles STALE — sidecar bytes
  count toward staleness, not just the `.cyr`. Reproduced locally by installing
  the release tarball into an isolated `CYRIUS_HOME`, which returned CI's output
  line for line, down to the absent `u128` sidecar. `dist/` is regenerated with
  released 6.5.28 and `dist/bayan-u128.deps` removed; both come back on the
  re-pin to `.29`. **Verify against the release tarball, not `~/.cyrius`, whenever
  the toolchain repo is mid-flight.**

### Verified on 6.5.28

| Gate | Result |
|---|---|
| `cyrius build src/main.cyr` | OK, **0 warnings**; smoke exits 42 |
| `cyrius test` / `cyrius tests` | **292 passed, 0 failed** (+ 1/1 `[build].test`) |
| `cyrius fmt --check` (src + tests) | clean |
| `cyrius lint` (12 files) | 0 warnings, 0 untracked deferrals |
| `cyrius vet src/main.cyr` | 20 deps, 0 untrusted, 0 missing |
| `cyrius distlib --all --check` | 9 bundles current (deterministic over 6 runs) |
| `scripts/consumer-check.sh` | 7/9 clean, 2 known-under-declared |
| `cyrius fuzz` · `cyrius bench` | 1/1 · 1/1 |
| `cyrius coverage` | 102/335 fns (30%) reference coverage |

### Known, not fixed here

Surfaced by the state review and recorded in
[`state.md`](docs/development/state.md) — each is its own change:

- `tests/bayan.fcyr` and `tests/bayan.bcyr` are still `cyrius init` scaffolds.
  The fuzz harness feeds a 4-byte literal into a body that returns immediately;
  the bench measures a no-op. Both report PASS — a false green on two v1.0
  criteria, and the CI gates that run them are correspondingly vacuous.
- `bigint` (0/20), `cyml` (0/17) and `csv` (0/3) are referenced by no test in
  bayan's own suite; their coverage still lives upstream in cyrius.
- `lib/bayan.cyr` is bayan's own fold vendored back into bayan's own `lib/` by
  `lib sync --full`. Inert (nothing includes it) but it defines the same symbols
  as `src/` — the hazard the ten dead pre-carve modules were removed for at
  1.4.0, and not durably fixable in-repo since `--full` re-adds it.
- `README.md` still says "Status **1.0.0** — Seven modules"; `docs/adr/` holds
  no ADRs; roadmap M1/M2 are unfilled template stubs; `CLAUDE.md` Project
  Identity and Goal are still `TODO`.

## [1.4.1] — 2026-08-05

### Fixed — `json_v_obj_get` takes a C-string while `json_v_obj_set` stores a `Str`

The object API is asymmetric and always has been: `bayan_json_v_obj_set` writes `key`
straight into the pair as a `Str`, while `bayan_json_v_obj_get` does `strlen(key)`.
Cyrius is i64-everywhere, so both spellings compile and the symmetric-looking pair is
memory-unsafe.

The failure is worse than a crash. Passing a `Str` to the getter makes `strlen` walk the
16-byte header and terminate a few bytes in on the data pointer's zero high bytes, so it
yields a junk length, the compare misses, and the lookup returns 0 — **"not found", a
silent wrong answer.** The SIGSEGV reporters saw comes later and elsewhere, from
`bayan_json_v_str(0)` → `str_len(0)`.

Three changes, none of which touch a call site:

- `bayan_json_v_obj_get(v, key: cstring)` — the annotation arms cyrius's existing
  Str→cstring diagnostic, which was inert only because the parameter was untyped. It
  fires at every call site passing a `Str`-typed local, at any argument position, and is
  **diagnostic only**: the compiled output is byte-identical.
- `json_v_obj_get` in `_compat.cyr` gets the same annotation, so the ~40 consumers using
  the short spelling are covered too.
- `bayan_json_v_obj_get_by_str(v, key: Str)` — the symmetric spelling, additive.
  ⚠ Deliberately NOT `..._obj_get_str`: a trailing `_str` is a reserved cyrius overload
  slot, and claiming it would silently reroute `obj_get` calls with a literal key.
- `obj_set`'s doc comment now states that the key is stored as a `Str` — the getter's
  side already said "C-string key" and had done since 2026-06-10; the setter's half was
  the one actually missing.

**Not done, deliberately:** renaming the getter to `_cstr` and giving the bare name a
`: Str`. ~115 call sites across ~16 repos pass a non-literal cstr and would break
silently, and each break is worse than the current defect (`str_len` on a raw cstr is
arbitrary garbage). That is a cross-repo migration, not a patch.

## [1.4.0] — 2026-07-31

### Added

- **The allocator-threaded (`_a`) JSON value surface is complete.** Six new
  entry points close the three gaps that made an arena cover only part of a
  request:

  | New | Signature | Was reachable through an arena before? |
  |---|---|---|
  | `bayan_json_v_obj_set_a` | `(a, obj, key, val) → 0 / -1` | no — pair cells went to the global bump |
  | `bayan_json_v_build_a` | `(a, v) → Str / 0` | no |
  | `bayan_json_v_build_pretty_a` | `(a, v, indent) → Str / 0` | no |
  | `bayan_json_v_parse_ctx_a` | `(a, ps, buf, len) → json_v* / 0` | no |
  | `bayan_json_v_parse_buf_a` | `(a, buf, len) → json_v* / 0` | no |
  | `bayan_json_v_parse_a` | `(a, src: Str) → json_v* / 0` | no |

  The eight value **constructors** have had `_a` forms since v5.8.36. What was
  missing was everything around them: you could allocate each cell of a tree
  through an arena and still leak the pair cells, the parse, and the serialized
  output onto the no-free global bump. That measures as "the arena works" right
  up until someone checks `alloc_used()`.

  Pinned by a test that fails when the threading is removed — verified by
  mutation, not assumed. Reverting a single `alloc_via(a, …)` to `alloc(…)` in
  the string parser turns the zero-growth assertion into `got 35200, expected 0`.

  | 200 × parse → obj_set → build | global bump growth |
  |---|---|
  | non-`_a` path | **> 100 KB** |
  | `_a` path through an arena | **0 bytes** |

### Fixed

- **The string parser never checked its allocation.** `_jp_parse_string` called
  `alloc(cap + 4)` and wrote through the result unconditionally. On the global
  bump that is near-unreachable (`alloc` returns 0 only for `size <= 0` or
  `> ALLOC_MAX`, and a failed chunk mmap exits inside `alloc_init`), so it never
  bit. Through an arena it is ordinary — a small arena runs dry — and the
  unchecked write would have gone to address 0. `_jp_parse_string_a` checks, and
  reports it as a normal `"out of memory in string"` parse error. `_jp_parse_array_a`
  and `_jp_parse_object_a` do the same for their container constructors.

### Changed

- **`_jb_walk`, `_jb_append_string` and `_jb_emit_indent` now have one body, not
  two.** Each is implemented as its `_a` form and the original name is a wrapper.
  The wrappers preserve the **abort**-on-OOM contract of the non-`_a`
  `str_builder` verbs they used to call directly, because turning an abort into a
  silently truncated JSON string would be a worse failure than the crash it
  replaced. The `_a` forms return `-1` instead, which is the contract an arena
  caller needs — the same split `bayan_json_v_arr_push_a` already used.
- **`_jb_emit_indent_a` emits its newline and spaces via `str_builder_add_cstr_a`**
  rather than `str_builder_add_byte`, which has no `_a` form. Both literals are
  one byte, so pretty output is byte-identical; this only moves the growth onto
  `a` and makes the failure reportable. No cyrius-side change was needed.

### Changed (toolchain)

- **Cyrius pin `6.4.68` → `6.5.4`**, with `cyrius lib sync --full` run against it.
  `lib/` now matches the pinned snapshot exactly — 0 of 99 files differ, and the
  build no longer emits a drift or shadow warning.

  `lib sync --full` alone did not achieve that: it copied 99 files and left five
  behind (`niyama` 1.0.5, `pam`, `shadow`, `vani` 1.1.1, `yantra` 1.0.0), all dated
  from the 2026-07-16 sync and none in bayan's `[deps] stdlib` list. They were
  refreshed from the snapshot directly. **A green `lib sync --full` is not proof
  that `lib/` matches the pin — compare the trees.**

### Removed

- **Ten dead pre-carve modules deleted from `lib/`** (109 → 99): `json`, `base64`,
  `bigint`, `csv`, `cyml`, `toml`, `u128`, `matrix`, `linalg`, `agnosys`. The first
  seven are content that was carved *out* of the cyrius stdlib *into bayan* at 1.0.0
  / cyrius 6.1.25 — so bayan was vendoring a stale copy of its own API, defining the
  same symbols as `src/`. Nothing included them, but a single `include` would have
  silently shadowed the real implementations under last-definition-wins. `matrix` and
  `linalg` moved to ganita at 6.1.26; `agnosys` is unrelated to this package. None was
  referenced by `src/`, `tests/`, or `cyrius.cyml`.
- The six `# Usage: include "lib/<mod>.cyr"` header lines that still advertised those
  removed paths now name `lib/bayan.cyr` (full bundle) or `lib/bayan-<profile>.cyr`
  (sublib).

### Notes

- **The parser state layout is unchanged at 48 bytes.** Putting the allocator in
  `ps` would have been tidier — every `_jp_*` already takes `ps` — but callers
  are documented to declare their own `var ps[48]`, so widening the struct would
  have silently overflowed their buffers. The allocator is an explicit first
  parameter instead, which is also what keeps the parse reentrant: a file-scope
  "current allocator" global would have undone the v1.0.3 thread-safety work.
- **`_a` is a naming convention, not a Cyrius dispatch suffix.** Unlike `_str`
  and `_ptr` (which the compiler routes to automatically — see the `1.3.0`
  `_str` → `_buf` entry), `_a` carries no overload behaviour, so these names
  cannot collide with the dispatch rules.
- The **serializer recursion is still uncapped**, matching every prior release.
  Both *parsers* cap at `_JP_MAX_DEPTH` (128); the serializer only ever walks a
  tree the caller built, so it is not an untrusted-input path. Do not build
  unbounded-depth values from user data.

## [1.3.0] — 2026-07-28

### Breaking

- **The cstr+len parse entries are renamed `_str` → `_buf`.** The old names were
  actively breaking their own Str-taking siblings (see Fixed below), so they
  could not be kept as aliases — the name *is* the defect.

  | Removed | Replacement | Signature |
  |---|---|---|
  | `bayan_json_v_parse_str` | `bayan_json_v_parse_buf` | `(buf, len)` |
  | `bayan_yaml_parse_str` | `bayan_yaml_parse_buf` | `(buf, len)` |
  | `json_v_parse_str` (alias) | `json_v_parse_buf` (alias) | `(buf, len)` |

  Migration is mechanical: `s/_parse_str(/_parse_buf(/`. Stale calls do **not**
  fail silently — the removed name is an undefined function, so the build
  refuses to emit a binary. Callers already passing a `Str` should prefer the
  bare `bayan_json_v_parse(src)` / `bayan_yaml_parse(src)`, which now work.

  `bayan_json_stream_parse_str`, `bayan_json_v_parse_ctx_str` and
  `bayan_yaml_parse_ctx_str` are **unchanged** — those genuinely take a `Str`
  first argument, which is what the `_str` suffix is supposed to mean.

### Fixed

- **`bayan_json_v_parse(src)`, `bayan_yaml_parse(src)` and the `json_v_parse`
  alias returned 0 for every input, including valid documents.** Cyrius routes a
  call `X(a, …)` to `X_str` whenever `a` is `Str`-typed at the call site and an
  `X_str` exists — the same overload dispatch that routes `&IDENT` to `_ptr`.
  Because the cstr+len forms were named `bayan_json_v_parse_str` /
  `bayan_yaml_parse_str`, every `bayan_json_v_parse(someStr)` in the ecosystem
  was rewritten by the compiler into a **1-argument call to a 2-argument
  function**: `len` bound garbage and the parse failed. The only outward sign was
  a `'bayan_json_v_parse_str' expects 2 arguments, got 1` warning, easily lost in
  build output. Renaming the cstr+len forms to `_buf` vacates the `X_str` slot
  and the dispatch has nothing to hijack.

  In Cyrius `X_str` means "the `Str`-taking variant of `X`", so a cstr+len form
  may never occupy that name. Both renamed functions now carry a comment saying
  so, to stop this recurring.

  Discovered while porting agnosai's `core/message.rs`, where
  `bayan_json_v_parse` silently failed to round-trip a message.

### Added

- **Regression coverage for the bare `Str` entries** (`tests/bayan.tcyr`, +11
  assertions, 263 → 274). `bayan_json_v_parse`, `bayan_yaml_parse` and
  `json_v_parse` had **no test calling them at all** — the suite only ever
  exercised the cstr+len forms, which is why a total failure of the public Str
  API went unnoticed. The new group asserts each returns a real tree, that the
  `Str` and `_buf` entries produce identical output, and that a null source is
  still rejected cleanly.

## [1.2.1] — 2026-07-20

### Changed

- **f64 JSON is now round-trip-correct** (`src/dtoa.cyr`, new). Replaced the
  6-decimal `fmt_float_buf(v, 6)` formatter — which lost ~9 mantissa bits on
  values like `1/3`, flushed `|x| < 5e-7` to `0`, and emitted the **non-JSON**
  token `-.00000-` for `Inf`/`NaN`/`|x| >= 2^63` — with a **Grisu2** (Loitsch)
  formatter: integer-only, always-succeeds, output guaranteed to round-trip.
  Non-finite values now serialize as `null` (serde_json / JS convention).
- **Parser is now correctly rounded + DoS-safe.** `_jp_atof` (bayan's JSON number
  parser) is replaced by a Clinger-fast-path + normalized-DiyFp `strtod`
  (`bayan_f64_from_json` / `bayan_f64_parse`) that agrees with a reference
  `strtod` on every tested input — killing the old 1-ULP divergence against
  `math f64_parse`. Its exponent scan **saturates**: the old O(exponent-VALUE)
  apply loop turned a 17-byte `{"x":1e100000000}` into ~237 ms of wasted CPU (an
  algorithmic-complexity DoS); it is now O(len).
- Validated **bit-exact across the entire double range** (all powers of two,
  subnormals, boundaries, 5000+ randoms) for both format→parse round-trip and
  reference-`strtod` parse agreement. +16 tests in `tests/bayan.tcyr`.

## [1.2.0] — 2026-07-16

### Added

- **Per-format sublibs** (the sigil/sandhi `[lib.<name>]` pattern) —
  `cyrius distlib <name>` → `dist/bayan-<name>.cyr` (+ `.deps` stdlib-leaf
  sidecar) for json / yaml / toml / cyml / csv / base64 / u128 / bigint, so
  a consumer that wants one parser doesn't pull the whole bundle as it
  grows. Each is the compile-verified self-contained closure of its
  format's entry points; the 7 carved modules have no cross-deps, so most
  closures are one module — yaml's carries `json.cyr` (shared value tree,
  parser state, number scanner; 2,458 lines vs the full bundle's ~4,750).
  Sublibs expose canonical `bayan_*` names only: `_compat.cyr` aliases
  reference every `bayan_*` symbol and ride only the full `dist/bayan.cyr`.

- **yaml: new module — YAML subset parser into the shared tagged value tree**
  (`src/yaml.cyr`). `bayan_yaml_parse` / `_parse_str` / `_parse_ctx` /
  `_parse_ctx_str` parse a pragmatic YAML subset into the SAME
  `JTAG_*`-tagged `bayan_json_v_*` node graph the JSON value parser produces,
  so one consumer traverses one node shape across both formats (the
  serde-data-model property the Rust originals have). Filed by **agnosai**
  (definition files) and driven equally by **mneme** (Markdown frontmatter) —
  see `docs/development/issues/2026-07-16-agnosai-yaml-parse-into-tagged-value-tree.md`.
  In the subset: block mappings (plain/quoted keys) nested by indentation,
  block sequences (incl. compact `- key: value` items and sequences at the
  parent key's indent), single-line flow sequences, `#` comments
  (quote-aware; mid-word quotes like `O'Brien` are literal), scalars typed as
  null/`~`/bool, strict-JSON-grammar numbers (via the json module's scanner;
  `01`/`1e` fall back to strings), and verbatim quoted strings (one layer
  stripped, no `\`-escape decoding — the toml convention). One leading `---`
  and one `...` marker; leading UTF-8 BOM skipped. **Everything out of
  subset fails loudly** — anchors/aliases/tags (value AND key position),
  block scalars, flow mappings (incl. implicit `[a: b]` entries), multi-doc
  streams, content on marker lines, tabs in indentation, empty flow elements,
  malformed/unterminated quotes — never a silent mis-parse. Reentrant from
  day one (shares the json per-call parser state; errors via
  `bayan_yaml_state_error*` or the `bayan_yaml_last_error*` mirror) and
  depth-capped from day one (shared 128 cap, block + flow). Strings share
  the source buffer (no copy). Hardened by a 36-agent adversarial review
  pass pre-release (6 parser bugs found and fixed, all pinned by tests).
- **yaml: Markdown frontmatter split.** `bayan_yaml_frontmatter_split(src)`
  (+ `_a` variant) splits `---` -fenced YAML frontmatter from a Markdown
  body (`...` also closes; CRLF tolerated; no/unclosed fence → `{0, whole
  input}`, mirroring mneme's interim parser). Accessors
  `bayan_yaml_fm_yaml` / `bayan_yaml_fm_body`.
- `tests/bayan.tcyr` — yaml group: scalar typing, quoting, comments,
  nesting, block/flow sequences, compact items, markers, frontmatter,
  reentrancy, err_pos, depth caps (block + flow), and a loud-rejection
  battery for every out-of-subset form; suite 101 → 249 asserts.

## [1.1.1] — 2026-07-16

### Changed

- **Toolchain: cyrius pin bumped 6.4.10 → 6.4.64.** `cyrius lib sync --full`
  re-synced the vendored `lib/` snapshot (99 files — sakshi/niyama/sigil/
  sandhi/yukti/patra/vani/mabda/sankoch had drifted behind their pins). Full
  suite green on 6.4.64: 86/86 asserts + full-bundle compile smoke.

### Fixed

- **json: parsers now cap recursion depth at 128 (serde_json parity).** Neither
  the value parser (`_jp_parse_value`) nor the streaming parser
  (`_js_parse_value`) bounded its descent, so a deeply nested document
  (`[[[[…` — 2 bytes per level) recursed once per level until the calling
  thread's stack was exhausted — an untrusted-input DoS, and a **parity
  regression** vs the Rust originals, which inherit serde_json's default
  128-level limit. The per-call parser state grew one slot
  (`_JP_STATE_SIZE` 40 → 48, `depth@+40`, zeroed in `_jp_state_init`); both
  descents increment it on entering an array/object branch, decrement on exit,
  and past 128 (`_JP_MAX_DEPTH`) fail through the existing per-call error path
  with `"nesting too deep"` — exactly like any other parse error (value path:
  `bayan_json_state_error()` / mirrored `bayan_json_last_error()`; stream
  path: `JS_EV_ERROR` + the same mirror). 128 open containers still parse;
  the 129th fails. `bayan_json_parse_state_size()` already reports the state
  size, so callers reserving via it are transparent; the documented stack
  pattern is now `var ps[48]`. Reported by agnosai (untrusted HTTP bodies on
  its server surface — blocker #2). See
  `docs/development/issues/2026-07-16-agnosai-json-no-recursion-depth-cap.md`.
  Covered by a new `tests/bayan.tcyr` group (200-deep rejected on both
  parsers, 100-deep parses, exact 128/129 boundary, legacy-entry mirror,
  `_compat` alias parity); suite 86 → 101 asserts.

## [1.1.0] — 2026-07-06

### Added

- **toml: array VALUE element access.** `bayan_toml_parse` has always captured
  an array value (`key = [a, b, c]`) verbatim as one raw bracketed `Str` but
  gave callers no way to reach its elements short of hand-rolling a comma
  splitter. Four new helpers decompose that raw value on demand:
  `bayan_toml_array_parse` (and its allocator-threading `_a` variant) returns a
  vec of top-level element `Str`s; `bayan_toml_is_array` reports whether a value
  is a `[...]` array; `bayan_toml_get_array` is the `get` + `parse` convenience
  (returns `0` for an absent key, else a possibly-empty vec). Elements are
  whitespace-trimmed; a single layer of matching quotes (`"` basic / `'`
  literal) is stripped with the body captured verbatim (no `\`-escape decoding,
  matching the scalar string parser); nested-array elements are returned whole
  for recursive re-parsing; trailing commas yield no phantom element; and `#`
  comments (leading full-line or trailing inline, outside strings) are skipped.
  Element `Str`s share the value's buffer (no copy), like the rest of the
  parser. Legacy `toml_*` aliases added in `_compat.cyr`.

### Fixed

- **toml: array-value capture is now quote-aware for `'…'` and skips `#`
  comments.** The multi-line array-capture scanner in `bayan_toml_parse` only
  tracked `"` basic-string state and had no comment handling, so a literal
  string element containing `]` (e.g. `key = ['a]', 'b']`) closed the outer
  bracket early and truncated the captured value, and a `]` inside a `#` comment
  line of a multi-line array did the same. The scanner now tracks whichever
  quote char opened the string (`"` or `'`) and skips `#`-to-end-of-line
  comments, so both forms round-trip intact. Exercised by the new
  `tests/bayan.tcyr` array group.

## [1.0.4] — 2026-07-03

### Fixed

- **toml: `"""…"""` multi-line strings are no longer silently dropped.** The
  TOML value parser only recognized `'''` (triple **single**-quote) as a
  multi-line delimiter; a `"""` (triple **double**-quote) value fell through to
  the single-line `"…"` branch, where the opening `"` immediately closed against
  the second `"` and the entire body was parsed as an empty string — no error,
  just silent data loss. This broke every consumer whose TOML used `"""`,
  notably takumi building zugot recipes: 436 of 563 recipes use `"""` for their
  `make`/`configure`/`install` build steps, so those steps parsed empty and
  takumi produced zero-payload `.ark` packages with no diagnostic. Fixed by
  parameterizing the multi-line parser/end-finder by delimiter char
  (`_toml_parse_multiline_q` / `_toml_multiline_end_q`, `q` = 34 `"` or 39 `'`)
  and adding a `"""` branch to the value dispatch **before** the single-line
  `"` case. Both triple forms are captured **verbatim** (bayan does not expand
  `\`-escapes anywhere; a `\` at a line end is preserved, so shell build steps
  with backslash line-continuations round-trip intact). The original `'''`
  entry points are kept as thin back-compat wrappers. Covered by a new
  `tests/bayan.tcyr` group (verbatim `"""`, `'''` regression, dispatch
  ordering, embedded quotes, empty `""`) plus an adversarial edge-probe pass
  (EOF/no-close bounds, 4-/6-quote counts, mixed delimiters, real zugot
  recipes) — all green.

## [1.0.3] — 2026-06-23

### Fixed

- **json: value + streaming parsers are now reentrant (thread-safe).** The
  recursive-descent value parser (`bayan_json_v_parse*`) and the event-streaming
  parser (`bayan_json_stream_parse*`) kept their lexer cursor in three process
  globals (`_jp_buf` / `_jp_len` / `_jp_pos`) plus shared error slots, so two
  concurrent parses clobbered each other's cursor mid-descent — wrong/garbage
  value trees or out-of-bounds loads. Replaced the global cursor with a per-call
  40-byte parser-state struct (`{buf, len, pos, err_msg, err_pos}`) threaded as
  the first argument through every parser helper. `bayan_json_v_parse_str` /
  `bayan_json_v_parse` / `bayan_json_stream_parse` keep their signatures and now
  stack-allocate their own state (so existing single-threaded callers are
  unchanged **and** concurrent), mirroring the per-call error into the legacy
  `bayan_json_last_error()` slots only as a back-compat courtesy. Node allocation
  is unchanged — the filed race was the cursor, not the node arena. Reported by
  thoth (parallel MCP tool-result parsing). See
  `docs/development/issues/2026-06-23-thoth-json-value-parser-global-cursor-not-thread-safe.md`.

### Added

- **Reentrant parse API.** `bayan_json_v_parse_ctx(ps, buf, len)` and
  `bayan_json_v_parse_ctx_str(ps, src)` parse into a caller-owned state buffer
  and touch no module globals — the path concurrent consumers use.
  `bayan_json_state_error(ps)` / `bayan_json_state_error_pos(ps)` read the error
  from that state; `bayan_json_parse_state_size()` returns the bytes to reserve
  (stack `var ps[40]` or heap).
- `tests/bayan.tcyr` — JSON value-parser group (nested object/array, ctx path,
  per-call error reporting, trailing-content rejection) and streaming-parser
  group (real `&fn` callbacks asserting per-event dispatch through the reentrant
  `_js_*` path: object/array/key/string/int/float/bool/null/error counts, the
  error mirror, and the `_parse_str` convenience entry); suite 8 → 48 asserts.

### Changed

- `cyrius` pin bumped 6.2.1 → 6.2.37 (closes the manifest/toolchain drift). No
  unrelated source changes; `.tcyr` suite green on 6.2.37.

## [1.0.2] — 2026-06-19

### Fixed

- **u128: aarch64 portability (SIGILL).** `bayan_u128_divmod` and
  `bayan_u64_mulmod` carried unguarded x86 `div`/`mul` inline asm — the raw x86
  machine-code bytes emitted verbatim into the text section on non-x86 targets and
  trapped (SIGILL) on aarch64. Guarded both x86 fast paths with
  `#ifdef CYRIUS_ARCH_X86`: `divmod` falls through to its existing portable
  shift-subtract loop, and `mulmod` gains a `#ifdef CYRIUS_ARCH_AARCH64` path that
  computes the 128-bit product + remainder via the u128 pipeline
  (`bayan_u128_mul` + `bayan_u128_mod`). x86 is byte-identical (the asm path is
  unchanged). Surfaced by cyrius's VR-01 full-tcyr-on-arm64 gate.

## [1.0.1] — 2026-06-12

### Changed

- `cyrius` pin bumped 6.1.24 → 6.2.1 (ecosystem-wide stdlib pin sweep onto the
  current toolchain). No source changes — bayan's `[deps]` carries no carved-out
  modules. Verified green on 6.2.1: `cyrius deps` resolves cleanly, `.tcyr` suite
  8/8, bench 1/1, `dist/bayan.cyr` regenerated via `cyrius distlib`.

## [1.0.0] — 2026-06-10

**Initial carve out of the Cyrius stdlib** (cyrius v6.1.25, first half of
Phase E — the bayan/ganita data/math split). bayan becomes the upstream
source of truth for the data-format & big-integer modules; cyrius folds
`dist/bayan.cyr` byte-identical into `lib/bayan.cyr` (sandhi pattern).

### Added
- **Seven modules carved from cyrius stdlib** (`json`, `toml`, `cyml`,
  `csv`, `base64`, `bigint`, `u128`) — ~3,350 lines, 149 public functions,
  zero cross-module dependencies. Rename-only transform: every public
  function gained the `bayan_` prefix (`json_parse` → `bayan_json_parse`,
  `u256_add` → `bayan_u256_add`, …); internal helpers (`_jp_*` / `_jv_*` /
  `_add64` / …) unchanged.
- **`src/_compat.cyr` back-compat alias module** — 149 forwarding shims
  exporting the legacy cyrius-stdlib names so downstream consumers build
  unchanged during the migration window. Deprecated; removed once the
  ecosystem re-pins.
- **`[lib]` distlib config** — `cyrius distlib` bundles the 7 modules +
  aliases into `dist/bayan.cyr` (3,500 lines), includes stripped, for the
  stdlib fold.
- Smoke entry (`src/main.cyr`, exits 42) + `tests/bayan.tcyr` (canonical
  API + alias parity). Deep coverage lives in cyrius's
  `json`/`toml`/`csv`/`base64`/`bigint`/`u128`/`cyml` `.tcyr` suite.
