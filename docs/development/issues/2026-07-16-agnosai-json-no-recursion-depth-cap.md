# bayan — JSON parsers have no recursion-depth cap: nested input stack-overflows the caller

**Status**: 🔴 **Open**
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
