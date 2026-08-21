# 0002 — The PDF object graph does not reuse the JSON value tree

**Status**: Accepted
**Date**: 2026-08-21

## Context

`src/json.cyr` defines a tagged dynamic value — a 24-byte cell with
`JTAG_NULL / BOOL / INT / FLOAT / STR / ARR / OBJ` — plus constructors,
accessors, mutators, and allocator-threaded `_a` twins. It is the most
developed thing in the library.

There is a live precedent for reusing it. `src/yaml.cyr` (1.2.0) parses **into**
`bayan_json_v_*` rather than defining a YAML AST, and it did so for a stated,
filed reason: agnosai asked for "one loader traverses one node type across JSON
and YAML" — the serde-data-model property its Rust original has.

`bayan_pdf_*` (1.5.0) needs a dynamic object representation for the same
mechanical reasons: a PDF file is a graph of typed objects, and both the reader
and the writer traverse it. Reusing the JSON tree would mean one node type
across three formats and no new accessor family.

## Decision

**Define a separate `bayan_pdf_obj_*` tree**: a 32-byte cell tagged
`PTAG_NULL / BOOL / INT / REAL / NAME / STR / ARR / DICT / STREAM / REF`.

Reuse json's **grammar**, not its **tree** — the same cell shape, the same
`_a`-twin convention, the same 0-on-failure / `-1`-on-null-handle accessor
contract — so the module reads as bayan even though the types differ.

## Consequences

- **Positive** — PDF's three types with no JSON analogue (`NAME`, `REF`,
  `STREAM`) get real tags instead of a convention layered over `JTAG_STR`.
  Encoding `/Type` and `1 0 R` as strings-with-a-marker is precisely the
  silent-mis-parse shape this library refuses elsewhere.
- **Positive** — `[lib.pdf]` is a **single-module closure**. Reuse would have
  dragged `json.cyr` *and* `dtoa.cyr` into it; for comparison, `bayan-yaml`
  pays 3,231 lines to ship an 878-line module for exactly that reason. It also
  keeps the cyrius fold small, which is [ADR-0001](0001-flate-via-hooks-not-a-sankoch-dependency.md)'s
  whole motivation.
- **Positive** — real numbers can be represented correctly. A PDF real is
  captured as `(scaled, places)` — value = `scaled / 10^places` — so parse and
  emit are exact inverses and `0.50` round-trips as `0.50`, not `0.5`. There is
  no float anywhere in the module.
- **Negative** — a second constructor/accessor family to document, test, and
  keep consistent, and a consumer holding both a JSON tree and a PDF graph uses
  two APIs with deliberately similar shapes. Mitigated by matching json's
  grammar exactly, so the second one is learned by analogy.
- **Neutral** — a `bayan_pdf_obj_to_json_v` bridge is now a *possible* future
  addition rather than an implicit given. It is deliberately **not** in 1.5.0:
  it would drag `json.cyr` into `[lib.pdf]` and undo the closure benefit. Add
  it in a separate module if a consumer files for it.

## Alternatives considered

- **Reuse `bayan_json_v_*` outright, as yaml does.** The strongest alternative,
  and the reason this ADR exists. It loses on three counts:

  1. **The type sets do not overlap enough.** Ten tags against seven, and three
     of the additions have no JSON analogue at all.
  2. **`JTAG_STR` is documented as a *decoded UTF-8* `Str`** (`json.cyr:229-231`).
     PDF strings are raw bytes with `\ddd` escapes and no Unicode guarantee.
     Sharing the tag means `bayan_json_v_build` would happily serialise a PDF
     byte string as JSON and `bayan_json_v_str` would hand a caller bytes it
     will mis-decode — a silent wrong answer across a module boundary.
  3. **The yaml precedent does not transfer.** yaml reuses the tree because a
     *filed consumer requirement* demanded that exact output shape. No consumer
     wants to run `bayan_json_v_obj_get` over a PDF trailer; the roadmap scopes
     the reader as "object graph + `bayan_pdf_extract_text`".

- **Reuse the tree but add PDF tags to `JTAG_*`.** Rejected: it makes every
  json consumer's `switch` on tag incomplete, and puts PDF concepts in the
  module every other module depends on.

- **A 24-byte cell plus a separate stream record.** Rejected on a narrower
  point: `PTAG_STREAM` genuinely needs three payload slots (its dict, its raw
  bytes, its decoded bytes). A 24-byte cell forces a second heap struct, a
  second size constant, and a second place for the decoded/undecoded state to
  drift out of sync. Eight extra bytes per cell buys one fewer type.

- **Reuse `dtoa.cyr` for real numbers.** Rejected on a hard blocker rather than
  a preference: `bayan_f64_to_json` emits exponent notation (`1e-9`) outside a
  moderate window and the token `"null"` for non-finite values. **Both are
  invalid PDF number syntax** — PDF 32000-1 §7.3.3 has no exponent form — and
  both compile clean, so the failure would have been silent corruption of a
  content stream. pdf carries its own fixed-point emitter regardless, so the
  dependency would have bought nothing.
