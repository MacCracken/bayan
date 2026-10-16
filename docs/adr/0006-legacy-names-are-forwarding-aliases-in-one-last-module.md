# 0006 — The pre-carve names are forwarding aliases in one module, which comes last

**Status**: Accepted
**Date**: 2026-06-10 (bayan 1.0.0). Written down at 1.6.1 (2026-10-15) from the CHANGELOG.

## Context

The carve ([ADR 0005](0005-the-data-format-modules-are-carved-out-of-the-stdlib.md)) renamed every
public function: `json_parse` became `bayan_json_parse`, `u256_add` became `bayan_u256_add`. The
consumers of the stdlib modules called the old names (1.4.1 counted about 40 using
`json_v_obj_get` alone), and cyrius folds bayan into its stdlib, so a plain rename would have broken
every one of them at the fold.

Cyrius compiles in a single pass: a function can call only what is defined before it. And the
bundle is one file of modules in a fixed order, so where the old names live decides what they can
reach.

## Decision

**Every pre-carve name is a one-line forwarding function in `src/_compat.cyr`, the last module of
the bundle, and only of the full bundle.**

- One shim per name, `fn json_parse(src): i64 { return bayan_json_parse(src); }`: 149 at 1.0.0,
  and four more at 1.1.0 for the toml array helpers, 153 in all. The set is closed. `yaml`, `dtoa`
  and `pdf` were written in bayan and have canonical names only, as does every function added
  since 1.1.0.
- `_compat.cyr` is the last entry of `[lib].modules`, because its shims reference a symbol from
  every other module.
- The per-format sublibs leave it out ([ADR 0007](0007-per-format-sublibs-beside-the-full-bundle.md)):
  an alias references every module, so it can ride only the bundle that has all of them.
- The module is deprecated as a whole, for the migration window: its header says it goes once
  consumers re-pin. No release has removed it.

## Consequences

- **Positive** — consumers built unchanged across the carve and every fold since.
- **Positive** — an alias is a call, not a copy. There is one implementation, and a fix to it
  reaches both names.
- **Negative** — two names for every pre-carve function, and anything stated about one has to be
  stated about the other. 1.4.1 annotated `json_v_obj_get`'s key `: cstring` alongside
  `bayan_json_v_obj_get`'s, and 1.5.10 deprecated both ([ADR 0004](0004-json-lookup-states-its-key-type-by-name.md)).
- **Negative** — a shim can go wrong without anything noticing. The coverage counter matched
  substrings until cyrius 6.6.8, and every alias is a substring of the name it forwards to, so all
  153 counted as covered while the suite called ten. 1.5.8 added a row for every alias against its
  twin on the same inputs, with each `_a` alias also run on an allocator that refuses everything
  (so a shim that drops its allocator fails). Sixteen deliberate mis-forwardings in a scratch copy
  were all caught.
- **Negative** — 153 more global names in the full bundle, in a namespace every fold shares.
- **Neutral** — removing them is a breaking change: a minor release that names it, after the
  consumers have moved. The roadmap has no slot for it yet.

## Alternatives considered

- **Rename with no bridge.** Every consumer breaks the day cyrius folds the release, in cyrius's
  own build as much as anyone's.
- **Keep the old names as the canonical ones.** The `bayan_` prefix marks the owner in a namespace
  every fold shares. Without it bayan's names are the stdlib's old names, and nothing marks them as
  bayan's.
- **An alias beside each canonical function** (not in the 1.0.0 record; noted at 1.6.1). Then every
  sublib would carry its module's aliases, and they could no longer be dropped as a unit. In one
  last module they cost the sublibs nothing and leave in one change.
