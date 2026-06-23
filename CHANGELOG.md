# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
