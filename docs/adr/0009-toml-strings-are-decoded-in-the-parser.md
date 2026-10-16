# 0009 — TOML strings are decoded in the parser, not by an accessor

**Status**: Accepted
**Date**: 2026-08-28 (bayan 1.5.3). Written down at 1.6.1 (2026-10-15) from the issue and the
CHANGELOG, whose 1.5.3 entry argues it under "Why fix 1 and not fix 2".

## Context

mneme reported ([2026-08-22](../development/issues/archived/2026-08-22-mneme-toml-basic-strings-not-unescaped.md))
that `bayan_toml_get` returned basic strings with their escapes unresolved: `"say \"hi\""` came
back with its backslashes. Measured against Python's `tomllib` while fixing it, nine of ten string
forms were wrong, and a literal string `'hello'` came back with its quotes. mneme had compensated
in its own code (`_cfg_toml_unesc`).

The filing offered three fixes and asked for none in particular:

1. decode in the parser, which is spec-correct but a behaviour change, because a consumer that
   compensated would then decode twice;
2. add a decoding accessor or a `bayan_toml_unescape(s)` helper and leave `bayan_toml_get` as it
   was, which breaks nothing;
3. at least document that values are raw.

## Decision

**Fix 1: each string is decoded by the parser, which is the one place that knows how it was
quoted.** A basic string resolves its escapes and a literal string must not, so the same bytes
decode two ways: `C:\tmp` is a path in `'...'` and a tab in `"..."`. A `Str` from `bayan_toml_get`
does not record which quote produced it, so a helper applied to the result cannot tell which rule to
use, and fix 2 alone cannot be right.

Fix 2's helpers ship as well (`bayan_toml_escape` / `bayan_toml_unescape`), for callers writing
TOML themselves, and fix 3's documentation is in the module header.

## Consequences

- **Positive** — values are what TOML says they are. `tomllib` is the oracle:
  `scripts/gen-toml-vectors.py` writes the string vectors from it, and CI regenerates them and
  requires no change.
- **Negative** — a wrong answer became a right one under consumers that had worked around it, and
  each of those now decodes twice. 1.5.3 shipped it as a patch, because fixing a wrong answer is a
  bug fix, under a banner telling consumers to remove their compensation. mneme's tests were written
  to fail at that moment rather than corrupt data quietly.
- **Negative** — decoding allocates, so a parse can now fail for memory. 1.5.11 made a refused
  decode a failure instead of an empty string, and 1.5.13 swept every allocation point of
  `bayan_toml_parse`.
- **Negative** — removing the quotes exposed what they had hidden. `bayan_toml_is_array` guessed
  from the value's first byte, so `format = '[ $host ]($style)'` turned into an "array". 1.5.4
  answered with the same principle, recording on each pair the kind of value the parser saw
  (`bayan_toml_pair_kind`) rather than guessing it from the bytes later.
- **Neutral** — the reasoning carries over to yaml, and 1.8.0 applied it there. Until then yaml's
  quoted scalars kept their escapes verbatim, "the toml convention" in `src/yaml.cyr`'s words, a
  convention that ended here. The json tree YAML parses into does not record quote style either
  ([ADR 0008](0008-yaml-parses-into-the-json-value-tree.md)), so the fix went into yaml's parser:
  double quotes take YAML 1.2's escapes and single quotes `''`, checked against PyYAML. cyml needs
  nothing: it returns its headers as raw TOML spans and decodes no values itself.

## Alternatives considered

- **Fix 2 alone** (a decoding accessor; `bayan_toml_get` unchanged). It cannot work: by the time
  the caller holds the value, the information that decides how to decode it is gone.
- **Fix 3 alone** (document the raw bytes). This documents a wrong answer and leaves every consumer
  to write the hand-rolled decoder that mneme already had.
- **Record the quote kind on the pair and decode in an accessor** (not in the 1.5.3 record; noted at
  1.6.1). That is correct in principle, but the raw value would still be the default answer, and
  wrong for every caller that never reaches for the accessor.
