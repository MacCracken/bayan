# 0012 — Public constants are `const`, and public predicates return `: bool`

**Status**: Accepted
**Date**: 2026-10-22 (bayan 1.10.0)

## Context

Until 1.10.0 every public constant was a top-level `var` set from a literal (`var JTAG_INT = 2;`),
and every predicate returned an `i64` 1 or 0. That is the carved stdlib's style. cyrius had neither
`const` (6.7.2) nor `bool` (6.7.3) when the carve happened, and the modules written since followed
the carved ones.

A `var` has storage. Any file in the program can assign it or take its address, and it is not a
constant expression: cyrius 6.7.16 refuses it as a `case` label, a stack buffer's size, an enum
value or an `#assert` operand ("a const context takes only constants"). So a consumer could not
`switch` on `bayan_json_v_tag(v)` over `JTAG_*`, or put a u256 on the stack with
`var b[U256_SIZE];`. A predicate typed `i64` cannot be returned from a consumer's own `: bool`
function, passed to a `: bool` parameter, or assigned to a `: bool` local. Each is refused with
"a value that is not a bool".

Both fixes break source, so the roadmap held them for one minor release, 1.10.0. It listed the
names by spelling: `JTAG_*`, `TOML_K_*`, `JSON_K_*`, `JS_EV_*`, the public `PDF_*`, `MD_K_*`,
`MD_EXT_*` and `MD_ALIGN_*` ("about 86"), and the 27 `bayan_*_is_*` / `_has_*` predicates.

## Decision

**Every public constant is a `const`, and every public predicate returns `: bool`, and so does its
`_compat` alias.** A public constant is an upper-case name declared at the top level. A predicate is
a function whose whole contract is a yes or no answer, whatever it is called.

- The rule follows the contract, not the spelling. Measured against the tree, the roadmap's
  spelling missed 13 constants (`PTAG_*`, `U256_SIZE`, `JSON_PAIR_SIZE`, `JV_SIZE`) and 5
  predicates (`bayan_u128_eq`, `bayan_u256_eq`, `bayan_pdf_obj_eq`, `bayan_pdf_obj_name_eq`,
  `bayan_pdf_winansi_ok`). 1.10.0 types all of them: 99 constants and 32 predicates, plus 12
  aliases.
- An alias is typed like its canonical name. [ADR 0006](0006-legacy-names-are-forwarding-aliases-in-one-last-module.md):
  whatever is stated about one name is stated about the other.
- **Not predicates**, though their values are 0 or 1:
  - `bayan_u256_cmp` is a three-way comparison.
  - `bayan_cyml_split` reports a status and writes its outputs.
  - `bayan_json_v_bool` reads a value.
  - markdown's `_fenced`, `_list_ordered`, `_list_tight` and `_row_header` are field accessors. They
    share their family's contract: one accessor per field, and 0 for a node of another kind.
    `_task` returns -1, 0 or 1 and `_list_start` returns a number.
- A CI step in `static` holds the rule for names added later. It refuses a top-level upper-case
  `var` and an `_is_` / `_has_` / `_eq` function that does not return `: bool`.

## Consequences

- **Positive** — a constant is a constant expression. `case JTAG_INT:`, `var b[U256_SIZE];` and
  `#assert MD_EXT_GFM == 15` compile, and no file can reassign a constant. The 99 globals have no
  storage: the smoke binary is 4,616 bytes smaller on 6.7.16.
- **Positive** — the type states the contract. A consumer's `: bool` code takes a predicate's
  answer directly.
- **Positive** — the suite pins both halves at compile time. Each constant has an `#assert` of its
  1.9.0 value, which fails the build if the name is a `var` again. Each predicate is passed to a
  `: bool` parameter.
- **Negative** — source breaks. `&NAME` and `NAME = ...` stop compiling. So does a consumer's own
  declaration of one of these names: as a `var` it is "already declared as a top-level const", and
  as a `const`, even with the same value, it is "declared twice".
- **Negative** — a program can hold only one copy of the toml and bigint modules, as it already
  could of json, pdf and markdown, whose private `const`s came earlier.
  [Architecture note 002](../architecture/002-one-copy-of-each-module-per-program.md) has the table.
- **Neutral** — the `: bool` half breaks no call site on 6.7.16. A bool reads as the integer 1 or 0
  in every integer position: `== 1`, arithmetic, an `i64` local or parameter, `store64`. The
  roadmap expected some integer use to stop compiling, and none does. The `const` half is what makes
  this a minor release.

## Alternatives considered

- **Keep the `var`s and document "do not assign".** The language can enforce what the comment would
  only ask. A constant expression stays out of reach: no `switch`, no stack buffer.
- **An `enum` per group** (not in the roadmap's record; noted at 1.10.0). An enum's constants are
  also constant expressions. But it adds a type name to a namespace every fold shares, and it does
  not fit the flag sets: `MD_EXT_*` values are combined with `|`, not enumerated.
- **Type only the names the roadmap spelled out.** The same module would then hold
  `bayan_u128_is_zero: bool` beside `bayan_u128_eq: i64`, a rule by spelling. A consumer re-checks
  once per minor release, and a second break for the missed names would cost them twice.
- **Type the boolean markdown accessors too.** They would leave the contract their accessor family
  shares. Splitting that family is its own decision.
- **One module per release.** Each consumer would re-check at every release. A minor release names
  the whole change once.
