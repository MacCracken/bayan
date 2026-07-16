# bayan — YAML parse into the existing tagged value tree (feature request)

**Status**: 🔴 **Open** — accepted onto the roadmap
([roadmap.md](../roadmap.md), "YAML parsing — `bayan_yaml_*`").
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
