# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).

## Version

**1.0.0** — initial carve out of cyrius stdlib (2026-06-10, cyrius v6.1.25).

## Toolchain

- **Cyrius pin**: `6.1.24` (in `cyrius.cyml [package].cyrius`)

## Source

Seven data/big-integer modules carved byte-identical from cyrius stdlib,
public functions prefixed `bayan_`:

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/json.cyr`   | 1434 | 57 | `bayan_json_*` |
| `src/u128.cyr`   | 504  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 422  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 365  | 20 | `bayan_u256_*` |
| `src/toml.cyr`   | 353  | 13 | `bayan_toml_*` |
| `src/base64.cyr` | 177  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 97   | 3  | `bayan_csv_*` |

- `src/_compat.cyr` — 149 back-compat aliases (legacy names → `bayan_*`).
- `dist/bayan.cyr` — 3,500-line bundle (149 canonical + 149 alias + 46
  internal helper fns), regenerated via `cyrius distlib`. This is the
  artifact folded into `cyrius/lib/bayan.cyr`.

## Tests

- `tests/bayan.tcyr` — base64 encode/decode + u128 arithmetic + alias parity.
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
