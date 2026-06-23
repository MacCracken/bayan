# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).

## Version

**1.0.3** — json value + streaming parsers made reentrant/thread-safe
(2026-06-23, cyrius v6.2.37). Carved from cyrius stdlib at 1.0.0 (2026-06-10).

## Toolchain

- **Cyrius pin**: `6.2.37` (in `cyrius.cyml [package].cyrius`)

## Source

Seven data/big-integer modules carved byte-identical from cyrius stdlib,
public functions prefixed `bayan_`:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/json.cyr`   | 1549 | 62 | `bayan_json_*` |
| `src/u128.cyr`   | 504  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 422  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 365  | 20 | `bayan_u256_*` |
| `src/toml.cyr`   | 353  | 13 | `bayan_toml_*` |
| `src/base64.cyr` | 177  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 97   | 3  | `bayan_csv_*` |

- `src/_compat.cyr` — 149 back-compat aliases (legacy names → `bayan_*`).
- `dist/bayan.cyr` — ~3,640-line bundle (canonical + alias + internal helper
  fns), regenerated via `cyrius distlib`. This is the artifact folded into
  `cyrius/lib/bayan.cyr`.

## Tests

- `tests/bayan.tcyr` — base64 encode/decode + u128 arithmetic + alias parity +
  json value-parser reentrancy (nested parse, ctx path, per-call error
  reporting, trailing-content rejection). 25 asserts, green on 6.2.37.
- `src/main.cyr` — full-bundle compile smoke (exits 42).
- Deep per-module coverage lives in cyrius's `.tcyr` suite (json/toml/csv/
  base64/bigint/u128/cyml).

## Dependencies

Direct (declared in `cyrius.cyml [deps].stdlib`): string, fmt, alloc, io,
vec, str, syscalls, assert, bench, result, fnptr, tagged. The dist bundle
strips includes — consumers must supply these (notably `result`, which is
NOT in cyrius's own stdlib auto-prepend set).

## Consumers

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr` (v6.1.25).
- Downstream repos using json/toml/csv/base64/bigint/u128 migrate to
  `bayan_*` on re-pin (back-compat aliases bridge the window).

## Next

See [`roadmap.md`](roadmap.md). ganita (math-domain) is the sibling carve
(cyrius v6.1.26).
