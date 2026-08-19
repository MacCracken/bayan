# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).
> Last refreshed: 2026-08-19.

## Version

**1.4.2** — toolchain + CI. Cyrius pin `6.5.16` → `6.5.28`, `lib/` re-synced to
an exact match, `dist/` regenerated. No behavioural change — the compiled smoke
binary is byte-identical across every source edit. `src/` now builds with **zero
compiler warnings** (three `: i64`-declared toml helpers that return `Str` are
annotated) and lints clean. CI went from 4 steps to a full gate, including three
distribution checks; the new consumer check immediately found two sublib `.deps`
sidecars that under-declare their dependencies.

Before that: 1.4.1 armed the Str→cstring diagnostic on
`bayan_json_v_obj_get` (the getter takes a C-string while `obj_set` stores a
`Str`, so passing a `Str` to the getter made `strlen` walk the 16-byte header
and return a **silent "not found"**) and added the symmetric
`bayan_json_v_obj_get_by_str`; 1.4.0 completed the allocator-threaded (`_a`)
JSON value surface — pair cells, parse, and serializer — so an arena can cover
a whole request instead of stopping at the sandhi seam; 1.3.0 renamed the
cstr+len parse entries `_str` → `_buf`; 1.2.1 made float serialization
round-trip-correct (Grisu2); 1.2.0 added the `yaml` module. Carved from cyrius
stdlib at 1.0.0 (2026-06-10).

## Toolchain

- **Cyrius pin**: `6.5.28` (`cyrius.cyml [package].cyrius`). `cyrius version`
  reports `manifest-pin: 6.5.28` with no drift line; build and test emit
  neither the pin-drift nor the shadow-lib warning.
- **`lib/` matches the pin exactly**: `diff -rq lib/ ~/.cyrius/versions/6.5.28/lib/`
  is empty — 108 files, 0 differ.

  **Verify by comparing the trees, not by trusting the sync's exit code.** At
  1.4.0 a green `cyrius lib sync --full` still left five files behind. This time
  it did land clean, but the check is the tree diff either way.
- **`lib/` grew 99 → 108 files** at this pin: `unicode/` (7 files — `_decode`,
  `categories`, `casefold`, `normalize` + generated data tables),
  `async_macos.cyr`, `thread_macos.cyr`. None is in `[deps].stdlib`, so none is
  auto-prepended; they ride along because `--full` vendors the whole snapshot.
- **Pin history**: 6.4.68 → 6.5.4 (1.4.0) → 6.5.16 (commit `97a3476`,
  2026-08-10, **undocumented** — no CHANGELOG entry, no state refresh) →
  6.5.28 (1.4.2).
- **Caveat on the local snapshot.** `lib/` matches the **released** 6.5.28
  tarball exactly (verified by extracting it). `~/.cyrius/versions/6.5.28/lib`
  on a machine that also develops cyrius may not: its `freelist.cyr` was edited
  in place on 2026-08-19 with `.29` REDZONE/QUARANTINE work. A local
  `diff -rq lib ~/.cyrius/versions/6.5.28/lib` can therefore show drift that CI
  will not — compare against the release tarball to settle it.

## Source

Eight data/big-integer modules carved byte-identical from cyrius stdlib
(public functions prefixed `bayan_`), plus the greenfield `yaml` module
(1.2.0, written in-repo — parses into json's value tree, so it must sit
after `json.cyr` in bundle order). Regenerated from the tree 2026-08-19:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
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
- `dist/bayan.cyr` — **5,554**-line bundle (canonical + alias + internal helper
  fns), regenerated via `cyrius distlib` at 1.4.2. This is the artifact folded
  into `cyrius/lib/bayan.cyr`.
- `dist/bayan-<format>.cyr` — per-format sublibs (the sigil/sandhi
  `[lib.<name>]` pattern), each `cyrius distlib <name>`-generated,
  compile-verified self-contained, with a `.deps` stdlib-leaf sidecar
  (u128 has none under released 6.5.28 — `.29`'s distlib writes an empty one).
  Canonical `bayan_*` names only — `_compat` aliases ride the full bundle.
  Two sidecars under-declare; see Known gaps 2.

  | Sublib | Lines | Stdlib leaves |
  |---|---|---|
  | `bayan-yaml`   | 3231 | 9 (carries `json.cyr` — shared value tree / parser state) |
  | `bayan-json`   | 2350 | 9 |
  | `bayan-toml`   | 555  | 5 |
  | `bayan-u128`   | 534  | 0 |
  | `bayan-cyml`   | 430  | 4 |
  | `bayan-bigint` | 375  | 2 |
  | `bayan-base64` | 187  | 2 |
  | `bayan-csv`    | 107  | 3 |

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

  **292 asserts, green** on cycc 6.5.28 (unchanged since 1.4.0).
- `src/main.cyr` — full-bundle compile smoke (exits 42).
- Deep per-module coverage lives in cyrius's `.tcyr` suite (json/toml/csv/
  base64/bigint/u128/cyml).

### Coverage

`cyrius coverage` — **102/335 fns (30%)**, 9/12 files referenced. Reference
coverage is a floor, not a correctness proof, and the deep suite still lives
upstream in cyrius — but three carved modules are referenced **nowhere** in
bayan's own tests:

| Module | Referenced |
|---|---|
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

Gates: pin-drift · version consistency (VERSION / manifest / CHANGELOG / all 9
dist headers) · `lib/` vs snapshot tree diff · format (src **and** tests) ·
lint (0 warnings, 0 deferrals) · vet · build with 0 warnings · smoke exits 42 ·
test · fuzz · bench · `coverage --min 30` · `distlib --all --check` ·
regeneration leaves no tree diff · consumer-check.

## Known gaps

Surfaced by the 2026-08-19 state review. Items 1 and 8 of the original list
were fixed in 1.4.2 (toml warnings, lint); these remain, each its own change.

1. **`tests/bayan.fcyr` and `tests/bayan.bcyr` are `cyrius init` scaffolds.**
   The fuzz harness feeds a 4-byte literal into a body that returns
   immediately; the bench measures a no-op (`noop: 2ns avg`). Both report PASS
   — a false green on two v1.0 criteria, and `docs/benchmarks.md` does not
   exist. CI now runs both, so the gates are vacuous until the harnesses are
   real. Parsers reading untrusted input are exactly the shape fuzzing is for.
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
5. **`README.md` is three minor versions stale** — "Status **1.0.0** — Seven
   modules, ~3,350 lines, 149 public functions", no `yaml`, no `dtoa`, no
   sublibs, no `_a` surface.
6. **`docs/` is largely scaffold.** `docs/adr/` holds only a README and the
   template — no ADR records the decisions that shaped the repo (the carve
   itself, `_compat` aliases, the sublib split, yaml-into-json's-tree, the
   1.4.1 `obj_get` non-rename). `docs/architecture/` is a README only;
   `docs/examples/` is a `.gitkeep`.
7. **`docs/development/roadmap.md` M1/M2 are unfilled template stubs**, as is
   the "Out of scope" list, while the v1.0 criteria checklist is entirely
   unticked — including items that are in fact met (CHANGELOG complete from
   1.0.0; a downstream consumer green).
8. **`CLAUDE.md` Project Identity and Goal are still `TODO`.**

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

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr`. The 6.5.28 snapshot
  carries **bayan 1.4.1**; 1.4.2 is a version-stamp-only bundle, so the refold
  can ride the next cyrius release with no behavioural change.
- Downstream repos using json/toml/csv/base64/bigint/u128 migrate to
  `bayan_*` on re-pin (back-compat aliases bridge the window).

## Next

See [`roadmap.md`](roadmap.md) — `bayan_markdown_*` is the next feature
milestone (driver: the **mneme** port). ganita (math-domain) is the sibling
carve; the 6.5.28 snapshot ships it at **1.1.0**.
