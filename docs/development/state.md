# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).
> Last refreshed: 2026-08-28.

## Version

**1.5.3** — **the TOML parser was returning wrong values, and had been since
1.0.0.** mneme reported it
([2026-08-22](issues/2026-08-22-mneme-toml-basic-strings-not-unescaped.md)):
basic-string escapes were never decoded, so `"say \"hi\""` came back with its
backslashes. Measuring that properly turned up nine more defects of the same
shape, one of them worse than anything reported — **there was no `'...'` branch
at all**, so every single-line literal string bayan has ever parsed came back
wearing its quotes.

Three things about this release are worth keeping.

- **It had to be fixed in the parser, not in an accessor.** The report offered
  a `bayan_toml_unescape` a caller applies afterwards. That cannot work: by then
  the string kind is gone, and a basic string decodes where a literal string
  must not. The information only exists where the quote is.
- **The suite was green the whole time.** Every TOML assertion in it had been
  written by reading bayan's output and writing it down. `tests/fixtures/toml/
  strings.vec` — 1,476 vectors from Python's `tomllib` — is the durable fix, and
  it is the third module to need that lesson taught (after `bayan_u256_mul` at
  1.5.1 and `bayan_u64_mulmod` at 1.5.2).
- **The fix shipped a memory-safety bug of its own for a few hours.** The new
  escaped-quote rule in the array capture had no bound and read one byte past a
  document ending in `a = ["x\`. Tests green, vectors green; an adversarial
  review of the fix caught it. Ten mutations were then run against the finished
  work — two of them survived both test layers, and closing those gaps found
  that the hand-written test for the *reported* multi-line defect could not
  actually detect the bug it was written for.

**Two CI gates were also proved to be reporting less than they claimed.**
`scripts/consumer-check.sh` and `ci.yml`'s build/test steps matched
`grep '^warning:'`, and cyrius prints the first warning *concatenated onto the
compile line*. So warning #1 was invisible, and a build whose only diagnostic
was one warning passed. That had been hiding half of a real under-declaration
in the sublib sidecars for months. Same family as the `lint`-always-exits-0 and
`cyrfmt`-reads-only-argv[1] traps below: the gate ran, and proved less than it
said.

Before that: 1.5.2 closed the reference-coverage gap (51% → 100%) and found
`bayan_u64_mulmod` killing the process; 1.5.1 was the P-1 security sweep (20
confirmed defects, two heap overflows, a 125 GB memory blowup); 1.5.0 added
`bayan_pdf_*`; 1.4.2 was toolchain + CI; 1.4.1 armed the Str→cstring
diagnostic; 1.4.0 completed the `_a` JSON surface. Carved from cyrius stdlib at
1.0.0.

## Toolchain

- **Cyrius pin**: `6.5.36` (`cyrius.cyml [package].cyrius`). `cyrius version`
  reports `manifest-pin: 6.5.36` with no drift line; build and test emit
  neither the pin-drift nor the shadow-lib warning.
- **`lib/` matches the pin exactly**: verified against the **released 6.5.36
  tarball** — 108 files, 0 differ. 11 files changed at this bump (`bayan.cyr`,
  `io.cyr`, `patra.cyr`, `sandhi.cyr`, `sankoch.cyr`, `sigil.cyr`, four
  `syscalls_*`, `tls_native_hs12.cyr`).

  At this bump the local `~/.cyrius/versions/6.5.36/lib` also matched the
  release byte for byte. `bin/` did not: of the release's 23 entries, `ci.sh`
  is **absent** locally and `cybs` **differs**, and the local tree carries four
  entries the release does not (`cycc-native-aarch64`, `cycc_cx`,
  `cyrius-repl.sh`, `dlopen-helper.c`). None is used by any gate here — `cycc`,
  `cyrfmt`, `cyrlint` and the `cyrius` wrapper are all identical — but that is
  a measured statement, not an assumption, and `dist/` was regenerated with the
  release toolchain in an isolated `CYRIUS_HOME` regardless.

  **Verify by comparing the trees, not by trusting the sync's exit code.** At
  1.4.0 a green `cyrius lib sync --full` still left five files behind.
- **Pin history**: 6.4.68 → 6.5.4 (1.4.0) → 6.5.16 (commit `97a3476`,
  2026-08-10, **undocumented**) → 6.5.28 (1.4.2) → 6.5.33 (1.5.0) → 6.5.36
  (1.5.3).
- **Caveat on the local snapshot — still live.** `~/.cyrius/versions/<pin>/lib`
  on a machine that also develops cyrius can carry unreleased in-flight edits at
  the same version number: at 6.5.28 its `freelist.cyr` had been edited in place
  with `.29` work. Settle it against the **release tarball**, always.

## Source

Eight data/big-integer modules carved byte-identical from cyrius stdlib
(public functions prefixed `bayan_`), plus two greenfield modules written
in-repo: `yaml` (1.2.0 — parses into json's value tree, so it must sit after
`json.cyr` in bundle order) and `pdf` (1.5.0 — cross-dep-free, so its position
is convention rather than necessity). Regenerated from the tree 2026-08-28:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/pdf.cyr`    | 9527 | 152 | `bayan_pdf_*` |
| `src/json.cyr`   | 1922 | 69 | `bayan_json_*` |
| `src/toml.cyr`   | 1261 | 21 | `bayan_toml_*` |
| `src/yaml.cyr`   | 899  | 12 | `bayan_yaml_*` |
| `src/dtoa.cyr`   | 573  | 3  | `bayan_f64_*` |
| `src/u128.cyr`   | 567  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 546  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 450  | 20 | `bayan_u256_*` |
| `src/base64.cyr` | 214  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 149  | 3  | `bayan_csv_*` |

`toml` gained 4 public functions at 1.5.3 (`bayan_toml_escape` /
`bayan_toml_unescape` and their `_a` twins) and roughly doubled in size — the
escape decoder, the literal-string parser, the rewritten multi-line scanner,
and a good deal of comment recording *why*, since six of the ten defects it
fixes were invisible to every test that existed.

**Allocator-threaded surface: 49 public `_a` functions** across the bundle —
pdf 26, json 15, toml 5, cyml 2, yaml 1. (Measured. The "21" this file carried
from 1.4.0 predated pdf's entire `_a` surface and was stale for three releases;
that is the hazard of writing a count into a file nobody re-measures.) The JSON
value API is complete end to end — construct, mutate, parse and serialize. A consumer can run a whole parse → mutate → serialize cycle on an
arena and measure **0 bytes** of global-bump growth; the assertion that pins
this is mutation-verified.

- `src/_compat.cyr` — 153 back-compat aliases (legacy names → `bayan_*`;
  yaml and the 1.5.3 toml escape helpers are new API, no aliases).
- `dist/bayan.cyr` — **16,308**-line bundle, regenerated via `cyrius distlib`
  at 1.5.3 with the **release** toolchain. This is the artifact folded into
  `cyrius/lib/bayan.cyr`. `src/pdf.cyr` is 9,527 of those lines, so the fold's cost to
  cyrius is dominated by one module; `[lib.pdf]` is a self-contained
  single-module closure if cyrius would rather fold it separately.
- `dist/bayan-<format>.cyr` — per-format sublibs, each `cyrius distlib <name>`-
  generated and compile-verified self-contained, with a `.deps` stdlib-leaf
  sidecar. Canonical `bayan_*` names only. Two sidecars under-declare; see
  Known gaps 2.

  | Sublib | Lines | Stdlib leaves |
  |---|---|---|
  | `bayan-pdf`    | 9535 | 9 (single-module closure — no `json.cyr`, no `dtoa.cyr`) |
  | `bayan-yaml`   | 3408 | 10 (carries `json.cyr` — shared value tree / parser state) |
  | `bayan-json`   | 2506 | 10 |
  | `bayan-toml`   | 1269 | 7 (+ `fmt`, undeclared — gap 2) |
  | `bayan-u128`   | 575  | 0 |
  | `bayan-cyml`   | 554  | 7 (+ `fmt`, undeclared — gap 2) |
  | `bayan-bigint` | 458  | 2 |
  | `bayan-base64` | 222  | 2 |
  | `bayan-csv`    | 157  | 3 |

## Tests

- `tests/bayan.tcyr` — **839 asserts, green**. base64, u128, alias parity, the
  json value/streaming parsers and their depth caps, toml, yaml, the 1.3.0
  Str-entry dispatch regression, the 1.4.0 `_a` block, the 1.5.0 pdf block, the
  1.5.1 sweep guards, the 1.5.2 coverage additions.

  **1.5.3 adds seven toml groups** (up from 749 asserts at 1.5.2): basic-string
  escapes, single-line literal strings, multi-line conformance, array-element
  escape rules, the public escape/unescape helpers, and the value arms
  (comments, CRLF, keyless lines, document-swallowing). Plus a **truncation
  property test**: eight documents cut at every length, asserting no key, value
  or section name reaches past its source buffer — the guard for the
  memory-safety bug the fix itself introduced.

  **Mutation-verified.** Ten mutations, one per part of the 1.5.3 fix, each
  turns the suite red. Two did not at first: the delimiter-run rule and the
  escaped-quote rule in the multi-line scan **mask each other** on the reported
  input, so the test written for the filed repro passed with either one removed.
  A test that cannot fail is a test that has stopped being a test.
- `tests/vectors.tcyr` — **oracle-driven, expected values from Python**:
  12,334 u128 checks, 656 f64 checks, and **1,476 TOML string vectors** (new at
  1.5.3, from `tomllib`). Kept in its own file so machine-generated checks do
  not swamp the hand-written assertion counts; **10 asserts**, green.
  Regenerate with `scripts/gen-numeric-vectors.py` and
  `scripts/gen-toml-vectors.py`; CI requires both regenerations to be
  byte-identical.
- `tests/pdf_flate.tcyr` — the compression path, isolated because it is the
  only test that pulls in `lib/sankoch.cyr`. **19 asserts, green.**
- `tests/pdf_fixture.cyr` — writes a representative document for CI to run
  through `scripts/pdfcheck.py`. The writer's real gate: the assertions cannot
  see a byte-accounting bug, and an independent strict parser can.
- `tests/bayan.fcyr` — a real fuzz harness. **671 inputs, 219 of which still
  parse, 269 page walks** — re-measured at 1.5.3 by instrumenting a copy and
  running it. The 582/183/245 this file carried since 1.5.0 was stale on all
  three counts; `cyrius fuzz` prints only `fuzz: ok`, so nothing in the tree
  reports these numbers and nothing would have caught the drift. Note honestly
  what it did NOT catch: the `/Length` overflow that segfaulted the reader
  survived it, because byte-flipping a corpus never produces a near-i64-max
  integer.
- `tests/bayan.bcyr` — real benchmarks. Results in
  [`benchmarks.md`](../benchmarks.md).
- `src/main.cyr` — full-bundle compile smoke (exits 42).

### Coverage

`cyrius coverage` — **454/454 fns (100%)**, 13/13 files, gated at `--min 100`.

**It is reference coverage.** A function being called is not a function being
correct — and 1.5.3 is the sharpest available demonstration: `src/toml.cyr` sat
at 100% reference coverage through 1.5.2 while returning wrong values from ten
distinct defects. The oracle vectors and the mutation-verified regression
guards are what check answers.

## CI

`.github/workflows/ci.yml` is the gate; `release.yml` calls it via
`workflow_call` before publishing. Properties worth remembering when editing it:

- **Regenerate `dist/` with the PINNED toolchain — the release tarball, not
  whatever `~/.cyrius` happens to hold.** Install the release into an isolated
  home:

  ```sh
  curl -sfLO https://github.com/MacCracken/cyrius/releases/download/<pin>/cyrius-<pin>-x86_64-linux.tar.gz
  tar xzf cyrius-<pin>-x86_64-linux.tar.gz
  H=/tmp/cy<pin>; mkdir -p "$H/versions/<pin>"
  cp -R cyrius-<pin>-x86_64-linux/bin cyrius-<pin>-x86_64-linux/lib "$H/versions/<pin>/"
  ln -sfn "$H/versions/<pin>/bin" "$H/bin"; ln -sfn "$H/versions/<pin>/lib" "$H/lib"
  CYRIUS_HOME=$H PATH="$H/bin:$PATH" cyrius distlib --all --check
  ```

- **Install via the upstream `scripts/install.sh`, never a hand-rolled tar.**
  `cyrius deps` requires the snapshot at `~/.cyrius/versions/<pin>/lib`.

- **Three gate traps, all the same shape: the gate ran and proved less than it
  said.**
  - `cyrius lint` always exits 0 — the CI step parses its `N warnings` /
    `N untracked deferrals` lines instead. `fmt --check` *does* exit 1.
  - The format step must stay a **per-file loop**. `cyrfmt` reads only
    `argv[1]` and silently ignores the rest, so `cyrius fmt src/*.cyr --check`
    checks the first file and exits 0.
  - **`grep '^warning:'` misses the first warning** — cyrius prints it
    concatenated onto the `compile <src> -> <out> [arch] ` prefix line. Fixed
    in 1.5.3 in `ci.yml`'s build and test steps and in
    `scripts/consumer-check.sh`; match `warning:` **anywhere**. Before the fix,
    a build whose only diagnostic was one warning passed, and the consumer gate
    had been reporting one missing symbol per bundle where there were two.

- **`scripts/consumer-check.sh` must build with `--no-deps`**, or a consumer
  missing a declared leaf still compiles and the check passes vacuously. It also
  subtracts a **measured harness floor** — `lib/syscalls.cyr` alone emits
  `undefined function 'alloc'`, which belongs to the scaffold rather than to any
  bundle — and asserts that floor is exactly that one warning, so the exemption
  cannot widen. Only scaffold warnings are subtracted, never a declared leaf's:
  a leaf's unresolved call is precisely the under-declaration the gate exists to
  catch.

Gates: pin-drift · version consistency (VERSION / manifest / CHANGELOG / all 10
dist headers) · `lib/` vs snapshot tree diff · format (src **and** tests) ·
lint (0 warnings, 0 deferrals) · vet · build with 0 warnings · smoke exits 42 ·
test · **pdf oracle** · **pdf fixture polarity** · **pdf metric-table
regeneration** · **pdf naming hazards** · fuzz · bench · `coverage --min 100` ·
**numeric vectors regenerate identically** · **toml vectors regenerate
identically** (new at 1.5.3) · `distlib --all --check` · regeneration leaves no
tree diff · consumer-check.

The 1.5.0 gate lessons still hold and generalise:

- **The oracle gate runs the writer's output through an independent parser**
  (`scripts/pdfcheck.py`), not through bayan's own reader. A round trip through
  your own code proves consistency, not correctness. The toml vector gate is
  the same principle applied to a parser instead of a writer.
- **The fixture-polarity gate asserts the `bad-*` fixtures still FAIL.**
- **A gate must not depend on a package the property under test does not depend
  on.** The metric-table gate skips rather than fails where groff is absent.
  The toml vector gate obeys the same rule: `tomllib` is Python stdlib from
  3.11, so it installs nothing.
- **The naming-hazard gate** forbids a bare `_pdf_<word>` helper and the
  reserved `_int` / `_cstr` / `_ptr` / `_str` overload-slot suffixes.

## Known gaps

1. **The TOML parser is a documented SUBSET, and seven structural gaps degrade
   silently.** Quoted keys, dotted keys, inline tables, empty tables (which
   shift array-of-table indices), duplicate keys (lookup returns the FIRST where
   the ecosystem takes the last), untrimmed header names, and
   `bayan_toml_is_array` being a byte heuristic that classifies a bracketed
   STRING as an array — which 1.5.3 made reachable for literal strings too, by
   correctly stripping the quotes that used to hide the `[`. New at 1.5.3:
   each is now stated in `src/toml.cyr`'s header — an undocumented gap is how a
   downstream repo ends up hand-rolling a second parser — and all six are filed
   together in
   [2026-08-28](issues/2026-08-28-toml-structural-subset-gaps.md).
   Deliberately not fixed in 1.5.3: each changes the parser's data model, and
   several want `bayan_toml_parse` to stop returning a flat vec.
2. **Two sublib `.deps` sidecars under-declare.** `bayan-toml` and `bayan-cyml`
   both need `+fmt` (`fmt_int_buf` *and* `fmt_int`). Upstream — the sidecars are
   generated by `cyrius distlib`, which does not close over the stdlib's own
   unincluded deps. Filed:
   [2026-08-19](issues/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md),
   re-measured at 1.5.3 (the issue's original table was stale, and the gate that
   was meant to police it had been hiding one of the two symbols). Held in
   `consumer-check.sh`'s `EXPECTED_FAIL`, which fails if either starts passing.
3. **`lib/bayan.cyr` is bayan's own fold vendored back into bayan's own
   `lib/`.** Nothing includes it, so it is inert — but it defines the same
   symbols as `src/`, the exact last-definition-wins hazard the ten dead
   pre-carve modules were removed for at 1.4.0. `lib sync --full` re-adds it on
   every bump, so deleting it is not durable; the durable fix is upstream (a
   `lib sync` self-exclusion) or a build-time guard.

   **Less sharp than at 1.5.0.** The 6.5.36 snapshot carries bayan **1.5.2**,
   not 1.4.1, so an accidental include is now one release behind rather than
   two and missing no whole module. It is still an older `bayan_toml_*` — i.e.
   the one with all ten string defects.
4. **`docs/` is still largely scaffold, but less so.** 1.5.0 added the first two
   ADRs and `docs/benchmarks.md`. Still unrecorded: the carve itself, `_compat`
   aliases, the sublib split, yaml-into-json's-tree, the 1.4.1 `obj_get`
   non-rename, and now the 1.5.3 decision to decode in the parser rather than
   in an accessor — which is the best ADR candidate on the list, because the
   reasoning generalises to yaml and cyml.
5. **`docs/development/roadmap.md` M1/M2 are still unfilled template stubs.**
6. **The two flat lookup APIs disagree about their key type.**
   `bayan_json_get(pairs, key)` compares with `str_eq` and needs a **`Str`**;
   `bayan_toml_get(pairs, key)` compares with `str_eq_cstr` and needs a
   **cstring**. Passing the wrong one yields a silent "not found". 1.5.1
   corrected the wrong doc claim on `bayan_toml_get`; 1.5.3 found the identical
   wrong claim still standing on `bayan_toml_get_array`, and the same
   undocumented trap on `bayan_toml_get_sections`. Both are now stated.
   Reconciling the signatures is still a breaking change and wants its own
   release.
7. **The 1.4.1 Str→cstring diagnostic misses the inline form.**
   `bayan_json_v_obj_get(o, str_from("k"))` — the spelling in the filed
   issue's own reproduction — compiles with zero warnings. The `: cstring`
   annotation fires only when the argument is a named `Str`-typed local. And the
   symptom has changed since filing: it no longer segfaults, it returns a silent
   0, which defers the fault to whatever the caller does with it. Annotated on
   [2026-08-04](issues/2026-08-04-agnosai-json-obj-get-takes-cstr-while-obj-set-takes-str.md).
8. **`src/cyml.cyr` carries the project's two remaining fixed read caps**, both
   truncating silently and reporting success — the shape 1.5.1 removed from
   toml, where it had lost 1,893 keys from a 300 KB file. `bayan_cyml_parse_file_r`
   caps at 256 KiB and returns `Ok(...)` on a truncated document;
   `_cyml_read_file_trimmed` declares `var buf[4096]` and cuts a
   `${file:PATH}` expansion at 4,095 bytes. Three unchecked allocations in
   `bayan_cyml_parse` fault under exhaustion rather than returning 0. All
   documented in the module as of 1.5.3, not fixed.

   *A first draft of this entry called the 256 KiB one "the last fixed cap in
   the project" — in the same release whose CHANGELOG says each doc fix "was
   verified against the code it documents". It was not; an adversarial review
   found the 4 KiB one 173 lines above it. Recorded because the failure is
   the exact one this file keeps warning about.*
9. **`src/csv.cyr` is an RFC 4180 subset**, not RFC 4180: a trailing empty
   field is not emitted (`a,` parses to one field where the RFC has two, so a
   round trip loses a column), records are LF-terminated where the RFC says
   CRLF, and CR does not trigger quoting. Documented at 1.5.3, not fixed.

## Scripts

- `scripts/consumer-check.sh` — compiles a throwaway consumer against every
  `dist/` bundle from exactly the leaves its `.deps` sidecar declares.
- `scripts/gen-numeric-vectors.py` — u128 + f64 vectors from Python.
- `scripts/gen-toml-vectors.py` — **new at 1.5.3.** TOML string vectors from
  `tomllib`. Every line is verified with the oracle before it is written: a
  document Python rejects aborts generation rather than becoming a vector that
  encodes a wrong belief.
- `scripts/pdfcheck.py`, `scripts/check-widths.py`, `scripts/gen-widths.py` —
  the pdf oracle and metric tables.

## Dependencies

Direct (declared in `cyrius.cyml [deps].stdlib`): string, fmt, alloc, io,
vec, str, syscalls, assert, bench, result, fnptr, tagged. The dist bundle
strips includes — consumers must supply these (notably `result`, which is
NOT in cyrius's own stdlib auto-prepend set).

No sibling `[deps.NAME]` entries, so `cyrius deps` writes no `cyrius.lock`.

## Consumers

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr`. The 6.5.36 snapshot
  carries **1.5.2**, so the fold is one release behind and the next refold
  carries the whole TOML string repair. Refolding is not optional in the usual
  sense: every cyrius-internal consumer of `bayan_toml_*` is currently reading
  values with their escapes intact.
- **mneme** — the named `bayan_pdf_*` consumer, and the filer of the 1.5.3
  issue. ⚠ **`_cfg_toml_unesc` in `src/core_config.cyr` must be removed on
  re-pin, or mneme will double-decode**; its `tests/core_config.tcyr` has
  assertions written to fail loudly at that moment. `_cfg_toml_esc` can go too
  — `bayan_toml_escape` replaces it. Separately, mneme still ships a hand-rolled
  PDF writer in `src/io_export_pdf.cyr` (**485** lines — it has grown since the
  443 this file recorded at 1.5.0) that 1.5.0 supersedes, and two bugs found in
  that file while reading it are mneme's to fix.
- **Any consumer of `bayan_toml_*`** should re-check for compensating code
  before re-pinning. The compensation is invisible from here, which is why the
  CHANGELOG entry leads with a banner.
- Downstream repos using json/toml/csv/base64/bigint/u128 migrate to
  `bayan_*` on re-pin (back-compat aliases bridge the window).

## Next

See [`roadmap.md`](roadmap.md) — `bayan_markdown_*` is the next feature
milestone (driver: the **mneme** port), and it pairs naturally with the PDF
work: a markdown AST plus `bayan_pdf_wrap` is the whole "notes to a laid-out
PDF" story.

Two things 1.5.3 argues should come first, or at least alongside:

- **A tagged-tree TOML parser** (`bayan_toml_v_parse` into json's existing
  value tree, the way yaml already does). It is the answer to Known gaps 1 and
  6 at once — dotted keys and inline tables both want nesting, and it gives the
  TOML surface the same shape as the JSON and YAML ones.
- **Escape handling in `yaml.cyr` and `cyml.cyr`.** The mneme issue noted both
  also have no unescape. That was true and is still true; 1.5.3 fixed only the
  module that was reported. The reasoning that forced the fix into the parser
  applies unchanged to both.

Known follow-ons for pdf: encrypted documents are detected and rejected rather
than handled; `LZWDecode` is rejected by name; there is no layout/flow API.
ganita (math-domain) is the sibling carve; the 6.5.36 snapshot ships it at
**1.1.4**.
