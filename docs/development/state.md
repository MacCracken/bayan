# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).
> Last refreshed: 2026-07-31.

## Version

**1.4.0** — completes the allocator-threaded (`_a`) JSON value surface:
`obj_set_a`, `build_a`, `build_pretty_a`, `parse_ctx_a`, `parse_buf_a`,
`parse_a`. The eight value *constructors* have had `_a` forms since v5.8.36;
what was missing was the pair cells, the parse and the serializer, so an arena
could cover part of a request and the rest still landed on the no-free global
bump. Filed by **agnosai**, whose per-request arena stopped at the sandhi seam
because of exactly this gap. Also fixes an unchecked `alloc` in the string
parser that only becomes reachable once an arena is in play.

Before that: 1.3.0 renamed the cstr+len parse entries `_str` → `_buf` (the old
names were shadowing their own Str-taking siblings via Cyrius's `X_str`
dispatch); 1.2.1 made float serialization round-trip-correct (Grisu2);
1.2.0 added the `yaml` module. Carved from cyrius stdlib at 1.0.0 (2026-06-10).

## Toolchain

- **Cyrius pin**: `6.5.4` (`cyrius.cyml [package].cyrius`) — bumped from `6.4.68`
  in this release, with `cyrius lib sync --full` run against it.
- **`lib/` matches the pin exactly**: 0 of 99 files differ from
  `~/.cyrius/versions/6.5.4/lib`. Build and test emit no drift or shadow warning.

  `cyrius lib sync --full` alone did not get there — it copied 99 files and left
  five behind (`niyama` 1.0.5, `pam`, `shadow`, `vani` 1.1.1, `yantra` 1.0.0), all
  dated from the 2026-07-16 sync and none of them in bayan's `[deps] stdlib` list.
  They were refreshed from the snapshot directly. Worth knowing for the next bump:
  a green `lib sync --full` is not by itself proof that `lib/` matches the pin —
  compare the trees.
- **Ten dead pre-carve modules were removed from `lib/`** (109 → 99 files):
  `json` `base64` `bigint` `csv` `cyml` `toml` `u128` — this content was carved
  *out* of the cyrius stdlib *into bayan* at 1.0.0 / cyrius 6.1.25, so a stale copy
  in bayan's own `lib/` defined the same symbols as `src/`, which is a
  last-definition-wins hazard waiting for someone to include it. `matrix` and
  `linalg` went to ganita at 6.1.26; `agnosys` is unrelated. None was referenced by
  `src/`, `tests/`, or `cyrius.cyml`. The six `# Usage: include "lib/<mod>.cyr"`
  header lines that still pointed at them were corrected to name
  `lib/bayan.cyr` / `lib/bayan-<profile>.cyr`.

## Source

Eight data/big-integer modules carved byte-identical from cyrius stdlib
(public functions prefixed `bayan_`), plus the greenfield `yaml` module
(1.2.0, written in-repo — parses into json's value tree, so it must sit
after `json.cyr` in bundle order). Regenerated from the tree 2026-07-31:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/json.cyr`   | 1730 | 68 | `bayan_json_*` |
| `src/yaml.cyr`   | 878  | 12 | `bayan_yaml_*` |
| `src/dtoa.cyr`   | 573  | 3  | `bayan_f64_*` |
| `src/toml.cyr`   | 545  | 17 | `bayan_toml_*` |
| `src/u128.cyr`   | 526  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 420  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 365  | 20 | `bayan_u256_*` |
| `src/base64.cyr` | 177  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 97   | 3  | `bayan_csv_*` |

**Allocator-threaded surface: 21 `_a` functions** across the bundle, of which
the JSON value API is now complete end to end — construct (8, since v5.8.36),
mutate (`obj_set_a`, 1.4.0), parse (`parse_a` / `parse_buf_a` / `parse_ctx_a`,
1.4.0) and serialize (`build_a` / `build_pretty_a`, 1.4.0). A consumer can run a
whole parse → mutate → serialize cycle on an arena and measure **0 bytes** of
global-bump growth; the assertion that pins this is mutation-verified.

- `src/_compat.cyr` — 153 back-compat aliases (legacy names → `bayan_*`;
  yaml is new API, no aliases).
- `dist/bayan.cyr` — **5,504**-line bundle (canonical + alias + internal helper
  fns), regenerated via `cyrius distlib` at 1.4.0. This is the artifact folded into
  `cyrius/lib/bayan.cyr`.
- `dist/bayan-<format>.cyr` — per-format sublibs (the sigil/sandhi
  `[lib.<name>]` pattern): json / yaml / toml / cyml / csv / base64 / u128 /
  bigint, each `cyrius distlib <name>`-generated, compile-verified
  self-contained, with a `.deps` stdlib-leaf sidecar (u128 needs none).
  yaml's closure carries json.cyr (shared value tree / parser state).
  Canonical `bayan_*` names only — `_compat` aliases ride the full bundle.

## Tests

- `tests/bayan.tcyr` — base64 encode/decode + u128 arithmetic + alias parity +
  json value-parser reentrancy (nested parse, ctx path, per-call error
  reporting, trailing-content rejection) + json streaming-parser callbacks
  (real `&fn` handlers asserting per-event dispatch) + json recursion-depth
  cap (200-deep rejected on both parsers, 100-deep parses, 128/129 boundary,
  alias parity) + toml triple-quoted strings + toml array-value element access
  (bare/quoted/literal-`'`/nested/empty/trailing-comma/multi-line-comment/
  nested-inline-comment + alias parity) + yaml (scalar typing, quoting,
  comments, nested mappings, block/flow/compact sequences, doc markers,
  frontmatter split, reentrancy, err_pos, block+flow depth caps, and a
  loud-rejection battery for every out-of-subset form).

  **1.4.0 adds an 18-assert block for the `_a` surface**, and it tests the
  contract rather than the symbols: `_a` output is byte-identical to the non-`_a`
  path (compact *and* pretty), 200 parse→obj_set→build cycles through an arena
  grow the global bump by **0 bytes** while the same 200 on the global path leak
  **>100 KB**, an exhausted arena surfaces as a normal parse error instead of a
  write through address 0, `obj_set_a` returns −1 on a null / non-object target,
  and a tree survives `reset_via` + re-parse.

  **Mutation-verified**: reverting one `alloc_via(a, …)` to `alloc(…)` in the
  string parser turns the zero-growth assertion into `got 35200, expected 0`.
  A guard no test can reach is a guard that silently rots.

  **292 asserts, green** on cycc 6.5.4 (was 274 at 1.3.0).
- `src/main.cyr` — full-bundle compile smoke (exits 42).
- Deep per-module coverage lives in cyrius's `.tcyr` suite (json/toml/csv/
  base64/bigint/u128/cyml).

## Dependencies

Direct (declared in `cyrius.cyml [deps].stdlib`): string, fmt, alloc, io,
vec, str, syscalls, assert, bench, result, fnptr, tagged. The dist bundle
strips includes — consumers must supply these (notably `result`, which is
NOT in cyrius's own stdlib auto-prepend set).

## Consumers

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr` (fold refreshed
  2026-07-06 with the 1.1.0 bundle; cyrius now at v6.4.64).
- Downstream repos using json/toml/csv/base64/bigint/u128 migrate to
  `bayan_*` on re-pin (back-compat aliases bridge the window).

## Next

See [`roadmap.md`](roadmap.md). ganita (math-domain) is the sibling carve
(v1.0.3, pins cyrius 6.4.26).
