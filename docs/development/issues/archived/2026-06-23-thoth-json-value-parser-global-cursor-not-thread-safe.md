# bayan — JSON value parser uses process-global cursor: not thread-safe (blocks concurrent parsing)

**Status**: ✅ **Resolved in bayan 1.0.3** (cyrius pin 6.2.37). The process-global
cursor was replaced with a per-call 40-byte parser-state struct threaded through
the whole recursive descent (value parser) and the streaming parser. See the
Resolution section below.
**Date**: 2026-06-23
**From**: thoth (the agentic-coding TUI) — found while designing parallel MCP tool
calls. Each tool result is parsed via `bayan_json_v_parse_str` (thoth's
`daimon_extract_text`), so concurrent tool calls => concurrent parses.
Reconfirmed against the bayan bundled in cyrius **6.2.37**.
**Severity**: blocks the feature; safe today because every consumer parses on one
thread. **Affects**: `src/json.cyr`.

## Summary

`bayan_json_v_parse_str` and the whole recursive-descent value parser key off
**process-global cursor + error slots**, reset on every parse and read-modified
through the entire descent:

- **`_jp_buf` / `_jp_len` / `_jp_pos`** — the parser cursor (`src/json.cyr:536-538`).
  Set at parse entry, then advanced/peeked everywhere (e.g. `_jp_skip_ws`
  `json.cyr:547-555`, `_jp_parse_string` `json.cyr:589+`, every `_jp_*` helper).
- **`_json_err_msg` / `_json_err_pos`** — error reporting slots (`src/json.cyr:248-249`,
  set via `_jp_set_err` `json.cyr:540-543`).

Because these are module globals, **two concurrent parses corrupt each other**:
thread B resets `_jp_buf`/`_jp_len`/`_jp_pos` mid-way through thread A's descent, so
A then reads B's buffer at A's offset → wrong/garbage value tree, or an
out-of-bounds `load8(_jp_buf + _jp_pos)`. This happens regardless of which
allocator backs the parsed nodes — it is the cursor state, not the node arena, that
races.

## Reproduction (the intended downstream use)

thoth runs a round of MCP tool calls concurrently (N worker threads). Each worker
parses its own tool-result HTTP body with `bayan_json_v_parse_str(body, len)` (via
`daimon_extract_text`). With ≥2 workers, the shared `_jp_*` cursor is clobbered
mid-descent and the value trees come out wrong or fault.

## Asked of bayan

Provide a **reentrant value-parse path** that threads parser state through a
per-call context instead of the module globals — e.g. a small parser-state struct
(`{buf, len, pos, err_msg, err_pos}`) allocated per call (from the caller's
Allocator, matching the `_a` convention used elsewhere), with the `_jp_*` helpers
taking that state as their first argument. The existing globals-backed
`bayan_json_v_parse_str` can stay as a thin wrapper over a fresh per-call state for
source compatibility; concurrent consumers would call the ctx-threaded variant (and
read errors from the per-call state rather than `bayan_json_last_error*`).

Once done, concurrent JSON parsing (thoth's parallel tool calls) is safe with no
further bayan change. Filed proactively per thoth's "port the floor; never fork the
spine" posture — thoth will not reimplement a parser to work around this.

## Resolution (bayan 1.0.3)

The cursor globals `_jp_buf` / `_jp_len` / `_jp_pos` and the error slots were
removed from the parse path. The value parser and the streaming parser both key
off a per-call **parser-state struct** (`_JP_STATE_SIZE` = 40 bytes:
`buf@+0, len@+8, pos@+16, err_msg@+24, err_pos@+32`) threaded as the first
argument `ps` through every `_jp_*` / `_js_*` helper.

**No thoth change required.** `bayan_json_v_parse_str(buf, len)` (thoth's
`daimon_extract_text` path) keeps its signature and now stack-allocates its own
`var ps[40]`, so each concurrent call owns its cursor — N worker threads parsing
N tool-result bodies no longer collide. The returned value tree is always
correct regardless of concurrency.

**New reentrant surface** (for callers that also want race-free error reporting):

- `bayan_json_v_parse_ctx(ps, buf, len)` / `bayan_json_v_parse_ctx_str(ps, src)`
  — parse into a caller-owned state; touch **no** module globals.
- `bayan_json_state_error(ps)` / `bayan_json_state_error_pos(ps)` — read the
  error from that state instead of `bayan_json_last_error*`.
- `bayan_json_parse_state_size()` — bytes to reserve (stack `var ps[40]` or heap
  `alloc(...)`).

The legacy `bayan_json_last_error()` / `_pos()` still work for single-threaded
callers: the globals-compat wrappers mirror the per-call error into those slots
after the parse returns (a documented, benign last-error race on the failure
path only — concurrent callers use the `ps` accessors above).

**Scope note:** the fix is the cursor, exactly as filed. Node allocation still
flows through the `json_v_*_new` constructors' `default_alloc()`; concurrent node
allocation is the caller's allocator's concern (use a thread-safe or
thread-local allocator), not this race.

Covered by `tests/bayan.tcyr` (nested parse, ctx path, per-call error reporting,
trailing-content rejection); suite green on cyrius 6.2.37.
