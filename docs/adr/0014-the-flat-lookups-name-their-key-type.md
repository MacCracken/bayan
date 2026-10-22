# 0014 — The flat lookups name their key type too; the bare names are deprecated

**Status**: Accepted
**Date**: 2026-10-22 (bayan 1.11.0)

## Context

[ADR 0004](0004-json-lookup-states-its-key-type-by-name.md) (1.5.10) fixed a key-type trap in the
JSON tree lookup by naming the key type in the function, `bayan_json_v_obj_get_by_cstr` /
`_by_str`, and deprecating the bare name. The flat APIs had the same trap, in both directions
(Known gap 7):

- `bayan_json_get` and `bayan_json_get_int` compare with `str_eq` and need a `Str`;
- `bayan_toml_get`, `_get_pair`, `_count`, `_get_sections`, `_get_inline` and `_get_array` compare
  with `str_eq_cstr` and need a C string.

Nothing in any of those names says which, and the wrong key type is a silent "not found". The toml
ones carried no `key: cstring`, so even cyrius's diagnostic could not fire.

The roadmap held this for 1.11.0, beside TOML into the tree (ADR 0013), whose lookup is already
typed. Two things changed since ADR 0004, measured on cyrius 6.7.16:

- **The `: cstring` diagnostic now reaches every spelling ADR 0004 listed as silent.** A `Str`
  passed to a `: cstring` parameter warns as a call's result, a global and a tail call, as well as
  a named local. cyrius fixed it in 6.6.13, from bayan's 2026-10-01 filing.
- **A string literal passed to a `: Str` parameter is wrapped into a `Str`**, so `_by_str(p, "k")`
  is correct. The one silent case left is an untyped C-string variable passed to a `: Str`
  parameter.

## Decision

**Each key-taking flat lookup comes in two, named for its key, as ADR 0004's did, and the bare name
and its alias are deprecated forwarders with the same answers.**

- `bayan_json_get_by_cstr` / `_by_str` and `bayan_json_get_int_by_cstr` / `_by_str`.
- `bayan_toml_get_by_*`, `bayan_toml_get_pair_by_*`, `bayan_toml_count_by_*`,
  `bayan_toml_get_sections_by_*`, `bayan_toml_get_inline_by_*` and `bayan_toml_get_array_by_*`.
- **`_by_cstr` carries `key: cstring`**, so a `Str` passed to it warns. **`_by_str` compares by the
  `Str`'s length**, so a `Str` cut from a longer one (`str_sub`, a `str_split` part), which is not
  NUL-terminated, is read correctly.
- **Each keeps its module's rule for a repeated key**: json's the FIRST pair, toml's the LAST
  (1.5.4). Each answers 0 for a null pairs or key (an empty vec for the sections lookup), where the
  bare names faulted.
- **The bare names keep their key type and forward to it.** The toml ones forward to `_by_cstr`
  and now carry `key: cstring`, as the roadmap asked. The json ones forward to `_by_str` and stay
  unannotated: a `: Str` there would wrap a literal and change the answer the deprecated name gives
  it.
- **The deprecated aliases** (`json_get`, `json_get_int`, `toml_get`, `toml_get_sections`,
  `toml_get_array`) forward to the typed names, never to the deprecated bare ones. A deprecated
  callee warns inside its caller's body, which would put a warning in every build of the bundle.
- Each `#deprecated` names both replacements, and `scripts/consumer-check.sh` checks every one in
  every bundle that ships it.

## Consequences

- **Positive** — a call site says what its key is, and review can see a mismatch. Most callers pass
  literals and move to `_by_cstr`, where the diagnostic now covers every spelling.
- **Positive** — the TOML lookups gain the diagnostic they never had, on both the typed name and
  the deprecated one.
- **Negative** — every call of a bare name warns on every build until it is renamed; a build that
  treats warnings as errors fails until then. ADR 0004 accepted the same cost.
- **Negative** — sixteen more public functions. The bare names go in a later minor release, once
  consumers have moved.
- **Neutral** — the flat APIs still differ on a repeated key (json first, toml last). That is a
  difference in what each format's parser does, and the tree, where TOML refuses a duplicate, is
  where a caller who cares goes.

## Alternatives considered

- **Give each lookup the other module's key type**, the "rename" ADR 0004 rejected. Every caller
  passing the current type would keep compiling and silently get "not found", or worse.
- **One typed name per lookup**, its current key type only. A caller holding the other type has to
  convert: `str_cstr` allocates, and `str_data` of a cut `Str` is not NUL-terminated.
- **Only `_by_cstr`, now that its diagnostic is complete.** That would force every `Str`-holding
  caller through a NUL-terminated copy.
- **Leave the flat APIs and point callers at the tree.** The flat API stays documented and has
  callers, so its trap stays live for every caller that stays.
