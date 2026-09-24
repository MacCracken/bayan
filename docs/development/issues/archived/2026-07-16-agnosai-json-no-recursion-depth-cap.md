# bayan — JSON parsers have no recursion-depth cap: nested input stack-overflows the caller

**Status**: ✅ **Resolved in bayan 1.1.1** (cyrius pin 6.4.64).
Both descents are bounded at **128 levels** (serde_json's default, so the port
is wire-parity); past the cap the parse fails with `"nesting too deep"` through
the existing per-call error path. See the Resolution section below.
**Date**: 2026-07-16
**From**: agnosai (the CrewAI-parity agent-orchestration Rust→Cyrius port) —
**blocker #2** in its port plan
(`agnosai/docs/development/cyrius-port-plan.md`). Noted there as an upstream
filing but never actually filed; materialized here on review.
**Severity**: blocks agnosai's server surface — untrusted-input DoS. This is a
**parity regression**, not a gap: the Rust original inherited serde_json's
default 128-level depth limit; the port loses it.
**Affects**: `src/json.cyr` — both the value parser and the streaming parser.

## Summary

Neither JSON descent bounds its recursion depth:

- **Value parser**: `_jp_parse_value` recurses through array elements
  (`src/json.cyr:886`) and object values (`src/json.cyr:921`) with no depth
  check. The per-call parser state (`_JP_STATE_SIZE = 40`, `src/json.cyr:563`)
  is exactly 5 slots — `buf, len, pos, err_msg, err_pos` — **no depth
  counter**.
- **Streaming parser**: `_js_parse_value` recurses via `_js_parse_array`
  (`src/json.cyr:1285`) and `_js_parse_object` (`src/json.cyr:1324`), same
  shape, same missing bound.

A deeply nested document (`[[[[…` — 2 bytes per level) recurses once per
level until the thread's stack is exhausted. Even behind sandhi's 64 KiB body
cap, ~32k levels fit in one request body — orders of magnitude past any stack.

## Reproduction (the intended downstream use)

agnosai's server parses untrusted HTTP bodies on `POST /crews`,
`/a2a/receive`, and `/mcp` with the bayan value parser. A hostile (or merely
buggy) client sends a few-KiB nested-array body → the worker thread
stack-overflows → the process dies. serde_json in the Rust original rejects
the same body at depth 128 with a parse error.

## Asked of bayan

Add a depth counter to the per-call parser state and bound the descent:

- Grow the parser state by one slot (`_JP_STATE_SIZE` 40 → 48, `depth@+40`),
  increment on entering `_jp_parse_value` / `_js_parse_value` (or just their
  array/object branches — scalars can't recurse), decrement on exit.
- Past the cap, fail the parse through the existing per-call error path
  (`err_msg`/`err_pos` — "nesting too deep") exactly like any other parse
  error; no new error surface needed.
- **Default cap 128**, matching serde_json, so the port is wire-parity.
  A setter on the ctx path (or a `_a`-style variant) for callers who need a
  different bound is welcome but not required.
- `bayan_json_parse_state_size()` already tells callers how many bytes to
  reserve, so the state growth is transparent to well-behaved consumers; the
  documented stack pattern `var ps[40]` in comments/docs needs the matching
  bump.

Filed per the same posture as the thoth cursor issue
([2026-06-23](2026-06-23-thoth-json-value-parser-global-cursor-not-thread-safe.md)):
agnosai will not fork or wrap the parser to work around this.

## Resolution (bayan 1.1.1)

Implemented exactly as asked. The per-call parser state grew one slot —
`_JP_STATE_SIZE` 40 → **48** bytes (`buf@+0, len@+8, pos@+16, err_msg@+24,
err_pos@+32, depth@+40`), zeroed in `_jp_state_init`, so every entry (value
`bayan_json_v_parse*` / ctx `bayan_json_v_parse_ctx*` / streaming
`bayan_json_stream_parse*`) starts each parse at depth 0.

Both descents are bounded in their value dispatchers — `_jp_parse_value` and
`_js_parse_value` increment `depth@+40` on entering an array/object branch
(scalars can't recurse, so only the container branches touch the counter),
decrement on exit, and past **`_JP_MAX_DEPTH` = 128** fail through the
existing per-call error path with `"nesting too deep"` — exactly like any
other parse error, no new error surface:

- **Value path**: returns 0; error in `bayan_json_state_error(ps)` /
  `_pos(ps)`, mirrored into `bayan_json_last_error()` by the globals-compat
  wrappers as usual.
- **Streaming path**: returns -1; fires `JS_EV_ERROR` and mirrors into the
  legacy last-error slots, same as every other stream error.

The cap is exact serde_json semantics: **128 open containers parse; the 129th
fails.** A hostile `[[[[…` body now costs 128 frames, not one frame per input
byte-pair.

**No agnosai change required.** `bayan_json_v_parse_str(buf, len)` and
`bayan_json_stream_parse(buf, len, h)` keep their signatures; the state growth
is internal to their stack allocation (`var ps[48]`). Callers of the ctx path
that sized their state via `bayan_json_parse_state_size()` (as documented) are
transparent; only a hardcoded `var ps[40]` needs the bump to 48. No
configurable-cap setter was added — 128 is the wire-parity default asked for;
a `_a`-style variant can follow if a consumer materializes a need.

Covered by `tests/bayan.tcyr` ("json recursion-depth cap" group: 200-deep
nested array rejected on both parsers with the depth error, 100-deep parses
clean, exact 128/129 boundary, legacy-entry error mirror, `_compat` alias
parity); suite 86 → 101 asserts, green on cyrius 6.4.64. `dist/bayan.cyr`
regenerated via `cyrius distlib`.
