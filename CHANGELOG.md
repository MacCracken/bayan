# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.1.1] — 2026-07-16

### Changed

- **Toolchain: cyrius pin bumped 6.4.10 → 6.4.64.** `cyrius lib sync --full`
  re-synced the vendored `lib/` snapshot (99 files — sakshi/niyama/sigil/
  sandhi/yukti/patra/vani/mabda/sankoch had drifted behind their pins). Full
  suite green on 6.4.64: 86/86 asserts + full-bundle compile smoke.

### Fixed

- **json: parsers now cap recursion depth at 128 (serde_json parity).** Neither
  the value parser (`_jp_parse_value`) nor the streaming parser
  (`_js_parse_value`) bounded its descent, so a deeply nested document
  (`[[[[…` — 2 bytes per level) recursed once per level until the calling
  thread's stack was exhausted — an untrusted-input DoS, and a **parity
  regression** vs the Rust originals, which inherit serde_json's default
  128-level limit. The per-call parser state grew one slot
  (`_JP_STATE_SIZE` 40 → 48, `depth@+40`, zeroed in `_jp_state_init`); both
  descents increment it on entering an array/object branch, decrement on exit,
  and past 128 (`_JP_MAX_DEPTH`) fail through the existing per-call error path
  with `"nesting too deep"` — exactly like any other parse error (value path:
  `bayan_json_state_error()` / mirrored `bayan_json_last_error()`; stream
  path: `JS_EV_ERROR` + the same mirror). 128 open containers still parse;
  the 129th fails. `bayan_json_parse_state_size()` already reports the state
  size, so callers reserving via it are transparent; the documented stack
  pattern is now `var ps[48]`. Reported by agnosai (untrusted HTTP bodies on
  its server surface — blocker #2). See
  `docs/development/issues/2026-07-16-agnosai-json-no-recursion-depth-cap.md`.
  Covered by a new `tests/bayan.tcyr` group (200-deep rejected on both
  parsers, 100-deep parses, exact 128/129 boundary, legacy-entry mirror,
  `_compat` alias parity); suite 86 → 101 asserts.

## [1.1.0] — 2026-07-06

### Added

- **toml: array VALUE element access.** `bayan_toml_parse` has always captured
  an array value (`key = [a, b, c]`) verbatim as one raw bracketed `Str` but
  gave callers no way to reach its elements short of hand-rolling a comma
  splitter. Four new helpers decompose that raw value on demand:
  `bayan_toml_array_parse` (and its allocator-threading `_a` variant) returns a
  vec of top-level element `Str`s; `bayan_toml_is_array` reports whether a value
  is a `[...]` array; `bayan_toml_get_array` is the `get` + `parse` convenience
  (returns `0` for an absent key, else a possibly-empty vec). Elements are
  whitespace-trimmed; a single layer of matching quotes (`"` basic / `'`
  literal) is stripped with the body captured verbatim (no `\`-escape decoding,
  matching the scalar string parser); nested-array elements are returned whole
  for recursive re-parsing; trailing commas yield no phantom element; and `#`
  comments (leading full-line or trailing inline, outside strings) are skipped.
  Element `Str`s share the value's buffer (no copy), like the rest of the
  parser. Legacy `toml_*` aliases added in `_compat.cyr`.

### Fixed

- **toml: array-value capture is now quote-aware for `'…'` and skips `#`
  comments.** The multi-line array-capture scanner in `bayan_toml_parse` only
  tracked `"` basic-string state and had no comment handling, so a literal
  string element containing `]` (e.g. `key = ['a]', 'b']`) closed the outer
  bracket early and truncated the captured value, and a `]` inside a `#` comment
  line of a multi-line array did the same. The scanner now tracks whichever
  quote char opened the string (`"` or `'`) and skips `#`-to-end-of-line
  comments, so both forms round-trip intact. Exercised by the new
  `tests/bayan.tcyr` array group.

## [1.0.4] — 2026-07-03

### Fixed

- **toml: `"""…"""` multi-line strings are no longer silently dropped.** The
  TOML value parser only recognized `'''` (triple **single**-quote) as a
  multi-line delimiter; a `"""` (triple **double**-quote) value fell through to
  the single-line `"…"` branch, where the opening `"` immediately closed against
  the second `"` and the entire body was parsed as an empty string — no error,
  just silent data loss. This broke every consumer whose TOML used `"""`,
  notably takumi building zugot recipes: 436 of 563 recipes use `"""` for their
  `make`/`configure`/`install` build steps, so those steps parsed empty and
  takumi produced zero-payload `.ark` packages with no diagnostic. Fixed by
  parameterizing the multi-line parser/end-finder by delimiter char
  (`_toml_parse_multiline_q` / `_toml_multiline_end_q`, `q` = 34 `"` or 39 `'`)
  and adding a `"""` branch to the value dispatch **before** the single-line
  `"` case. Both triple forms are captured **verbatim** (bayan does not expand
  `\`-escapes anywhere; a `\` at a line end is preserved, so shell build steps
  with backslash line-continuations round-trip intact). The original `'''`
  entry points are kept as thin back-compat wrappers. Covered by a new
  `tests/bayan.tcyr` group (verbatim `"""`, `'''` regression, dispatch
  ordering, embedded quotes, empty `""`) plus an adversarial edge-probe pass
  (EOF/no-close bounds, 4-/6-quote counts, mixed delimiters, real zugot
  recipes) — all green.

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
