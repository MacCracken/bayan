# bayan — YAML parse into the existing tagged value tree (feature request)

**Status**: ✅ **Resolved in bayan 1.2.0** (cyrius pin 6.4.64). Shipped as
asked — see the Resolution section below.
**Date**: 2026-07-16
**From**: agnosai (the CrewAI-parity agent-orchestration Rust→Cyrius port) —
listed as an upstream filing in its port plan
(`agnosai/docs/development/cyrius-port-plan.md`, "Upstream filings": *"YAML
parse → the existing tagged value tree (draft written)"*). The referenced
draft was never filed in bayan; materialized here on review.
**Severity**: not a blocker — YAML sits behind agnosai's non-default
`definitions` cargo feature and is explicitly **deferred past v2.0.0 parity**
(port plan, Phase 9: JSON-only definitions ship; ZIP + YAML are upstream
filings). Wanted post-parity.
**Affects**: new module (`src/yaml.cyr`).

## Summary

agnosai's `definitions` feature loads agent/crew definition files. The Rust
original deserializes YAML through the same serde data model as JSON, so one
loader traverses one value shape regardless of input format. For the port to
keep that property, bayan's YAML parser must produce **the same `JTAG_*`-tagged
`bayan_json_v_*` node graph** the JSON value parser returns — not a new
YAML-specific AST — so `bayan_json_v_*` accessors work identically over parsed
JSON and parsed YAML.

(Phase-9 note for scope calibration: the ```` ```yaml ```` at agnosai's
`k8s_crd.rs:33` is a doc comment — its CRD path parses JSON only. The real
YAML consumer is definition files.)

## Asked of bayan

- `bayan_yaml_parse(src)` (+ `_a` allocator-threading variant per house
  convention) → the existing tagged value tree (`bayan_json_v_*` nodes).
- Pragmatic YAML subset (block/nested mappings, block + flow sequences,
  quoted scalars, comments) — anchors/aliases, tags, and multi-document
  streams explicitly out unless a consumer materializes for them. Reject
  out-of-subset input loudly rather than mis-parsing.
- Per-call parser state from day one (the thoth cursor lesson,
  [2026-06-23](2026-06-23-thoth-json-value-parser-global-cursor-not-thread-safe.md))
  and a recursion-depth cap from day one (the JSON gap,
  [2026-07-16](2026-07-16-agnosai-json-no-recursion-depth-cap.md)) — don't
  re-introduce either.

## Convergent demand

**mneme** (note-taking port) independently needs YAML frontmatter parsing and
hand-rolls a ~200-line subset in `mneme/src/core_frontmatter.cyr` in the
interim — see the roadmap item for the combined scope (including the
`bayan_yaml_frontmatter_split` helper). Two consumers, one filing: this lands
once, both migrate.

## Resolution (bayan 1.2.0)

Implemented as asked — `src/yaml.cyr` (874 lines, 12 public fns):

- **`bayan_yaml_parse(src)`** / `bayan_yaml_parse_str(buf, len)` /
  reentrant `bayan_yaml_parse_ctx(ps, buf, len)` + `_ctx_str` → the existing
  `JTAG_*`-tagged `bayan_json_v_*` value tree. Every `bayan_json_v_*`
  accessor traverses YAML output unchanged — the one-loader-one-shape
  property this filing asked for. Errors via `bayan_yaml_state_error*(ps)`
  (per-call) or the `bayan_yaml_last_error*()` mirror.
- **Subset** (documented in the module header): block mappings (plain/quoted
  keys) nested by indentation, block sequences incl. compact `- key: value`
  items, single-line flow sequences, quote-aware `#` comments, scalars
  (null/`~`/bool, strict-JSON-grammar numbers via the json scanner, verbatim
  quoted strings), one `---`/`...` marker pair, BOM skip. **Out-of-subset
  rejects loudly** — anchors/aliases/tags (value and key position), block
  scalars, flow mappings incl. implicit `[a: b]`, multi-doc, marker-line
  content, tabs in indent, empty flow elements, malformed quotes.
- **Both lessons applied from day one** as asked: per-call parser state
  (shared with json — reserve via `bayan_json_parse_state_size()`) and the
  shared 128 recursion cap covering block AND flow nesting.
- **`bayan_yaml_frontmatter_split(src)`** (+`_a`) for the mneme shape:
  `---`-fenced frontmatter → `{yaml, body}` pair (`...` closes too; CRLF
  tolerated; no/unclosed fence → `{0, whole input}`).
- Pre-release hardening: a 36-agent adversarial review found 6 parser bugs
  (marker-line content absorbed, lax number typing, mid-word quotes
  suppressing comments, implicit flow mappings key-splitting, phantom nulls
  from empty flow elements, glued quoted scalars) — all fixed and pinned.
  Suite 101 → 249 asserts, green on cyrius 6.4.64. `dist/bayan.cyr`
  regenerated (~4,750 lines); `yaml.cyr` sits after `json.cyr` in
  `[lib].modules` (single-pass order).

**Consumer next steps:** agnosai re-pins bayan ≥ 1.2.0 (or picks up the next
cyrius `lib/bayan.cyr` refold) and points its `definitions` loader at
`bayan_yaml_parse`; mneme replaces `core_frontmatter.cyr` with
`bayan_yaml_frontmatter_split` + `bayan_yaml_parse`.
