# 0008 — YAML parses into the JSON value tree

**Status**: Accepted
**Date**: 2026-07-16 (bayan 1.2.0). Written down at 1.6.1 (2026-10-15) from the issue and the
CHANGELOG. [ADR 0002](0002-pdf-objects-do-not-reuse-the-json-value-tree.md) (1.5.0) cites this
decision as the precedent it declined to follow for PDF, and says why.

## Context

agnosai's filing ([2026-07-16](../development/issues/archived/2026-07-16-agnosai-yaml-parse-into-tagged-value-tree.md))
asked for YAML parsing for its agent and crew definition files. Its Rust original reads YAML and
JSON through the same serde data model, so one loader walks one value shape whatever the input
format, and the port has to keep that. mneme needed the same parser for Markdown frontmatter, and
had written its own in the meantime.

`src/json.cyr` already had a tagged dynamic value: a 24-byte cell tagged
`JTAG_NULL / BOOL / INT / FLOAT / STR / ARR / OBJ`, with constructors, accessors, `_a` twins, a
per-call parser state (1.0.3, after thoth's thread-safety report) and a recursion cap of 128
(1.1.1, after agnosai's). YAML's data model, without anchors, tags and the like, is JSON's.

## Decision

**`bayan_yaml_parse` returns the same `bayan_json_v_*` cells the JSON value parser returns, and
reuses the JSON parser's machinery to build them.**

- One node type: every `bayan_json_v_*` accessor works on YAML output unchanged.
- One parser state: YAML runs on json's 48-byte per-call state (a caller reserves it with
  `bayan_json_parse_state_size()`), shares its depth cap (128, block and flow nesting), and types
  numbers with json's strict-grammar scanner. So it was reentrant and depth-capped from its first
  release, as the filing asked.
- What the tree cannot hold is refused, loudly: anchors and aliases, tags, block scalars, flow
  mappings, multi-document streams. The subset is listed in `src/yaml.cyr`'s header.
- `yaml.cyr` references json internals (`_jp_state_init`, `_jp_set_err`, `_jp_parse_number`, the
  constructors), so it comes after `json.cyr` in every module list.

## Consequences

- **Positive** — one loader serves both formats, which is the property the filing asked for.
- **Positive** — reentrancy and the depth cap came with the shared state, so YAML repeated neither
  of the two lessons the JSON parser learnt through filings.
- **Negative** — the two modules are coupled. A change to json's internals is a change to yaml's,
  and `bayan-yaml` carries `json.cyr` and `dtoa.cyr` ([ADR 0007](0007-per-format-sublibs-beside-the-full-bundle.md)).
- **Negative** — the tree's rules bind YAML. `bayan_json_v_obj_set` appends, so until 1.5.1 a
  duplicate key became two pairs that were read two ways: bayan's lookup took the first, and any
  JSON reader of the serialised output the last. YAML has refused duplicate keys since. The scanner
  is shared too, and that cut both ways: an integer past i64 (`uid: 18446744073709551616`) became
  0 in both formats, and json's number fix at 1.5.1 fixed yaml with it.
- **Negative** — the tree records values, not how they were written. A string cell does not say
  which quote produced it, so anything that depends on the quote style has to happen in the parser.
  That is [ADR 0009](0009-toml-strings-are-decoded-in-the-parser.md)'s argument, and why the yaml
  escapes item on the roadmap (1.8.0) is a parser change.
- **Neutral** — the line this draws: reuse the tree where the formats share a data model. PDF does
  not, so its objects have their own tree ([ADR 0002](0002-pdf-objects-do-not-reuse-the-json-value-tree.md)),
  and TOML's flat model may move into this one (roadmap 1.11.0).

## Alternatives considered

- **A YAML AST of its own.** Rejected by the filing's reason: a consumer would convert it to the
  json tree, which is the second loader the filing asked bayan to make unnecessary.
- **A YAML parser with its own state and depth handling** (not in the 1.2.0 record; noted at 1.6.1).
  It would build the same cells with a second copy of the machinery, and the two lessons would have
  had to be applied twice.
