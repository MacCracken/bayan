# 0005 — The data-format modules are carved out of the cyrius stdlib, and bayan owns them

**Status**: Accepted
**Date**: 2026-06-10 (bayan 1.0.0, cyrius 6.1.25). Written down at 1.6.1 (2026-10-15) from the
CHANGELOG and the issues; nothing here was recorded as an ADR at the time.

## Context

Until cyrius 6.1.25, `json`, `toml`, `cyml`, `csv`, `base64`, `bigint` and `u128` shipped in
cyrius's own `lib/`. The stdlib is the floor every Cyrius program builds on, bare-metal and
firmware consumers included, and none of those seven is a primitive: they parse and serialise data
formats and do wide arithmetic. A kernel object that needs neither should not have to carry them.

cyrius 6.1.25 opened Phase E, the bayan / ganita split of data and maths out of the stdlib
(`matrix` and `linalg` went to ganita at 6.1.26). The seven modules had no dependencies on each
other, about 3,350 lines and 149 public functions between them.

The second half of bayan's goal (`CLAUDE.md`) is why the modules got a project of their own, not
just a new directory: no downstream project should write a second one. Consumers do write their
own when a format has no owner. mneme wrote a YAML frontmatter parser, a markdown subset and a PDF
writer, and agnosai its definition loading, and each of those is a bayan module now or on the
roadmap.

## Decision

**Carve the seven modules into bayan, unchanged except for names, and make bayan their only
upstream.** At 1.0.0:

- every public function gained the `bayan_` prefix (`json_parse` → `bayan_json_parse`,
  `u256_add` → `bayan_u256_add`); internal helpers kept their names. The transform was rename
  only: no behaviour changed in the carve;
- the old names stayed callable through forwarding aliases ([ADR 0006](0006-legacy-names-are-forwarding-aliases-in-one-last-module.md));
- `cyrius distlib` bundles the modules into `dist/bayan.cyr`, and cyrius folds that file
  byte-identical into its stdlib as `lib/bayan.cyr` (the sandhi pattern). A consumer gets bayan
  either by including the fold or by vendoring a bayan release.

The data domain grows here, not in the stdlib: `yaml` (1.2.0), `dtoa` (1.2.1) and `pdf` (1.5.0)
were written in bayan, and `markdown` is next on the roadmap (1.9.0).

## Consequences

- **Positive** — the stdlib floor holds primitives only. A program that wants a parser includes
  the bundle, or since 1.2.0 one format's sublib ([ADR 0007](0007-per-format-sublibs-beside-the-full-bundle.md)).
- **Positive** — one copy, one owner. A fix ships as a bayan release and reaches cyrius on its next
  fold, so a consumer's hand-rolled version can be deleted rather than kept in step.
- **Negative** — the code moved and its tests did not. Until 1.5.1, `cyrius coverage` found `csv`
  0/3, `cyml` 0/17 and `bigint` 0/20 functions referenced by bayan's suite, on the belief that
  their tests still ran upstream. They did not: cyrius no longer had the code. csv's first test
  found two heap buffer overflows, and the 1.5.1 sweep confirmed twenty defects across bayan's
  modules. `bayan_u256_mul`, wrong for 46% of products, had shipped like that for five releases.
  state.md records the rule this left: a carved module with no local test is untested.
- **Negative** — bayan is the upstream for these modules. There is nowhere to file a module bug;
  it is bayan's to fix.
- **Negative** — the fold comes back. `cyrius lib sync --full` vendors cyrius's whole `lib/` into
  bayan's, so bayan's own `lib/` held stale copies of its own modules until 1.4.0 removed them, and
  it holds `lib/bayan.cyr`, an older bayan, after every pin bump. Deleting it does not last, so from
  1.6.1 CI refuses any way of reaching it (`scripts/vendored-fold-guard.sh`).
- **Neutral** — bayan's release timing is tied to cyrius's: a bayan release headed into a cyrius
  fold carries only what it is for. And a module in the fold shares one global namespace with every
  other fold, under a single-pass compiler. That is why `[lib].modules` has an order, and why
  `pdf` reaches Flate through hooks instead of a hard dependency on sankoch
  ([ADR 0001](0001-flate-via-hooks-not-a-sankoch-dependency.md)).

## Alternatives considered

- **Leave them in the stdlib.** This is what Phase E undid: parsers in the floor that every
  program, a kernel included, builds against.
- **Delete them from the stdlib with no new home**, and let each consumer keep what it needs. This
  multiplies the hand-rolled copies that bayan exists to remove.
- **Carve and redesign at once** (not in the 1.0.0 record; noted at 1.6.1). A rename-only carve
  could be checked mechanically and let every old name forward to its new one. The redesigns came
  afterwards, one release at a time: the TOML structural fixes (1.5.4), the flat JSON parser
  (1.5.10).
