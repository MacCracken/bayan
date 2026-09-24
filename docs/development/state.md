# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).
> Last refreshed: 2026-09-23.

## Version

**1.5.7** — **the f64 parser is correctly rounded for every input.** prakash
reported that ~2 in 10⁵ doubles did not survive `bayan_f64_to_json →
bayan_f64_from_json`
([2026-09-22](issues/archived/2026-09-22-prakash-f64-parse-double-rounding-at-midpoint.md)).
The DiyFp tier rounded its 64 approximate bits a second time and read
`low == halfway` as a real tie. Measured against Python, the parser also got
~1 in 10³ arbitrary decimals wrong, and three defect classes the report did not
cover turned up: the 20th+ digit discarded, `[2⁻¹⁰⁷⁵, 2⁻¹⁰⁷⁴)` flushed to 0,
and the exact overflow tie read as DBL_MAX. Now **0 wrong of 884,093**
oracle-checked inputs.

The shape of the fix is recorded in
[ADR-0003](../adr/0003-f64-parse-exact-fallback-not-eisel-lemire.md). Tier 2
answers only outside an explicit ±16 error window (derived bound < 5.01,
measured maximum 3.25). Everything else goes to an exact decimal tier (Go
strconv's `decimal`, on the caller's stack). **Fixing only `low == halfway`
would have left 936 wrong answers** in a 390,000-input near-midpoint sample.

**Two lessons worth keeping.**

- **The fixture was the right kind and the wrong size, so volume was not the
  fix.** `f64.vec` has a Python oracle and 328 lines, which gives it about a
  0.7% chance of holding one failure at a 2×10⁻⁵ rate. `f64parse.vec` has
  7,736 lines aimed at midpoints, and the old parser gets 355 of them wrong.
- **Measuring the report found more than the report.** Three of the four defect
  classes fixed here were not in it. They surfaced only because the parser was
  measured against an oracle across input classes (subnormal seam, > 19 digits,
  overflow seam), rather than only on the reported repro.

Toolchain **6.6.2 → 6.6.6** in the same release. The one lint failure was the
`pdf.cyr:6126` deferral the roadmap predicted. `tests/pdf_flate.tcyr` is green,
and it was green on the released 6.6.0 too: 1.5.5's RED came from a
pre-release snapshot (Known gaps #2).

Before that: **1.5.6** — toolchain 6.6.0 → 6.6.2, no source change. **1.5.5** —
migrated to the cyrius 6.6.0 `Result`/`Option`/`Either` value form: a payload
variant is a register pair, so a consumer receiving one of the three `_r`
loaders' Results must bind both halves. The dangerous shape was the
hand-rolled `load64(r + 8)` payload read, which still compiles and now
dereferences a plain value. All six were found by grep, not by the build.

Before that: **1.5.4** — **the seven structural TOML gaps, closed.** 1.5.3 fixed what a
value *decodes to*; 1.5.4 fixes where a pair *lands*: quoted keys, dotted keys
naming a table, inline tables, empty tables, duplicate keys, the value-kind
record, and trimmed header names. `cyml`'s last two fixed read caps went with
them, so there are no fixed read caps left in `src/`.

Four of those changes move data — the root table is always `sections[0]`, an
empty table is emitted, a dotted key names a table, and a duplicate resolves to
the LAST value — and the pair struct is 24 bytes rather than 16. The CHANGELOG
leads with a banner.

**The scoping is the part worth keeping.** 1.5.3 filed these seven as "wants its
own release" without asking, which was a scoping decision presented as a
technical one and wrong twice over: the report was a repair request, and the
call belonged to the maintainer. The four decisions here that move data or
change a struct were put to the maintainer before any of them was written.

Verification: 918 asserts (from 839), 1,494 oracle vectors (from 1,476, now
including 18 STRUCTURAL records that check where a pair landed rather than what
it decoded to), 466/466 reference coverage, and ten mutations — one per gap fix
— each confirmed to turn the suite red.

Before that: **1.5.3** — **the TOML parser was returning wrong values, and had
been since 1.0.0.** mneme reported it
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

- **Cyrius pin**: `6.6.6`, bumped at 1.5.7 from `6.6.2` (`cyrius.cyml
  [package].cyrius`). `cyrius version` reports `manifest-pin: 6.6.6` with no
  drift line; build and test emit neither the pin-drift nor the shadow-lib
  warning. The only source change the bump needed was the `src/pdf.cyr:6126`
  lint pointer (6.6.5's cyrlint folds case).
- **`lib/` matches the pin exactly, and the pin matches the RELEASE**:
  `diff -rq lib ~/.cyrius/versions/6.6.6/lib`: 111 files, 0 differ, after
  `cyrius deps` then `cyrius lib sync --full` (`deps` alone refreshed only the 9
  declared leaves and left 25 files stale). The snapshot's `lib/` is byte-identical
  to the 6.6.6 release tarball's. 40 files changed at this bump, plus one new
  file (`alloc_cx.cyr`).

  This settles the 1.5.5 caveat. That bump was measured against a pre-release
  6.6.0 snapshot, and the `pdf_flate` RED it recorded was the snapshot's, not
  the release's (Known gaps #2).

  `bin/` still differs from the release in the same way it has since 6.5.36.
  Of the release's entries, `ci.sh` is **absent** locally and `cybs`
  **differs**, and the local tree carries four the release does not
  (`cycc-native-aarch64`, `cycc_cx`, `cyrius-repl.sh`, `dlopen-helper.c`).
  `cycc`, `cyrfmt`, `cyrlint` and the `cyrius` wrapper are identical, measured
  by `diff -rq` against the tarball. `dist/` was regenerated with the release
  toolchain in an isolated `CYRIUS_HOME` regardless, and the local toolchain
  produces byte-identical bundles.

  **Verify by comparing the trees, not by trusting the sync's exit code.** At
  1.4.0 a green `cyrius lib sync --full` still left five files behind.
- **Pin history**: 6.4.68 → 6.5.4 (1.4.0) → 6.5.16 (commit `97a3476`,
  2026-08-10, **undocumented**) → 6.5.28 (1.4.2) → 6.5.33 (1.5.0) → 6.5.36
  (1.5.3) → 6.6.0 (1.5.5) → 6.6.2 (1.5.6) → 6.6.6 (1.5.7).
- **Caveat on the local snapshot — still live.** `~/.cyrius/versions/<pin>/lib`
  on a machine that also develops cyrius can carry unreleased in-flight edits at
  the same version number: at 6.5.28 its `freelist.cyr` had been edited in place
  with `.29` work. Settle it against the **release tarball**, always.

## Source

Eight data/big-integer modules carved byte-identical from cyrius stdlib
(public functions prefixed `bayan_`), plus two greenfield modules written
in-repo: `yaml` (1.2.0 — parses into json's value tree, so it must sit after
`json.cyr` in bundle order) and `pdf` (1.5.0 — cross-dep-free, so its position
is convention rather than necessity). Re-measured from the tree 2026-09-23:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/pdf.cyr`    | 9528 | 152 | `bayan_pdf_*` |
| `src/json.cyr`   | 1922 | 69 | `bayan_json_*` |
| `src/toml.cyr`   | 1632 | 33 | `bayan_toml_*` |
| `src/yaml.cyr`   | 899  | 12 | `bayan_yaml_*` |
| `src/dtoa.cyr`   | 889  | 3  | `bayan_f64_*` |
| `src/u128.cyr`   | 567  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 576  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 450  | 20 | `bayan_u256_*` |
| `src/base64.cyr` | 214  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 149  | 3  | `bayan_csv_*` |

`toml` has gone 17 -> 21 -> **33** public functions across 1.5.3 and 1.5.4,
and roughly tripled in size. 1.5.3 added the escape decoder, the literal-string
parser and the rewritten multi-line scanner; 1.5.4 added the key-path scanner,
the extracted value dispatch, the inline-table accessor and the value-kind
record. A good deal of the growth is comment recording *why*, because most of
the defects both releases fixed were invisible to every test that existed.

`dtoa` grew 573 -> **889** lines at 1.5.7 with no new public function: the
exact decimal tier (`_d_dec_*`, `_d_exact`), the error-window rounding, and
the derivation of the window in the comment that sets it.

**Allocator-threaded surface: 51 public `_a` functions** across the bundle —
pdf 26, json 15, toml 7, cyml 2, yaml 1. (Measured. The "21" this file carried
from 1.4.0 predated pdf's entire `_a` surface and was stale for three releases;
that is the hazard of writing a count into a file nobody re-measures.) The JSON
value API is complete end to end — construct, mutate, parse and serialize. A consumer can run a whole parse → mutate → serialize cycle on an
arena and measure **0 bytes** of global-bump growth; the assertion that pins
this is mutation-verified.

- `src/_compat.cyr` — 153 back-compat aliases (legacy names → `bayan_*`;
  yaml and the 1.5.3 toml escape helpers are new API, no aliases).
- `dist/bayan.cyr` — **17,026**-line bundle, regenerated via `cyrius distlib`
  at 1.5.7 with the **release** 6.6.6 toolchain. This is the artifact folded into
  `cyrius/lib/bayan.cyr`. `src/pdf.cyr` is 9,528 of those lines, so the fold's cost to
  cyrius is dominated by one module; `[lib.pdf]` is a self-contained
  single-module closure if cyrius would rather fold it separately.
- `dist/bayan-<format>.cyr` — per-format sublibs, each `cyrius distlib <name>`-
  generated and compile-verified self-contained, with a `.deps` stdlib-leaf
  sidecar. Canonical `bayan_*` names only. Every sidecar is complete:
  `scripts/consumer-check.sh` builds all 10 bundles from their declared leaves
  alone, and goes red when a needed one is deleted (checked at 1.5.7).

  | Sublib | Lines | Stdlib leaves |
  |---|---|---|
  | `bayan-pdf`    | 9536 | 8 (single-module closure — no `json.cyr`, no `dtoa.cyr`) |
  | `bayan-yaml`   | 3724 | 9 (carries `json.cyr` — shared value tree / parser state) |
  | `bayan-json`   | 2822 | 9 |
  | `bayan-toml`   | 1640 | 7 |
  | `bayan-cyml`   | 584  | 7 |
  | `bayan-u128`   | 575  | 2 |
  | `bayan-bigint` | 458  | 2 |
  | `bayan-base64` | 222  | 2 |
  | `bayan-csv`    | 157  | 3 |

  `bayan-toml` and `bayan-cyml` stopped listing `fmt` at 1.5.7, and that is
  correct: cyrius 6.6.6's `lib/io.cyr` includes `fmt.cyr` itself, so the `io`
  leaf brings it. The json/yaml/pdf sidecars dropped `tagged` at 1.5.6 for the
  same kind of reason.

## Tests

- `tests/bayan.tcyr` — **962 asserts, green**. base64, u128, alias parity, the
  json value/streaming parsers and their depth caps, toml, yaml, the 1.3.0
  Str-entry dispatch regression, the 1.4.0 `_a` block, the 1.5.0 pdf block, the
  1.5.1 sweep guards, the 1.5.2 coverage additions.

  **1.5.7 adds the f64 parse group** (+43): the 27 vectors from the prakash
  issue, each checked as the literal string and through the emitter, plus
  pins for the three defect classes the measurement found and two through
  the JSON decoder. **37 of the 43 are red on the old parser**, and the other
  6 are boundary controls that bracket a defect from the side the old parser
  already got right.

  **1.5.4 adds seven more groups** — quoted keys, dotted keys, inline tables,
  empty tables, duplicates, value kinds, header names, plus one for cyml's
  removed read caps. **1.5.3 added seven toml groups** (up from 749 asserts at 1.5.2): basic-string
  escapes, single-line literal strings, multi-line conformance, array-element
  escape rules, the public escape/unescape helpers, and the value arms
  (comments, CRLF, keyless lines, document-swallowing). Plus a **truncation
  property test**: eight documents cut at every length, asserting no key, value
  or section name reaches past its source buffer — the guard for the
  memory-safety bug the fix itself introduced.

  **Mutation-verified, both releases.** Ten mutations at 1.5.3 and ten more at
  1.5.4, one per fix, each turns the suite red — including two run against the
  structural vectors specifically, to check the new records bite rather than
  merely run. At 1.5.3 two mutations did not fail at first: the delimiter-run
  rule and the escaped-quote rule in the multi-line scan **mask each other** on
  the reported input, so the test written for the filed repro passed with
  either one removed. A test that cannot fail is a test that has stopped being
  a test.
- `tests/vectors.tcyr` — **oracle-driven, expected values from Python**:
  12,334 u128 checks, 656 f64 round-trip checks, **7,736 f64 parse vectors**
  (`f64parse.vec`, new at 1.5.7), and **1,494 TOML vectors** from `tomllib`
  (1,476 string + **18 structural**, the latter new at 1.5.4). A string vector
  can only see what a value decodes to; a structural one carries a table name
  and a key and checks WHERE the pair landed, which is what quoted keys, dotted
  keys and header trimming are all about.

  `f64parse.vec` is aimed, not sampled. Its lines are midpoints cut to 16–19
  digits, full-length exact ties ±1 past their last digit, inputs past the
  exact tier's 800-digit buffer, and the subnormal and overflow seams. The
  pre-1.5.7 parser gets 355 of them wrong, while `f64.vec`'s 328 shortest-repr
  strings stayed green on it throughout.

  Duplicate keys are deliberately absent: `tomllib` rejects the document
  outright, so there is no oracle answer and last-wins is bayan policy, pinned
  by hand where the reasoning sits next to the assertion. Kept in its own file so machine-generated checks do
  not swamp the hand-written assertion counts; **13 asserts**, green.
  Regenerate with `scripts/gen-numeric-vectors.py` and
  `scripts/gen-toml-vectors.py`; CI requires every regenerated file
  (`u128.vec`, `f64.vec`, `f64parse.vec`, `strings.vec`) to be byte-identical.
- `tests/pdf_flate.tcyr` — the compression path, isolated because it is the
  only test that pulls in `lib/sankoch.cyr`. **19 asserts, green.**
- `tests/pdf_fixture.cyr` — writes a representative document for CI to run
  through `scripts/pdfcheck.py`. The writer's real gate: the assertions cannot
  see a byte-accounting bug, and an independent strict parser can.
- `tests/bayan.fcyr` — a real fuzz harness. **671 inputs, 219 of which still
  parse, 269 page walks** — re-measured at 1.5.3 by instrumenting a copy and
  running it. The 576/183/245 this file carried since 1.5.0 was stale on all
  three counts; `cyrius fuzz` prints only `fuzz: ok`, so nothing in the tree
  reports these numbers and nothing would have caught the drift. Note honestly
  what it did NOT catch: the `/Length` overflow that segfaulted the reader
  survived it, because byte-flipping a corpus never produces a near-i64-max
  integer.
- `tests/dtoa.fcyr` — **new at 1.5.7**, the f64 parser at a volume no fixture
  holds. 2×10⁶ `to_json → parse` round-trips at the prakash report's seed
  (uniform finite doubles; |x| ≈ 1e-16..1e16), plus 200,000 random decimals
  where the tiered parser must agree with the exact tier alone. That checks
  every tier-2 answer against an independent algorithm without Python. The
  old parser fails 31 of the round-trips. ~8 s, most of it the emitter.
- `tests/bayan.bcyr` — real benchmarks, including one f64-parse row per tier
  (1.5.7). Results in [`benchmarks.md`](../benchmarks.md).
- `src/main.cyr` — full-bundle compile smoke (exits 42).

### Coverage

`cyrius coverage` — **465/465 fns (100%)**, 13/13 files, gated at `--min 100`
(re-measured at 1.5.7; 1.5.7 adds no public function, so the tier-3 helpers are
covered by the oracle and fuzz layers, not by this count).

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

1. ~~**The TOML parser is a documented SUBSET, and seven structural gaps
   degrade silently.**~~ **Fixed in 1.5.4** — all seven.
   [2026-08-28](issues/2026-08-28-toml-structural-subset-gaps.md) is resolved.

   What remains of the subset is narrower and stated in `src/toml.cyr`'s
   header: a dotted key whose QUOTED segment contains a literal dot
   (`a."b.c".d`) joins into a name indistinguishable from `a.b.c.d`, and a
   `[[array-of-tables]]` under a dotted parent is not merged with a same-named
   sibling. Both are edge cases with no known consumer, and both are recorded
   rather than assumed away.

2. ~~**`tests/pdf_flate.tcyr` is RED (16/19) on every cycc ≥ 6.5.57.**~~
   **Green (19/19) on the released 6.6.0 and every pin since**, re-measured on
   6.6.2 and 6.6.6 at 1.5.7. The diagnosis 1.5.5 recorded was right: 6.5.57's
   assignment-path aggregate copy wrote a `Str`'s two slots over a one-slot
   handle local, which smashed the page dictionary pointer at
   `src/pdf.cyr:8924`. The fix shipped in the **released** cyrius 6.6.0 (its
   CHANGELOG: "A SILENT MISCOMPILE THAT SHIPPED IN v6.5.57 AND WAS LIVE FOR
   SEVENTEEN RELEASES"). 1.5.5 recorded RED because it measured a pre-release
   6.6.0 snapshot, which is the local-snapshot caveat under Toolchain doing its job.

   It was never worked around in `src/`, so there was nothing to back out.

3. ~~**Two sublib `.deps` sidecars under-declare.**~~ **Fixed upstream in cyrius
   6.6.0**, verified at 1.5.5. `cyrius distlib --all` now closes the transitive
   set (`sidecar: re-added 1 leaf(s) the inference missed (compile-verified)`)
   and both `bayan-toml` and `bayan-cyml` declare `fmt`. `consumer-check.sh`
   reported both as `FIXED` — its known-bad list fails when a listed bundle
   starts passing, which is how this surfaced — so `EXPECTED_FAIL` is now empty
   and the issue is archived:
   [2026-08-19](issues/archived/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md).

   1.5.7 note: at cyrius 6.6.6 neither sidecar lists `fmt`, correctly, because
   `lib/io.cyr` now includes it. The consumer gate was re-checked to go red
   when a needed leaf is deleted, so this is not a gate gone quiet.

4. **`lib/bayan.cyr` is bayan's own fold vendored back into bayan's own
   `lib/`.** Nothing includes it, so it is inert — but it defines the same
   symbols as `src/`, the exact last-definition-wins hazard the ten dead
   pre-carve modules were removed for at 1.4.0. `lib sync --full` re-adds it on
   every bump, so deleting it is not durable; the durable fix is upstream (a
   `lib sync` self-exclusion) or a build-time guard.

   At 1.5.7 the 6.6.6 snapshot carries bayan **1.5.6**, one release behind. It
   is fixed in toml, but it is the `bayan_f64_parse` with **all four f64
   misrounding classes** this release fixes. An accidental include would bring
   the misrounding back with no warning beyond the duplicate-definition ones.
5. **`docs/` is still largely scaffold, but less so.** 1.5.0 added the first two
   ADRs and `docs/benchmarks.md`. Still unrecorded: the carve itself, `_compat`
   aliases, the sublib split, yaml-into-json's-tree, the 1.4.1 `obj_get`
   non-rename, and now the 1.5.3 decision to decode in the parser rather than
   in an accessor — which is the best ADR candidate on the list, because the
   reasoning generalises to yaml and cyml.
6. **`docs/development/roadmap.md` M1/M2 are still unfilled template stubs.**
7. **The two flat lookup APIs disagree about their key type.**
   `bayan_json_get(pairs, key)` compares with `str_eq` and needs a **`Str`**;
   `bayan_toml_get(pairs, key)` compares with `str_eq_cstr` and needs a
   **cstring**. Passing the wrong one yields a silent "not found". 1.5.1
   corrected the wrong doc claim on `bayan_toml_get`; 1.5.3 found the identical
   wrong claim still standing on `bayan_toml_get_array`, and the same
   undocumented trap on `bayan_toml_get_sections`. Both are now stated.
   Reconciling the signatures is still a breaking change and wants its own
   release.
8. **The 1.4.1 Str→cstring diagnostic misses the inline form.**
   `bayan_json_v_obj_get(o, str_from("k"))` — the spelling in the filed
   issue's own reproduction — compiles with zero warnings. The `: cstring`
   annotation fires only when the argument is a named `Str`-typed local. And the
   symptom has changed since filing: it no longer segfaults, it returns a silent
   0, which defers the fault to whatever the caller does with it. Annotated on
   [2026-08-04](issues/2026-08-04-agnosai-json-obj-get-takes-cstr-while-obj-set-takes-str.md).
   **Re-measured at 1.5.7 / cyrius 6.6.6: unchanged.** 6.6.6 reworked the
   `: cstring` gate (non-zero integer literals are now refused), and the inline
   form still compiles clean and returns 0.
9. ~~**`src/cyml.cyr` carries the project's two remaining fixed read caps.**~~
   **Both removed in 1.5.4** — `bayan_cyml_parse_file_r` and
   `_cyml_read_file_trimmed` slurp into a growing `str_builder`, a mid-file read
   ERROR is no longer folded into clean EOF, and an empty file is a legal empty
   document rather than `Err`. **There are no fixed read caps left in `src/`**
   — and that sentence has been wrong twice in this file, so here is how it was
   checked: `grep -rn '262144' src/` and `grep -n 'var buf\[' src/*.cyr`, both
   re-run at 1.5.4.

   What remains in cyml: three unchecked allocations in `bayan_cyml_parse`
   fault under exhaustion rather than returning 0. Documented in the module,
   not fixed.

   *A 1.5.3 draft called the 256 KiB one "the last fixed cap in the project" —
   in the release whose CHANGELOG says each doc fix "was verified against the
   code it documents". It was not; an adversarial review found the 4 KiB one
   173 lines above it. Recorded because the failure is the exact one this file
   keeps warning about.*

10. **`src/csv.cyr` is an RFC 4180 subset**, not RFC 4180: a trailing empty
   field is not emitted (`a,` parses to one field where the RFC has two, so a
   round trip loses a column), records are LF-terminated where the RFC says
   CRLF, and CR does not trigger quoting. Documented at 1.5.3, not fixed.

## Scripts

- `scripts/consumer-check.sh` — compiles a throwaway consumer against every
  `dist/` bundle from exactly the leaves its `.deps` sidecar declares.
- `scripts/gen-numeric-vectors.py` — u128 + f64 vectors from Python, and at
  1.5.7 `f64parse.vec` (the aimed parse vectors). The latter uses its own
  `random.Random`, so adding it left the other two byte-identical.
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

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr`. The 6.6.6 snapshot
  carries **1.5.6**, so the next refold carries the correctly rounded f64
  parser. Every cyrius-internal JSON/YAML float decode goes through it.
- **prakash** (optics; filed the 1.5.7 issue). ⚠ **Action on re-pin:**
  `tests/hardening.tcyr` pins `1.621274542797433e-9` → `0x3E1BDA70DB50D1A0`,
  the WRONG +1 ULP value, so that the first `cyrius deps` vendoring 1.5.7
  turns it red, as designed. Delete that assertion and the `src/serialize.cyr`
  caveat that a float field is not guaranteed to round-trip bit-exactly.
- **mneme** — the named `bayan_pdf_*` consumer, and the filer of the 1.5.3
  issue. ⚠ **`_cfg_toml_unesc` in `src/core_config.cyr` must be removed on
  re-pin, or mneme will double-decode**; its `tests/core_config.tcyr` has
  assertions written to fail loudly at that moment. `_cfg_toml_esc` can go too
  — `bayan_toml_escape` replaces it. **1.5.4 adds a second thing to check**:
  mneme's config uses `[[vault]]` tables, and an empty one is now EMITTED
  rather than dropped, so any index-based walk over `bayan_toml_get_sections`
  results should be re-read. That change is in the safe direction — it stops a
  vault entry with no fields from shifting every later index — but it is a
  change. Separately, mneme still ships a hand-rolled
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

Two things the TOML work argues should come first, or at least alongside:

- **Escape handling in `yaml.cyr` and `cyml.cyr`.** The mneme issue noted both
  also have no unescape. That was true and is still true: 1.5.3 and 1.5.4 fixed
  only the module that was reported. The reasoning that forced the fix into the
  parser rather than into an accessor — only the parser knows which quote
  produced the string — applies unchanged to both, and neither has been
  measured against an oracle the way toml now has.
- **A tagged-tree TOML parser** (`bayan_toml_v_parse` into json's existing
  value tree, the way yaml already does). Less urgent than it was: 1.5.4 gave
  dotted keys and inline tables real answers inside the flat model. It is still
  the right shape for the surface, and it is the answer to Known gap 6 (the two
  flat lookup APIs disagreeing about their key type).

Known follow-ons for pdf: encrypted documents are detected and rejected rather
than handled; `LZWDecode` is rejected by name; there is no layout/flow API.
ganita (math-domain) is the sibling carve; the 6.6.6 snapshot ships it at
**1.2.6**.
