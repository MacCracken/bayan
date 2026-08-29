# `bayan_json_v_obj_get` takes a cstr key while `bayan_json_v_obj_set` takes a `Str`

**Filed by**: agnosai (Rust → Cyrius port, M7 bite 10)
**Date**: 2026-08-04
**Version**: bayan 1.4.x (as vendored by `cyrius deps` at cyrius 6.5.6)
**Severity**: Low — no wrong answers, but the failure mode is a segfault rather
than an error return.
**Status**: OPEN, and the header line above is now inaccurate — see the
2026-08-28 re-measurement below.

> **Re-measured 2026-08-28 at bayan 1.5.3 / cyrius 6.5.36. Still open, but the
> symptom has CHANGED and the 1.4.1 mitigation does not cover this issue's own
> reproduction.**
>
> **The crash is gone; a silent wrong answer took its place.** Running this
> file's own repro today returns 0 ("not found") rather than faulting: `strlen`
> terminates a few bytes into the `Str` header on the data pointer's zero high
> bytes and yields a junk length, so the length compare simply misses. Nothing
> faults at the call. That is *worse* to diagnose, not better — the fault is
> deferred to whatever the caller does with the 0 (`bayan_json_v_str(0)` ->
> `str_len(0)` is the path named in the in-code banner), which is somewhere
> else entirely. Anyone triaging from the "SIGSEGV" in the header above will be
> looking for the wrong thing.
>
> **The armed diagnostic misses the inline form — which is the form this issue
> reproduces with.** The `: cstring` annotation added in 1.4.1 fires when the
> argument is a named `Str`-typed local (`var key = str_from("k");` then
> `obj_get(o, key)` warns). It does NOT fire on
> `bayan_json_v_obj_get(o, str_from("name"))`, the inline spelling in the
> Reproduction section of this very file: that compiles with zero warnings and
> returns 0. So the mitigation misses the case it was written to catch.
>
> Reconciling the two signatures is still a breaking change and still wants its
> own release. Recorded in `docs/development/state.md` under Known gaps.

## What happens

The two halves of the object API disagree about what a key is:

```cyrius
fn bayan_json_v_obj_set(obj, key, val): i64   # `key` is a Str
fn bayan_json_v_obj_get(v, key): i64          # `key` is a char*
```

`obj_set` stores `key` and later reads it with `str_len` / `str_data`
(`_jv_pair_new`), so it wants a `Str`. `obj_get` calls `strlen(key)` and
`memeq(str_data(ks), key, klen)`, so it wants a NUL-terminated C string.

Writing the symmetric-looking pair is therefore a crash:

```cyrius
var o = bayan_json_v_obj_new();
bayan_json_v_obj_set(o, str_from("name"), bayan_json_v_str_new(str_from("x")));
bayan_json_v_obj_get(o, str_from("name"));   # SIGSEGV
```

`strlen` walks the 16-byte `Str` header as characters. It reads the length
field and the data pointer as text and keeps going until it finds a zero byte,
which is a read of unbounded length off the end of the header.

## Reproduction

```cyrius
# repro.cyr — build with `cyrius build repro.cyr /tmp/repro`
fn main(): i64 {
    alloc_init();
    var o = bayan_json_v_obj_new();
    bayan_json_v_obj_set(o, str_from("k"), bayan_json_v_int_new(1));

    # Correct, per the current API: a cstr literal.
    var ok = bayan_json_v_obj_get(o, "k");
    if (bayan_json_v_int(ok) != 1) { return 2; }

    # The symmetric spelling — crashes.
    var bad = bayan_json_v_obj_get(o, str_from("k"));
    return bayan_json_v_int(bad);
}
var rc = main();
syscall(60, rc);
```

Observed: exit 139 (SIGSEGV) on the second call, on x86_64 Linux.

The same shape crashed four separate tests in agnosai's
`tests/sandbox_python.tcyr` before the keys were changed to cstr literals.

## Why it is worth fixing

Every other `Str`-taking function in the JSON surface accepts a `Str`, and
`obj_set` — the function a caller reaches for immediately before `obj_get` —
is one of them. The mismatch is invisible at the call site: both spellings
compile, because Cyrius passes an `i64` either way. There is no diagnostic, and
the result is a fault rather than a 0 return, which is what the function
already documents for "key not found".

`bayan_json_v_pointer_cstr` / `bayan_json_v_pointer` show the codebase's own
convention for exactly this: the `_cstr` suffix marks the raw-pointer variant
and the bare name takes a `Str`. `obj_get` is the bare name taking the raw
pointer.

## Suggested fix

Whichever the maintainer prefers — this is a note about the asymmetry, not a
request for a specific shape:

1. **Follow the existing `_cstr` convention.** Rename the current function to
   `bayan_json_v_obj_get_cstr` and add `bayan_json_v_obj_get(v, key: Str)`.
   This matches `bayan_json_v_pointer` / `_pointer_cstr` and makes the
   symmetric spelling correct. It is a breaking change for callers passing
   literals, though those callers are the ones a compiler cannot distinguish
   today anyway.

2. **Or accept both.** A `Str` is a 16-byte header whose first eight bytes are a
   small length; a cstr key points at character data. A guard could tell them
   apart in practice, but heuristics on caller-supplied pointers are worse than
   an explicit API, so this is mentioned only for completeness.

3. **Or, at minimum, document it.** The doc comment on `obj_get` currently
   says "Returns 0 if not found" and does not say what `key` is. Stating that
   `key` is a NUL-terminated C string, and that `obj_set` takes a `Str`, would
   have prevented this entirely.

No agnosai work is blocked — the call sites were corrected to pass cstr
literals, which is the documented-by-code behaviour.
