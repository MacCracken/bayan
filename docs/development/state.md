# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).
> Last refreshed: 2026-08-21.

## Version

**1.5.0** — **PDF read/write, `bayan_pdf_*`.** The roadmap's P2 item ships as
`src/pdf.cyr`: 9,348 lines, 152 public functions, the largest module in the
bundle by a wide margin and the first that is neither a stdlib carve nor a
text-format parser. Writer and reader both. Cyrius pin `6.5.28` → `6.5.33`.

The module is shaped by a close reading of **mneme**'s hand-rolled writer,
which it supersedes. That reading found the structural layer correct — the
byte-exact `/Length`, the 20-byte xref entries, one `BT`/`ET` per line — and
the typography layer wrong: an 80-**character** wrap in a proportional face
(a measured 4.26× spread, running 308 pt off a 595 pt page at worst), no
`/Encoding` on the font (so `Résumé` renders `RÃ©sumÃ©` and an em-dash
vanishes), no compression, and silent failure on write. bayan fixes each,
and the CHANGELOG records which mneme defect each choice answers.

**The module was reviewed adversarially before release, and that pass was not
ceremonial.** Five lenses over the new code, every finding handed to a separate
agent told to refute it: eighteen candidates, **ten survived with a
reproducer**, all ten fixed. One was a **remote SIGSEGV from a 428-byte file**
— a `/Length` near i64 max made an additive bounds check wrap negative, so the
guard passed and the reader dereferenced ~9.2 exabytes below its buffer. It is
now `bad-huge-length.pdf` in the fixture set and a mutation-verified assertion
in the suite. The lesson to carry: 446 passing assertions, a strict external
validator, and a fuzz harness all reported green on that code. None of them
generate a near-i64-max integer, and none of them were looking for wraparound.

Two more things worth carrying forward as habits rather than facts:

- **Byte offsets are measured, never predicted.** mneme's `var offset = 9;` is
  `len("%PDF-1.4\n")` and is correct only until a second header line exists.
  bayan reads each offset off the output builder immediately before appending
  the object, then re-checks every recorded offset against the bytes it names
  before `to_bytes` returns.
- **The acceptance oracle was mutation-tested before it was trusted**, and
  that exercise found two bugs *in the oracle*: a `\s*endstream` match that let
  an off-by-one `/Length` slide through, and a tuple/int comparison that
  crashed on every PDF-1.5 file. A gate you have not tried to fool is not a
  gate.

Before that: 1.4.2 was toolchain + CI (pin `6.5.16` → `6.5.28`, 4 CI steps to a
full gate); 1.4.1 armed the Str→cstring diagnostic on `bayan_json_v_obj_get`;
1.4.0 completed the allocator-threaded (`_a`) JSON value surface; 1.3.0 renamed
the cstr+len parse entries `_str` → `_buf`; 1.2.1 made float serialization
round-trip-correct (Grisu2); 1.2.0 added `yaml`. Carved from cyrius stdlib at
1.0.0 (2026-06-10).

## Toolchain

- **Cyrius pin**: `6.5.33` (`cyrius.cyml [package].cyrius`). `cyrius version`
  reports `manifest-pin: 6.5.33` with no drift line; build and test emit
  neither the pin-drift nor the shadow-lib warning.
- **`lib/` matches the pin exactly**: verified against the **released 6.5.33
  tarball** — 108 files, 0 differ. At this bump the local
  `~/.cyrius/versions/6.5.33/lib` also matched the release byte for byte, which
  is not something to assume (see the caveat below); it was checked.

  **Verify by comparing the trees, not by trusting the sync's exit code.** At
  1.4.0 a green `cyrius lib sync --full` still left five files behind. This time
  it did land clean, but the check is the tree diff either way.
- **`lib/` grew 99 → 108 files** at this pin: `unicode/` (7 files — `_decode`,
  `categories`, `casefold`, `normalize` + generated data tables),
  `async_macos.cyr`, `thread_macos.cyr`. None is in `[deps].stdlib`, so none is
  auto-prepended; they ride along because `--full` vendors the whole snapshot.
- **Pin history**: 6.4.68 → 6.5.4 (1.4.0) → 6.5.16 (commit `97a3476`,
  2026-08-10, **undocumented** — no CHANGELOG entry, no state refresh) →
  6.5.28 (1.4.2) → 6.5.33 (1.5.0).
- **Caveat on the local snapshot — still live.** `~/.cyrius/versions/<pin>/lib`
  on a machine that also develops cyrius can carry unreleased in-flight edits at
  the same version number: at 6.5.28 its `freelist.cyr` had been edited in place
  with `.29` work, so a local tree diff showed drift CI would never see. Settle
  it against the **release tarball**, always. At 6.5.33 the two agreed, but that
  was established by checking, not by assuming.

## Source

Eight data/big-integer modules carved byte-identical from cyrius stdlib
(public functions prefixed `bayan_`), plus two greenfield modules written
in-repo: `yaml` (1.2.0 — parses into json's value tree, so it must sit after
`json.cyr` in bundle order) and `pdf` (1.5.0 — cross-dep-free, so its position
is convention rather than necessity). Regenerated from the tree 2026-08-21:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/pdf.cyr`    | 9348 | 152 | `bayan_pdf_*` |
| `src/json.cyr`   | 1766 | 69 | `bayan_json_*` |
| `src/yaml.cyr`   | 878  | 12 | `bayan_yaml_*` |
| `src/dtoa.cyr`   | 573  | 3  | `bayan_f64_*` |
| `src/toml.cyr`   | 547  | 17 | `bayan_toml_*` |
| `src/u128.cyr`   | 526  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 422  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 367  | 20 | `bayan_u256_*` |
| `src/base64.cyr` | 179  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 99   | 3  | `bayan_csv_*` |

**Allocator-threaded surface: 21 public `_a` functions** across the bundle, of
which the JSON value API is complete end to end — construct (8, since v5.8.36),
mutate (`obj_set_a`, 1.4.0), parse (`parse_a` / `parse_buf_a` / `parse_ctx_a`,
1.4.0) and serialize (`build_a` / `build_pretty_a`, 1.4.0). A consumer can run a
whole parse → mutate → serialize cycle on an arena and measure **0 bytes** of
global-bump growth; the assertion that pins this is mutation-verified.

- `src/_compat.cyr` — 153 back-compat aliases (legacy names → `bayan_*`;
  yaml is new API, no aliases).
- `dist/bayan.cyr` — **14,905**-line bundle (canonical + alias + internal
  helper fns), regenerated via `cyrius distlib` at 1.5.0. This is the artifact
  folded into `cyrius/lib/bayan.cyr`. It nearly tripled at this release: `pdf`
  alone is 9,348 of those lines, so the fold's cost to cyrius is now dominated
  by one module. If that becomes a problem, `[lib.pdf]` is already a
  self-contained single-module closure and can be folded separately.
- `dist/bayan-<format>.cyr` — per-format sublibs (the sigil/sandhi
  `[lib.<name>]` pattern), each `cyrius distlib <name>`-generated,
  compile-verified self-contained, with a `.deps` stdlib-leaf sidecar
  (u128 has none — its closure needs no stdlib leaf at all).
  Canonical `bayan_*` names only — `_compat` aliases ride the full bundle.
  Two sidecars under-declare; see Known gaps 2.

  | Sublib | Lines | Stdlib leaves |
  |---|---|---|
  | `bayan-pdf`    | 9356 | 9 (single-module closure — no `json.cyr`, no `dtoa.cyr`) |
  | `bayan-yaml`   | 3231 | 10 (carries `json.cyr` — shared value tree / parser state) |
  | `bayan-json`   | 2350 | 10 |
  | `bayan-toml`   | 555  | 6 |
  | `bayan-u128`   | 534  | 0 |
  | `bayan-cyml`   | 430  | 5 |
  | `bayan-bigint` | 375  | 2 |
  | `bayan-base64` | 187  | 2 |
  | `bayan-csv`    | 107  | 3 |

  `bayan-pdf` is the largest sublib and the cleanest: pdf carries its own
  `bayan_pdf_obj_*` graph and its own decimal emitter, so neither `json.cyr`
  nor `dtoa.cyr` rides along. Contrast `bayan-yaml`, which pays 3,231 lines to
  ship an 878-line module because it reuses json's value tree.

## Tests

- `tests/bayan.tcyr` — base64 encode/decode + u128 arithmetic + alias parity +
  json value-parser reentrancy (nested parse, ctx path, per-call error
  reporting, trailing-content rejection) + json streaming-parser callbacks
  (real `&fn` handlers asserting per-event dispatch) + json recursion-depth
  cap (200-deep rejected on both parsers, 100-deep parses, 128/129 boundary,
  alias parity) + toml triple-quoted strings + toml array-value element access
  + yaml (scalar typing, quoting, comments, nested mappings, block/flow/compact
  sequences, doc markers, frontmatter split, reentrancy, err_pos, block+flow
  depth caps, and a loud-rejection battery for every out-of-subset form) +
  the 1.3.0 Str-entry dispatch regression + the 1.4.0 `_a` block.

  The `_a` block tests the contract rather than the symbols: `_a` output is
  byte-identical to the non-`_a` path (compact *and* pretty), 200
  parse→obj_set→build cycles through an arena grow the global bump by **0
  bytes** while the same 200 on the global path leak **>100 KB**, an exhausted
  arena surfaces as a normal parse error instead of a write through address 0,
  `obj_set_a` returns −1 on a null / non-object target, and a tree survives
  `reset_via` + re-parse.

  **Mutation-verified**: reverting one `alloc_via(a, …)` to `alloc(…)` in the
  string parser turns the zero-growth assertion into `got 35200, expected 0`.
  A guard no test can reach is a guard that silently rots.

  **1.5.0 adds a pdf block**: the standard-14 metrics against Adobe's
  documented widths, metric measurement and wrap (including the 4.26× spread
  that makes a character-count wrap wrong, asserted as a number), WinAnsi
  transcoding both ways, the object model and its wrong-tag/out-of-range
  behaviour, parse↔serialise token-exactness (`0.50` stays `0.50`), the
  `N G R` ambiguity in all three of its forms, a loud-rejection battery, the
  writer pipeline, a writer→reader round trip, the on-disk fixtures, and
  reentrancy across two concurrent parser states.

  A **hardening block** pins the ten defects the pre-release adversarial review
  confirmed, so each has a regression guard with a known failure mode rather
  than a hypothetical one.

  **433 asserts, green** on cycc 6.5.33.
- `tests/pdf_flate.tcyr` — the compression path, isolated because it is the
  only test that pulls in `lib/sankoch.cyr`. The main suite proves the
  hook-ABSENT contract (valid uncompressed output, a loud reader error); this
  one installs the hooks and proves the hook-PRESENT one, including that
  compressed and uncompressed output extract **identical** text. Keeping them
  in separate binaries means neither can mask the other. **19 asserts, green.**
- `tests/pdf_fixture.cyr` — writes a representative document (two pages, four
  faces, wrapped body copy, graphics, `/Info`) for CI to run through
  `scripts/pdfcheck.py`. This is the writer's real gate: the assertions above
  cannot see a byte-accounting bug, and an independent strict parser can.
- `tests/bayan.fcyr` — **a real fuzz harness as of 1.5.0.** It feeds the fixture
  corpus into the PDF reader whole, truncated at sixteen fractions, and
  byte-flipped at a stride, plus a set of degenerate inputs. Instrumented on
  2026-08-21: **582 inputs, 183 of which still parse and 245 pages walked** — so
  it exercises the success path too, not only the reject path. Note honestly
  what it did NOT catch: the `/Length` overflow that segfaulted the reader
  survived this harness, because byte-flipping a corpus never produces a
  near-i64-max integer. Mutation fuzzing finds a different class of bug than
  value-boundary reasoning does, and this project now has evidence of the gap. The contract is
  that no input reads out of bounds, loops forever, or aborts the process.
  A denser sweep flipping **every** byte was also run clean before shipping.
- `tests/bayan.bcyr` — **real benchmarks as of 1.5.0**, replacing the no-op that
  reported `noop: 2ns avg`. Results in [`benchmarks.md`](../benchmarks.md).
- `src/main.cyr` — full-bundle compile smoke (exits 42).
- Deep per-module coverage lives in cyrius's `.tcyr` suite (json/toml/csv/
  base64/bigint/u128/cyml).

### Coverage

`cyrius coverage` — **167/456 fns (36%)**, 10/13 files referenced, against a
`--min 30` gate. Reference coverage is a floor, not a correctness proof, and
the deep per-module suite for the carved modules still lives upstream in
cyrius — but pdf's own coverage is bayan's to keep, and 72 distinct
`bayan_pdf_*` symbols are referenced by the two pdf test files.

Adding 152 public functions in one release moves this number a long way, in
both directions: the denominator grew by 121 while the numerator grew by 65.
The gate held because the pdf block was written alongside the module rather
than after it.

| Module | Referenced |
|---|---|
| `pdf.cyr`    | 72/152 |
| `yaml.cyr`   | 11/12 |
| `json.cyr`   | 37/69 |
| `toml.cyr`   | 6/17  |
| `u128.cyr`   | 3/35  |
| `base64.cyr` | 2/4   |
| `dtoa.cyr`   | 2/3   |
| `bigint.cyr` | **0/20** |
| `cyml.cyr`   | **0/17** |
| `csv.cyr`    | **0/3**  |

## CI

`.github/workflows/ci.yml` is the gate; `release.yml` calls it via
`workflow_call` before publishing anything. Rewritten at 1.4.2 from 4 steps to
a full sweep. Three properties worth remembering when editing it:

- **Regenerate `dist/` with the PINNED toolchain — the release tarball, not
  whatever `~/.cyrius` happens to hold.** The cyrius repo is frequently mid-flight
  at the same version number: on 2026-08-19 the local `cyrius` self-reported
  `6.5.28` while carrying unreleased `.29` distlib fixes, and `dist/` generated
  with it was STALE on CI (sidecar bytes count toward `--check` staleness, so the
  `.cyr` looked fine and the `.deps` failed it). To verify the way CI does,
  install the release into an isolated home:

  ```sh
  curl -sfLO https://github.com/MacCracken/cyrius/releases/download/<pin>/cyrius-<pin>-x86_64-linux.tar.gz
  tar xzf cyrius-<pin>-x86_64-linux.tar.gz
  H=/tmp/cy<pin>; mkdir -p "$H/versions/<pin>"
  cp -R cyrius-<pin>-x86_64-linux/bin cyrius-<pin>-x86_64-linux/lib "$H/versions/<pin>/"
  ln -sfn "$H/versions/<pin>/bin" "$H/bin"; ln -sfn "$H/versions/<pin>/lib" "$H/lib"
  CYRIUS_HOME=$H PATH="$H/bin:$PATH" cyrius distlib --all --check
  ```

  The same caveat explains a local-only `lib/` diff: `~/.cyrius/versions/<pin>/lib`
  can be edited in place by in-flight work, while bayan's vendored copy holds the
  released content. Against the release tarball, `lib/` matches exactly.

- **Install via the upstream `scripts/install.sh`, never a hand-rolled tar.**
  `cyrius deps` requires the snapshot at `~/.cyrius/versions/<pin>/lib`; a
  hand-untar into `~/.cyrius/{bin,lib}` satisfies the compiler but not `deps`,
  which fails with *"pins version X but it is not installed"*. The installer
  creates `versions/<pin>/{bin,lib}` and symlinks `~/.cyrius/{bin,lib}` at
  them. Compare `lib/` against `versions/<pin>/lib`, not the symlink.

- **`cyrius lint` and `cyrius fmt --check` do not both gate by exit code.**
  `lint` always exits 0 — the CI step parses its `N warnings` /
  `N untracked deferrals` lines instead. `fmt --check` *does* exit 1.
  `cyrius build` exits non-zero on errors but only *warns* on the diagnostics
  that matter here (bad pointer typing, `lib/` shadowing, pin drift), and
  `--strict` does not promote them — so that step greps for `^warning:`.

  The format step must stay a **per-file loop**. `cyrfmt` reads only `argv[1]`
  and silently ignores the rest, so `cyrius fmt src/*.cyr --check` checks the
  first file and exits 0 — verified here by passing a known-good then a
  known-bad file and getting a green. patra records the same trap (libro sat
  green over five unformatted files on exactly that form).
- **`scripts/consumer-check.sh` must build with `--no-deps`.** `cyrius build`
  auto-prepends everything in `[deps].stdlib`, so a consumer missing a declared
  leaf still compiles and the check passes vacuously. Verified by deleting
  leaves from a sidecar one at a time: without `--no-deps` all eight still
  reported clean.

Gates: pin-drift · version consistency (VERSION / manifest / CHANGELOG / all 10
dist headers) · `lib/` vs snapshot tree diff · format (src **and** tests) ·
lint (0 warnings, 0 deferrals) · vet · build with 0 warnings · smoke exits 42 ·
test · **pdf oracle** · **pdf fixture polarity** · **pdf metric-table
regeneration** · **pdf naming hazards** · fuzz · bench · `coverage --min 30` ·
`distlib --all --check` · regeneration leaves no tree diff · consumer-check.

Four gates were added at 1.5.0, and the shape of each is worth keeping:

- **The oracle gate runs the writer's output through an independent parser**
  (`scripts/pdfcheck.py`), not through bayan's own reader. A round trip through
  your own code proves consistency, not correctness.
- **The fixture-polarity gate asserts the `bad-*` fixtures still FAIL.** A
  validator that quietly goes lenient passes every happy-path check ever
  written; this is the only step that would notice.
- **The metric-table gate re-runs `scripts/gen-widths.py`** and diffs its output
  against what is in `src/pdf.cyr`, so the generated data cannot drift from its
  generator.
- **The naming-hazard gate** forbids a bare `_pdf_<word>` helper (mneme defines
  14 of them and a duplicate fn name in cyrius silently rebinds even earlier
  call sites) and the reserved `_int` / `_cstr` / `_ptr` / `_str` overload-slot
  suffixes. `_by_str` is the one deliberate exception, mirroring
  `bayan_json_v_obj_get_by_str`; its base name does not exist, so nothing is
  ambiguous.

## Known gaps

Surfaced by the 2026-08-19 state review. Items 1 and 8 of the original list
were fixed in 1.4.2 (toml warnings, lint); **item 1 of this list was fixed in
1.5.0**; the rest remain, each its own change.

1. ~~**`tests/bayan.fcyr` and `tests/bayan.bcyr` are `cyrius init`
   scaffolds.**~~ **Fixed in 1.5.0.** The fuzz harness now drives the PDF
   reader over the fixture corpus, truncated and byte-flipped (582 inputs, 183
   of which still parse); the bench measures seven real operations; and
   `docs/benchmarks.md` exists. Both were vacuous *while CI ran them*, which is
   the worst state for a gate to be in — it reports PASS and proves nothing.
2. **Two sublib `.deps` sidecars under-declare.** `bayan-toml` needs
   `+string +fmt`, `bayan-cyml` needs `+fmt`; a consumer following the sidecar
   gets a green build (the compiler only *warns* on undefined functions) and a
   broken binary. Upstream — the sidecars are generated by `cyrius distlib`,
   which does not close over the stdlib's own unincluded deps. Filed:
   [2026-08-19](issues/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md).
   Held in `consumer-check.sh`'s `EXPECTED_FAIL`, which fails if either starts
   passing.
3. **`bigint` (0/20), `cyml` (0/17) and `csv` (0/3) are referenced by no test
   in bayan's own suite** — their coverage still lives upstream in cyrius,
   which is where it was before the carve. bayan owns them now.
4. **`lib/bayan.cyr` is bayan's own fold vendored back into bayan's own
   `lib/`** (1.4.1, from the pinned snapshot). Nothing in `src/`, `tests/`, or
   `cyrius.cyml` includes it, so it is inert — but it defines the same symbols
   as `src/`, the exact last-definition-wins hazard the ten dead pre-carve
   modules were removed for at 1.4.0. `lib sync --full` re-adds it on every
   bump, so deleting it is not durable; the durable fix is upstream (a
   `lib sync` self-exclusion) or a build-time guard.

   **This got sharper at 1.5.0.** The vendored copy is from the 6.5.33
   snapshot, which carries bayan **1.4.1** — so it now defines an *older*
   `bayan_json_*` surface and no `bayan_pdf_*` at all. Anything that
   accidentally includes it gets a silently downlevel bundle.
5. ~~**`README.md` is three minor versions stale.**~~ **Fixed in 1.5.0** —
   rewritten against the tree.
6. **`docs/` is still largely scaffold, but less so.** 1.5.0 added the first
   two ADRs (the Flate hooks, and pdf not reusing the json tree) and
   `docs/benchmarks.md`. Still unrecorded: the carve itself, `_compat` aliases,
   the sublib split, yaml-into-json's-tree, and the 1.4.1 `obj_get` non-rename.
   `docs/architecture/` is a README only; `docs/examples/` is a `.gitkeep`.
7. **`docs/development/roadmap.md` M1/M2 are still unfilled template stubs**,
   though the v1.0 criteria checklist is now partly ticked and the PDF and YAML
   items are marked shipped. Benchmarks and a real fuzz harness were two of the
   unticked criteria and are now met.
8. ~~**`CLAUDE.md` Project Identity and Goal are still `TODO`.**~~ **Fixed in 1.5.0.**

## Scripts

- `scripts/consumer-check.sh` — compiles a throwaway consumer against every
  `dist/` bundle from exactly the leaves its `.deps` sidecar declares. Run it
  locally the same way CI does: `./scripts/consumer-check.sh` (workdir defaults
  to the gitignored `build/.consumer-check`).

## Dependencies

Direct (declared in `cyrius.cyml [deps].stdlib`): string, fmt, alloc, io,
vec, str, syscalls, assert, bench, result, fnptr, tagged. The dist bundle
strips includes — consumers must supply these (notably `result`, which is
NOT in cyrius's own stdlib auto-prepend set).

No sibling `[deps.NAME]` entries, so `cyrius deps` writes no `cyrius.lock`
and `cyrius deps --verify` reports "no cyrius.lock found" by design.

## Consumers

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr`. The 6.5.33 snapshot
  still carries **bayan 1.4.1**, so the fold is now two releases behind and the
  next refold is not a no-op: it triples the bundle (5,554 → 14,905 lines) and
  adds 152 public functions. `[lib.pdf]` is a self-contained single-module
  closure if cyrius would rather fold pdf separately.
- **mneme** — the named `bayan_pdf_*` consumer. It ships a hand-rolled writer
  in `src/io_export_pdf.cyr` (443 lines) that this release supersedes; the
  migration keeps mneme's markdown layer and hands the PDF primitives to bayan.
  Two bugs found in that file while reading it are mneme's to fix and are filed
  separately: an unterminated code fence silently discards the rest of a note,
  and PDF export ignores write failures. During the migration window mneme will
  have both files in scope, which is why no bayan helper is named bare
  `_pdf_*` and why CI enforces it.
- Downstream repos using json/toml/csv/base64/bigint/u128 migrate to
  `bayan_*` on re-pin (back-compat aliases bridge the window).

## Next

See [`roadmap.md`](roadmap.md) — `bayan_markdown_*` is the next feature
milestone (driver: the **mneme** port), and it pairs naturally with what just
shipped: a markdown AST plus `bayan_pdf_wrap` is the whole "notes to a
laid-out PDF" story, and it is the reason the PDF flow/layout layer was
deliberately left out of 1.5.0 rather than built against a markdown parser
that does not exist yet.

Known follow-ons for pdf specifically: encrypted documents are detected and
rejected rather than handled (they need the standard security handler, which
is `sigil` territory and would recreate the fold-ordering hazard the Flate
hooks exist to avoid); `LZWDecode` is rejected by name; and there is no
layout/flow API. ganita (math-domain) is the sibling carve; the 6.5.33
snapshot ships it at **1.1.0**.
