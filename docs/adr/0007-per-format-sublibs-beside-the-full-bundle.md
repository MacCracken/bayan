# 0007 — Each format also ships as its own sublib, beside the full bundle

**Status**: Accepted
**Date**: 2026-07-16 (bayan 1.2.0). Written down at 1.6.1 (2026-10-15) from the CHANGELOG and
`cyrius.cyml`.

## Context

Until 1.2.0 bayan shipped one artifact, `dist/bayan.cyr`: every module and every alias, which is
also what cyrius folds. 1.2.0 added `yaml` and took the bundle to about 4,750 lines; at 1.6.0, with
`pdf`, it is 718 KB. A consumer that wants base64 does not want a PDF reader's globals in its
program, and every module added makes that worse.

`cyrius distlib` can build named profiles from `[lib.<name>]` tables in the manifest (the pattern
sigil and sandhi use), each a list of modules that it concatenates in order.

## Decision

**One `[lib.<name>]` profile per format, each the self-contained closure of that format's entry
points, built beside the full bundle.** `cyrius distlib --all` writes `dist/bayan-<name>.cyr` and
a `.deps` sidecar naming the stdlib leaves it needs.

- 1.2.0 added json, yaml, toml, cyml, csv, base64, u128 and bigint; 1.5.0 added pdf.
- A closure is written out by hand in `cyrius.cyml`, in single-pass order. Most are one module,
  because the carved modules do not depend on each other. `yaml` carries `dtoa` and `json`, the
  value tree it parses into ([ADR 0008](0008-yaml-parses-into-the-json-value-tree.md)). `pdf` is
  one module by design: it has its own object tree and number emitter
  ([ADR 0002](0002-pdf-objects-do-not-reuse-the-json-value-tree.md)), and reaches Flate through
  hooks ([ADR 0001](0001-flate-via-hooks-not-a-sankoch-dependency.md)).
- Sublibs expose canonical `bayan_*` names only. The aliases ride the full bundle alone
  ([ADR 0006](0006-legacy-names-are-forwarding-aliases-in-one-last-module.md)).
- The full bundle stays the fold.

## Consequences

- **Positive** — a consumer pays for what it uses: `bayan-base64.cyr` is 9 KB, `bayan-csv.cyr` 6 KB.
- **Positive** — fewer global names in a consumer that wants one format.
- **Negative** — ten artifacts to keep regenerable from `src/` and consistent with each other. CI
  checks that `distlib --all --check` passes, that a fresh regeneration changes nothing, and
  (`scripts/consumer-check.sh`) that each bundle compiles as a consumer from exactly the leaves its
  sidecar declares, with `--no-deps` so the manifest's own list cannot hide a missing one.
- **Negative** — a sidecar can be wrong, and bayan cannot edit one: `distlib` generates them.
  Under cyrius 6.5.28 the sidecars of `bayan-toml` and `bayan-cyml` left out `fmt`, because the
  inference did not close over the stdlib's own dependencies, so neither compiled for a consumer
  that followed its sidecar. The consumer check, new at 1.4.2, surfaced it (filed 2026-08-19,
  Known gap 3), and cyrius 6.6.0 fixed the generator.
- **Negative** — sublibs overlap. `bayan-yaml` contains `bayan-json`, so a consumer that wants
  both includes `bayan-yaml` alone. Including both defines json's symbols twice.
- **Neutral** — from 1.5.12 (cyrius 6.6.18's distlib) every bundle opens with a compile-verified
  `# Requires` include block of its sidecar's leaves, so a sublib can be included with nothing in
  front of it. CI builds the full bundle that way.

## Alternatives considered

- **The full bundle only**, as before 1.2.0. Every consumer carries every module, and the cost grows
  with each one bayan adds.
- **Ship the modules and let consumers include what they need** (not in the 1.2.0 record; noted at
  1.6.1). The consumer would then own the single-pass order and the closure (that `yaml` needs `json`
  and `dtoa` first, and which stdlib leaves each needs), which is what `distlib` computes and CI
  verifies.
