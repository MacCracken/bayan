# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
