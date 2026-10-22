# 0013 — TOML parses into the JSON value tree, strictly, by tomllib's answers

**Status**: Accepted
**Date**: 2026-10-22 (bayan 1.11.0)

## Context

bayan's TOML parser (`src/toml.cyr`, carved from the stdlib at 1.0.0) is flat. A document is a
vec of sections, each section a dotted name and a vec of key/value pairs, and a value is a `Str`:
an array or an inline table stays raw text that a caller decomposes on demand. It has no error
channel, so it degrades. A duplicate key resolves to the last value, an unterminated string ends at
the line, and a document TOML refuses still parses to something. Two shapes of document cannot be
stated in it at all (Known gap 1): a dotted key whose quoted segment holds a dot, and an array of
tables under a dotted parent. A table name is one dotted string, so there is nowhere to keep either
apart.

yaml has parsed into json's value tree since 1.2.0 ([ADR 0008](0008-yaml-parses-into-the-json-value-tree.md)),
so one loader walks json and yaml alike, and its lookup is json's. TOML's data model is that tree's
except for one type the tree does not have: dates and times. The roadmap put TOML into the tree at
1.11.0 as "the right shape for the surface".

Five things had to be decided: how strict the parser is and against what; what a date becomes in a
tree that has no date; where the parser lives; what happens at the tree's limits; and what the
cost bound is.

## Decision

**`bayan_toml_v_parse` reads TOML 1.0.0 into json's value tree and answers what Python's `tomllib`
answers: a document tomllib accepts parses to the tree tomllib builds, and one it refuses is
refused, with a message and a byte offset.** The flat parser stays, unchanged, for the callers it
has.

- **The oracle is tomllib**, stdlib from Python 3.11, so CI installs nothing to ask it. The rules
  the TOML spec leaves to prose (when a table counts as defined, what a dotted key may extend) are
  tomllib's. Its model keeps three flags per table, and bayan keeps the same three in the container
  cell's reserved word during the parse, clearing them before it returns:
  - EXPLICIT: a header named the table;
  - FROZEN: an inline table or a static array;
  - PENDING: a dotted key opened the table in this section; it becomes EXPLICIT at the next header.
- **A date or time is a string cell holding its text as written**, and the parser writes which of
  TOML's four kinds it is into the cell's reserved word (`TOML_DT_OFFSET`, `_LOCAL`, `_DATE`,
  `_TIME`). `bayan_toml_v_datetime_kind(v)` reads it, and a cell json or yaml made reads 0. Every
  json consumer sees a string, as a JSON tool would, and a TOML-aware consumer can still tell a
  date from a string.
- **Where the tree cannot follow tomllib, bayan refuses.** An integer outside i64 is "integer out of
  range"; tomllib returns a Python int. Nesting past json's cap of 128 levels is "nesting too deep",
  counted as json counts, the root table being level 1; tomllib stops at Python's recursion limit.
  The input is bytes, so bytes that are not UTF-8 are refused; tomllib.load raises
  UnicodeDecodeError on them before parsing.
- **A module of its own, `src/toml_tree.cyr`, and a sublib of its own, `bayan-toml-tree`** (dtoa,
  json, toml_tree). It shares nothing with `toml.cyr`. `bayan-toml` stays the flat parser alone, so
  its consumers neither carry json nor lose the right to include `bayan-json` beside it.
- **A hash index keeps a key's lookup O(1).** Every key a document defines goes into one
  open-addressing table keyed by (parent cell, key bytes). A table of n keys then costs O(n), where
  a walk of each object's pairs would cost O(n²). `tests/toml_scaling.cyr` gates it.

## Consequences

- **Positive** — one loader for json, yaml and toml, and one lookup for all three:
  `bayan_json_v_obj_get_by_cstr` / `_by_str`, which state their key type (ADR 0004). That is the
  answer to the flat lookups' key-type disagreement too ([ADR 0014](0014-the-flat-lookups-name-their-key-type.md)).
- **Positive** — the two subset edges have answers. `a."b.c".d` is three nested tables, and
  `[[a.b]]` repeated under a dotted parent is one array.
- **Positive** — a refused document is refused. The flat parser has no error channel, and its
  documented degradations were the last place a TOML consumer could silently get a different answer
  from every other TOML implementation.
- **Positive** — the claim is checked, not asserted. CI regenerates 3,494 vectors from tomllib:
  hand-written documents per rule, random documents over a small key alphabet so that tables
  collide, mutations of those, and the string vectors' documents. A scratch differential of 384,384
  more agreed at 1.11.0. A fuzz harness checks the properties no oracle is needed for, at volume.
- **Negative** — two TOML parsers, with different answers on the documents TOML refuses. The flat
  parser's header points at the tree one, and the CHANGELOG says which to use.
- **Negative** — the reserved word is now read for one purpose. json's layout comment says so, and
  a later use of the word has to keep a string's kind or move it.
- **Negative** — a date is not a type a JSON consumer can switch on. A consumer that must tell
  `d = 1979-05-27` from `d = "1979-05-27"` has to know to ask `bayan_toml_v_datetime_kind`.
- **Neutral** — strictness costs time. The tree parse of a 3.1 KB manifest takes about 100 µs, the
  flat parse about 30 µs; the flat one validates nothing and leaves arrays and inline tables as raw
  text.

## Alternatives considered

- **Parse into the tree leniently, as the flat parser does.** That rebuilds the flat parser's
  silent answers in a second shape. Without an oracle, "lenient" has no definition a test can
  check.
- **A `JTAG_DATETIME` tag.** Every `switch` over `JTAG_*` in every consumer would meet a tag it
  does not know. `bayan_json_v_build` would need a rule for writing a date to JSON, and JSON has
  none.
- **Normalize a date's text** (`T` for the space, `Z` uppercase). Nothing in the stdlib reads RFC
  3339 that would need it: `lib/chrono.cyr`'s parser reads a fixed `YYYY-MM-DDTHH:MM:SSZ` layout
  either way. The text as written loses nothing.
- **Refuse dates.** They are first-class TOML values, common in configuration and frontmatter.
- **Put the tree parser in `bayan-toml`.** Every flat consumer would carry json, and a program
  including `bayan-toml` and `bayan-json` would be refused, because json's consts would be declared
  twice ([architecture note 002](../architecture/002-one-copy-of-each-module-per-program.md)).
- **Look keys up by walking the object's pairs**, as `bayan_json_v_obj_get_*` does. That is
  quadratic on a table anyone can send.
