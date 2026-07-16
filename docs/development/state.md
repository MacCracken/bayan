# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).

## Version

**1.1.1** — json recursion-depth cap at 128 in both parsers (serde_json
wire-parity; parser state 40 → 48 bytes, agnosai's blocker #2) + toolchain
bumped to cyrius v6.4.64 with a full `lib/` re-sync (2026-07-16). Carved
from cyrius stdlib at 1.0.0 (2026-06-10).

## Toolchain

- **Cyrius pin**: `6.4.64` (in `cyrius.cyml [package].cyrius`; bumped
  2026-07-16, `lib/` snapshot re-synced via `cyrius lib sync --full`)

## Source

Seven data/big-integer modules carved byte-identical from cyrius stdlib,
public functions prefixed `bayan_`:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/json.cyr`   | 1584 | 62 | `bayan_json_*` |
| `src/u128.cyr`   | 526  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 420  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 365  | 20 | `bayan_u256_*` |
| `src/toml.cyr`   | 545  | 17 | `bayan_toml_*` |
| `src/base64.cyr` | 177  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 97   | 3  | `bayan_csv_*` |

- `src/_compat.cyr` — 153 back-compat aliases (legacy names → `bayan_*`).
- `dist/bayan.cyr` — ~3,900-line bundle (canonical + alias + internal helper
  fns), regenerated via `cyrius distlib`. This is the artifact folded into
  `cyrius/lib/bayan.cyr`.

## Tests

- `tests/bayan.tcyr` — base64 encode/decode + u128 arithmetic + alias parity +
  json value-parser reentrancy (nested parse, ctx path, per-call error
  reporting, trailing-content rejection) + json streaming-parser callbacks
  (real `&fn` handlers asserting per-event dispatch) + json recursion-depth
  cap (200-deep rejected on both parsers, 100-deep parses, 128/129 boundary,
  alias parity) + toml triple-quoted strings + toml array-value element access
  (bare/quoted/literal-`'`/nested/empty/trailing-comma/multi-line-comment/
  nested-inline-comment + alias parity). 101 asserts, green on 6.4.64.
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
