# 0004 — A JSON object lookup states its key type in its name; the bare name is deprecated

**Status**: Accepted
**Date**: 2026-10-01

## Context

`bayan_json_v_obj_set(obj, key, val)` stores its key as a `Str` (a 16-byte `{data, len}`
header). `bayan_json_v_obj_get(v, key)` reads its key as a NUL-terminated C string. Cyrius
passes both as the same `i64`, so the symmetric-looking pair

```cyrius
bayan_json_v_obj_set(o, str_from("name"), val);
bayan_json_v_obj_get(o, str_from("name"));      # compiles; returns 0
```

compiles, and the lookup `strlen`s the header's pointer bytes and answers "not found". The
caller's next step (`bayan_json_v_str(0)` → `str_len(0)`) is where it crashes, somewhere else
entirely (issue [2026-08-04](../development/issues/archived/2026-08-04-agnosai-json-obj-get-takes-cstr-while-obj-set-takes-str.md), archived as resolved by this decision).

1.4.1 answered with two additive changes: `key: cstring` on `obj_get`, to arm cyrius's
Str-to-cstring diagnostic, and a Str-keyed `bayan_json_v_obj_get_by_str`. Measured on cyrius
6.6.12 (x86_64 and aarch64), the diagnostic does not reach the filed spelling:

- It types only a **named** local or parameter. `bayan_json_v_obj_get(o, str_from("k"))` — the
  issue's own reproduction — compiles with zero warnings, and so does any `Str`-returning call,
  a `Str` global, a `: Str` struct field, a tail call (`return f(o, sk)`) and a method call.
- Cyrius's overload routing (`foo(Str, ..)` → `foo_str`) keys on the **first** argument. The
  key is the second, so no sibling can route on it.

A `Str`'s data pointer is no way out either. A `Str` is not NUL-terminated at its length:
`str_sub`, `str_split` and `str_new` borrow their parent's bytes. So `str_data(s)` handed to a
C-string lookup can run past the key, and the lookup can match a **longer** stored key and
return another pair's value. A `Str` key needs a lookup that takes the length.

The constraint that makes this a real choice: the bare name already means "C string" to every
caller that passes one, including callers whose key is not a literal (a cstr variable, a
`vec_get` result). And `dist/bayan.cyr` is folded into cyrius's stdlib, so whatever the name
means, it means it everywhere at once.

## Decision

**The caller states the key type in the function name, and the name that states nothing is
deprecated.** 1.5.10:

- adds `bayan_json_v_obj_get_by_cstr(v, key: cstring)`, carrying the pre-1.5.10 body;
- keeps `bayan_json_v_obj_get_by_str(v, key: Str)` (1.4.1) as the Str-keyed half;
- marks `bayan_json_v_obj_get` and its legacy alias `json_v_obj_get` `#deprecated(..)`, with a
  message naming both replacements. Both forward to `_by_cstr`, so every answer is unchanged —
  only the call site's warning is new. Both keep `key: cstring`, so the named-local diagnostic
  still fires where callers have not migrated;
- gives both typed lookups a null-key guard: a null `key` died of SIGSEGV before (`strlen(0)` /
  `str_data(0)`) and now returns 0. The deprecated names inherit it.

All of them answer the **first** pair whose key matches; `obj_set` appends, so a repeated key is
a second pair.

The cyrius-side gap (the diagnostic does not type call results, globals, fields, tail or method
calls) is filed with cyrius as `docs/development/issues/2026-10-01-str-cstring-diagnostic-misses-call-results.md`; this decision does not wait on it.

## Consequences

- **Positive** — `#deprecated` flags every call site of the bare name *whatever the argument
  is*, so it reaches the inline `str_from(..)` spelling the type check cannot see, and does so
  in a tail call, where the type check is also blind. It flags the bare name's call sites only:
  `_by_cstr` keeps the old name's diagnostic reach (the first Negative below). A migrated call
  site is self-describing: `_by_cstr(o, "k")` and `_by_str(o, s)` cannot be confused with each
  other in review.
- **Positive** — nothing breaks. Every existing call keeps compiling and answering identically
  (a null key now answers 0 instead of crashing).
- **Negative** — the deprecation does not widen the diagnostic. `_by_cstr` has exactly the old
  name's reach: a `Str`-returning call, a `Str` global or a `: Str` field passed to it compiles
  with no warning. A call that holds a `Str` key moves to `_by_str`, however the key is spelled;
  renaming it to `_by_cstr` leaves it as silent as it was before 1.5.10.
- **Negative** — every remaining call of a deprecated name warns on every build that compiles it,
  and a build that treats warnings as errors fails until the call is renamed.
- **Negative** — `#deprecated` does not cover every path either (measured on 6.6.12): a call
  through `&bayan_json_v_obj_get`, a method-dot call, and a call parsed before the definition do
  not warn. Those are rare spellings for a lookup, unlike `str_from(..)`.
- **Neutral** — bayan's suite must pin the deprecated names' behaviour without warning, so it
  calls them through `&fn` and says so. The warning itself is pinned by
  `scripts/consumer-check.sh`, which compiles a direct call of each deprecated name against every
  bundle that ships it and requires exactly the expected warnings at the caller, with the exact
  message, and none from the bundle. The same script refuses any call of a deprecated name in
  `src/` or `dist/` (one parsed before the definition would not warn), and pins `_by_cstr`'s two
  `key: cstring` diagnostics: a Str-typed local warns, an integer-literal key does not compile.
  Without it the decision would be invisible to CI: bayan's own build and tests are warning-free
  by construction.
- **Neutral** — the `_cstr` suffix is a cyrius overload-slot suffix. It is inert here because the
  base it would attach to, `bayan_json_v_obj_get_by`, does not exist (CI forbids defining it) and
  because 6.6.12 registers `_cstr` siblings without dispatching on them.

## Alternatives considered

- **Rename, as the filing proposed** (`_cstr` takes the C string; the bare name takes a `Str`).
  Rejected in 1.4.1 and again here: renaming the bare name to a `Str` key would silently break
  every caller passing a non-literal C string — a cstr variable, a `vec_get` result. Each would
  keep compiling and break worse than today: `str_len` on a raw C string reads characters 8..15
  as a length and characters 0..7 as a pointer. Swapping a silent wrong answer for a silent wild
  read is not a fix.
- **Accept both key types with a runtime guess** (a `Str` header's second word is a small length;
  a C string's is text). Rejected, as the filing itself does: a heuristic on caller-supplied
  pointers is a worse contract than an explicit one, and for a C string shorter than 16 bytes —
  most JSON keys — the "second word" it would inspect is not part of the key at all.
- **Rely on the `: cstring` diagnostic** (status quo since 1.4.1). Rejected: measured, it misses
  the filed spelling. Its reach is cyrius's to widen; when it does, `_by_cstr` benefits for free.
- **Document only.** The 1.4.1 banner already did, at length, and the 2026-08-28 and 2026-09-23
  re-measurements found the defect still reachable from the most natural spelling.
