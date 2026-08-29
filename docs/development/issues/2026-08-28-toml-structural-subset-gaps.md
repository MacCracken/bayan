# TOML: seven structural gaps that degrade silently rather than reporting

**Filed by**: bayan (self, during the 1.5.3 string-decoding repair)
**Date**: 2026-08-28
**Version**: bayan 1.5.3, cyrius 6.5.36. Every item confirmed by building a
repro against `src/toml.cyr` at that revision.
**Severity**: Medium — no crashes and no memory errors, but each returns a
wrong answer or drops data without saying so.
**Status**: OPEN. Deliberately not fixed in 1.5.3.

## Why this is a separate filing

1.5.3 fixed the string-VALUE defects mneme reported
([2026-08-22](2026-08-22-mneme-toml-basic-strings-not-unescaped.md)) plus the
value-arm defects found alongside them — comments captured into values, CRLF
left on values, two scanners that swallowed the rest of the document. Those all
live in one place: the code that decides where a value starts and stops.

The seven below do not. Each changes what the parser's **data model** is — what a
key is, whether a table can be empty, what a duplicate means — and several
cannot be fixed without changing the shape `bayan_toml_parse` returns. Bundling
them into a patch release alongside a string fix would make one CHANGELOG entry
that consumers cannot reason about. They want their own release, and probably
their own design note about whether bayan's flat `vec of {name, pairs}` is
still the right return type.

The gaps are now stated in `src/toml.cyr`'s module header, which is the
immediate harm reduction: an undocumented gap is how a downstream repo ends up
hand-rolling a second parser, which is the outcome bayan exists to prevent.

## The gaps

Each was confirmed by running the parser, not by reading it. Item 6 is the
only one 1.5.3 made reachable by one more spelling; the rest predate it.

### 1. Quoted keys are not parsed

```toml
"key one" = 1
plain = 2
```

The key scan (`bayan_toml_parse`, the `else` arm) breaks on `=`, space, tab or
newline with no quote awareness, and the `load8(...) == 61` test that follows
has no `else`. So `"key one"` scans to `"key`, the next byte is a space rather
than `=`, and **the whole pair is discarded**. Without a space —
`"key" = 1` — the pair survives but the key keeps its quotes, so
`bayan_toml_get(pairs, "key")` misses it.

Per the spec both are ordinary keys naming `key one` and `key`.

### 2. Dotted keys are flat, and the spaced form is dropped

`a.b.c = 1` yields one pair whose key is the literal `a.b.c`, not a nested
table. That much is at least consistent and a caller can work with it.

`a . b = 1` — legal TOML, the same key — is **discarded entirely**, for the
same reason as case 1: the key scan stops at the space, `_toml_skip_ws` skips
only spaces and tabs so it stops on the `.`, and the missing `=` drops the pair.

### 3. Inline tables have no accessor, and split wrongly inside arrays

`k = { a = 1, b = "x" }` falls to the unquoted-value arm and is captured as the
raw Str `{ a = 1, b = "x" }`. There is no `bayan_toml_inline_parse` to
decompose it, and it is not listed as a subset limit anywhere a caller reads.

Worse, as an array element:

```toml
pts = [ { x = 1, y = 2 }, { x = 3, y = 4 } ]
```

`bayan_toml_array_parse` tracks `[` / `]` depth and quotes but not braces, so it
splits on every comma at depth 1 and returns **four syntactic fragments**
(`{ x = 1`, `y = 2 }`, …) rather than two elements. A caller iterating them gets
garbage that looks structured.

### 4. An empty table is dropped, shifting array-of-table indices

All three flush sites gate on `vec_len(cur_pairs) > 0`, so a header with no
pairs under it emits no section:

```toml
[a]
[b]
x = 1
```

yields one section, named `b`. The more damaging form is an array of tables:

```toml
[[s]]
name = "a"
[[s]]
[[s]]
name = "c"
```

`bayan_toml_get_sections(secs, "s")` returns **two** entries, not three, so
`s[1]` is the third table. An index-based caller silently reads the wrong
record — and an empty entry is exactly the case a defensive caller writes a
test for.

### 5. Duplicate keys are accepted, and the lookup returns the FIRST

```toml
secure = true
secure = false
```

Both pairs are pushed and `bayan_toml_get(pairs, "secure")` returns `true`.

The spec makes a duplicate key an error. Every mainstream implementation that
does not error takes the **last** value, which is also what an editing tool
that appends a corrected line will assume. Returning the first inverts the
result of a security-relevant override — and returning `true` for `secure` when
the file's last word is `false` is the wrong direction to fail in.

### 6. `bayan_toml_is_array` is a byte heuristic, so a bracketed string lies

```toml
format = '[ $hostname ]($style)'
```

`bayan_toml_is_array` inspects the stored value's first non-whitespace byte, by
which point the quotes are gone — so a STRING whose content starts with `[` is
indistinguishable from an array. `bayan_toml_get_array` then returns a bogus
one-element vec instead of 0, and a caller branching on `is_array` takes the
array path for a plain string.

This has always been true for basic strings (`k = "[a]"`), because their quotes
were always stripped. **1.5.3 extended it to literal strings**, since the new
`'...'` branch correctly strips quotes that previously hid the `[`. The value is
a string in both versions; only the classification flipped. The trigger above is
not hypothetical — it is the shape of a starship-style prompt format string.

The fix is the same one items 1-3 want: record the value's kind. There is
nowhere to put it in a 16-byte `{key, value}` pair.

### 7. Header names are stored raw

`[ a ]` produces a section named `` a `` — with the spaces. `["a b"]` produces
one named `"a b"` — with the quotes. There is no trim and no quote-strip, so
`bayan_toml_get_sections(secs, "a")` misses both, silently, and the caller sees
an empty vec rather than an error.

## What a fix has to decide

Not "should these be fixed" — they should — but:

- **Does `bayan_toml_parse` keep returning a flat `vec of {name, pairs}`?**
  Dotted keys and inline tables both want nesting. json.cyr already has a
  tagged value tree that yaml.cyr reuses; a `bayan_toml_v_parse` producing the
  same tree is the obvious shape, and it would give TOML the decoded-value
  escape hatch the flat JSON API has and TOML does not
  ([2026-08-22](2026-08-22-mneme-toml-basic-strings-not-unescaped.md) makes
  this argument).
- **Duplicate keys: last-wins, or an error?** An error needs an error channel
  this parser does not have. Last-wins is a one-line change to `bayan_toml_get`
  and matches the ecosystem, but it is a silent behaviour change for anyone who
  has (deliberately or not) relied on first-wins.
- **Empty tables: emit them, and does that break index-based callers?**
  Emitting is correct and it is what shifts existing indices — in the safe
  direction, but it is still a change.

## Consumer impact

None known to be blocked. mneme's config files use flat keys and `[[vault]]`
tables with at least one pair each, so none of the seven currently bites it —
but item 4 would the first time a vault entry is written with no fields, item 5
the first time a config line is overridden by appending, and item 6 the first
time a value is a literal string starting with `[`.
