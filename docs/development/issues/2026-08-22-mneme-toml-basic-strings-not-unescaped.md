# TOML basic strings are never unescaped, and there is no API that returns a decoded value

**Filed by**: mneme (Rust → Cyrius port, 1.1.3 toolchain refresh)
**Date**: 2026-08-22
**Version**: bayan 1.5.2 (as vendored by `cyrius deps` at cyrius 6.5.35); confirmed
in `src/toml.cyr` at `main` (b4cb1d8)
**Severity**: Medium — silently wrong values, not a crash. The multiline arm also
truncates.
**Status**: ✅ **Resolved in bayan 1.5.3** (cyrius pin 6.5.36), by **fix 1** —
the spec-correct decode at parse time — plus fix 2's helpers and fix 3's
documentation. See the Resolution section at the end.

> ⚠ **mneme action required.** `_cfg_toml_unesc` in `src/core_config.cyr` must
> be removed, or mneme will double-decode. Its `tests/core_config.tcyr`
> assertions ("toml escape: …") were written to fail loudly at exactly this
> moment; they should now be failing. `_cfg_toml_esc` can go too —
> `bayan_toml_escape` replaces it.

## What happens

`_toml_parse_str` (`src/toml.cyr`) returns the **raw slice between the quotes**.
The backslash is only used to stop an escaped quote from ending the scan; it is
never consumed as an escape:

```cyrius
fn _toml_parse_str(buf, pos, end): Str {
    pos = pos + 1;
    var start = pos;
    while (pos < end) {
        var c = load8(buf + pos);
        if (c == 34) {
            var s = str_new(buf + start, pos - start);   # <- raw bytes, escapes intact
            store64(s + 8, pos - start);
            return s;
        }
        if (c == 10) { return str_from(""); }
        if (c == 92) { pos = pos + 1; }                  # skip, do not decode
        pos = pos + 1;
    }
    return str_from("");
}
```

`src/toml.cyr` contains exactly two references to byte 92, both of that
skip-the-next-byte shape, and no decode step anywhere. So every value reached
through `bayan_toml_parse` / `bayan_toml_parse_file` / `bayan_toml_get` /
`bayan_toml_get_array` carries its backslashes.

Per the TOML spec, `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f`, `\uXXXX` and
`\UXXXXXXXX` in a basic string are escape sequences to be resolved at parse
time, so these are wrong answers rather than a stylistic choice.

**The multiline arm additionally truncates.** `_toml_parse_multiline_q` has no
byte-92 handling at all, so it does not skip an escaped quote while hunting the
closing delimiter. An escaped quote adjacent to the delimiter makes the scan
terminate one byte early and drop a character (see repro 2).

## Reproduction

```cyrius
# repro.cyr — build with `cyrius build repro.cyr /tmp/repro`
include "lib/bayan.cyr"

fn main(): i64 {
    alloc_init();
    # TOML source, literally:
    #   name = "say \"hi\""
    #   path = "C:\\tmp"
    # Spec values:  name = say "hi"      path = C:\tmp
    var src = str_from("name = \"say \\\"hi\\\"\"\npath = \"C:\\\\tmp\"\n");
    var pairs = bayan_toml_section_pairs(vec_get(bayan_toml_parse(src), 0));
    var bad = 0;
    if (str_eq(bayan_toml_get(pairs, "name"), str_from("say \"hi\"")) == 0) { bad = bad + 1; }
    if (str_eq(bayan_toml_get(pairs, "path"), str_from("C:\\tmp")) == 0) { bad = bad + 1; }
    return bad;
}
var rc = main();
syscall(60, rc);
```

Observed on x86_64 Linux, cyrius 6.5.35 — **exit 2**, i.e. both values wrong:

```
name  decoded: say \"hi\"          name  expected: say "hi"
path  decoded: C:\\tmp             path  expected: C:\tmp
```

**Repro 2 — multiline truncation.** Source `s = """he said \"hi\""""`, whose
spec value is `he said "hi"`:

```
decoded:  he said \"hi\
expected: he said "hi"
```

The final `"` is **gone**. The closing-delimiter scan finds three consecutive
quotes starting at the quote of the escaped `\"`, so it stops one byte early.
That is a lost character, not just an undecoded one.

## Why it is worth fixing

The comparison to the JSON surface is not "TOML is inconsistent" — the *flat*
JSON API captures value bytes verbatim too, and `src/json.cyr:91-93` says so
outright ("this flat API does not decode escapes — the tagged-tree parser
does"). That is a deliberate, documented split, and a JSON caller who needs a
decoded value has somewhere to go: `_jp_parse_string_a` resolves `\"`, `\\`,
`\n`, `\r`, `\t`, `\uXXXX` and surrogate pairs at parse time.

The TOML surface has **no such alternative**. There is no tagged-tree TOML
parser — the whole public API is `bayan_toml_parse` / `_parse_file` /
`_get` / `_get_sections` / `_get_array` and the section/pair accessors — so a
caller who needs a spec-correct value has no bayan function that will give one.

And unlike the flat JSON case it is **undocumented**: nothing on
`bayan_toml_parse` or `bayan_toml_get` says values come back raw. The failure is
silent and shaped to look fine — a value with no escapes (the common case)
round-trips perfectly, so the gap only appears once a user types a quote.

`yaml.cyr` and `cyml.cyr` also have no unescape, so this may be a shared
decision rather than a TOML oversight. If so, that is worth stating once,
somewhere a caller will see it.

## Suggested fix

Whichever the maintainer prefers — this is a report, not a request for a
specific shape:

1. **Decode in `_toml_parse_str`.** Resolve the spec's escape set into a fresh
   buffer, the way `_jp_parse_string_a` already does for JSON — the logic is
   the same and could plausibly be shared. This is the spec-correct behaviour
   and what a caller reasonably expects. ⚠ It is a **behaviour change for
   existing consumers**: anyone who has compensated for the raw bytes (see
   below) would double-decode. Worth a CHANGELOG entry loud enough that
   consumers re-check, since the compensating code is invisible from here.

2. **Or add a decoding accessor** — `bayan_toml_get_decoded`, or a
   `bayan_toml_unescape(s)` helper callers can apply themselves — and leave
   `bayan_toml_get` verbatim. This breaks nothing and gives the TOML surface
   the escape hatch the JSON surface already has.

3. **Or, at minimum, document it**, as the flat JSON API does. State on
   `bayan_toml_parse` / `bayan_toml_get` that values are the raw bytes between
   the quotes with escapes unresolved, and that decoding is the caller's job.

The multiline truncation in `_toml_parse_multiline_q` is worth fixing
independently of which of the above is chosen — the closing-delimiter scan
should skip a backslash-escaped byte the way `_toml_parse_str` and
`_toml_str_end` already do, or `\"` next to the delimiter will keep eating a
character regardless of whether escapes are decoded.

## Consumer status

**mneme is not blocked.** As of 1.1.3 it escapes on write and decodes on read in
its own code (`src/core_config.cyr`, `_cfg_toml_esc` / `_cfg_toml_unesc` /
`_cfg_toml_str`) — it had been writing values raw, which produced malformed TOML
whenever a vault name contained a quote, and reading them back through
`bayan_toml_get` cancelled the error out so the round-trip looked correct while
the file on disk was invalid. A conforming parser (checked against Python
`tomllib`) now reads mneme's output correctly.

⚠ That workaround is coupled to this issue: if bayan adopts fix 1, mneme will
**double-decode** until its `_cfg_toml_unesc` is removed. mneme's
`tests/core_config.tcyr` has assertions ("toml escape: …") written to fail
loudly at that moment rather than corrupt data quietly. Anyone taking fix 1
should expect the same shape of coupling in other consumers that have quietly
compensated.

---

## Resolution (bayan 1.5.3, 2026-08-28)

**Fix 1 was taken**, with fix 2's helpers alongside it and fix 3's
documentation on top. Fixes 2 and 3 alone would not have been enough, and the
reason is worth recording: **only the parser can decode this.** A
`bayan_toml_unescape` a caller applies to a returned value cannot work, because
by then the string kind is gone — a basic string resolves escapes and a literal
string must not, so the same bytes decode two different ways depending on which
quote produced them. A caller holding a `Str` from `bayan_toml_get` has no way
to tell which it was.

The report's warning about behaviour change was taken seriously and is answered
in the CHANGELOG, which is deliberately loud, and in a banner at the top of
`src/toml.cyr`.

### What was wrong, measured

Both repros reproduced exactly as filed. Building the whole picture found more
than the report did — nine of ten string forms disagreed with Python's
`tomllib`, and one defect was worse than anything reported:

| Form | bayan 1.5.2 | tomllib |
|---|---|---|
| `"say \"hi\""` | `say \"hi\"` | `say "hi"` |
| `"C:\\tmp"` | `C:\\tmp` | `C:\tmp` |
| `'C:\tmp'` (literal) | `'C:\tmp'` — **with quotes** | `C:\tmp` |
| `'hello'` (literal) | `'hello'` — **with quotes** | `hello` |
| `"""he said \"hi\""""` | `he said \"hi\` — **byte dropped** | `he said "hi"` |
| `"""he said "hi""""` | `he said "hi` | `he said "hi"` |
| `"""\nline1\n"""` | `line1` — **newline dropped** | `line1\n` |
| `'''a''''` | `a` — **byte dropped** | `a'` |
| `"""\<nl>  foo \<nl>  bar"""` | backslashes and indent kept | `foo bar` |

**The single-quoted literal string was the one the report did not reach**, and
it is arguably the worst of them: there was no `'...'` branch at all, so a
literal string fell through to the "unquoted value, read to end of line" arm and
came back **wearing its quotes**. `'hello'` was seven bytes where the spec says
five, and `'C:\tmp'` — the form literal strings exist FOR — was wrong twice
over. Any consumer comparing a literal-string value to an expected string has
been failing that comparison since 1.0.0.

The report's multi-line truncation was confirmed and turned out to have two
independent causes, one of which masks the other: the delimiter scan did not
skip an escaped quote (as filed), AND it took the FIRST three quotes of a run
where TOML says the closer is the LAST three. Fixing only the first leaves
`"""a""""` wrong; fixing only the second leaves `"""a\"""b"""` wrong. Mutation
testing was what separated them — a test for the reported case passes with
either fix in place.

### What changed

- `_toml_parse_str` decodes `\b \t \n \f \r \" \\ \uXXXX \UXXXXXXXX`.
  Unknown escapes are preserved **verbatim** rather than deleted: this parser
  has no error channel, so keeping the bytes beats losing them.
- `_toml_parse_lit` / `_toml_lit_end` — new. Single-line literal strings.
- The multi-line scan skips an escaped byte in a `"""` body, takes the closer
  as the last three of the run, stops trimming the trailing newline, accepts
  CRLF after the opening delimiter, honours the line-ending backslash, and
  normalises a raw CRLF in the body to LF.
- The escaped-quote rule reached all three array scanners — the value capture,
  the element splitter, and the content-end walk — which had the same bug.
- `bayan_toml_unescape` / `bayan_toml_escape` (+ `_a` twins) are public, so
  mneme's `_cfg_toml_unesc` / `_cfg_toml_esc` can both be deleted rather than
  only the reading half.

A value with **no backslash is still a zero-copy view** into the source; only a
string that actually needs decoding pays for a copy. There is a test pinning
that in both directions, because a decode step added carelessly would have
quietly ended the module's defining property for every string in every file.

### How it is kept fixed

`tests/fixtures/toml/strings.vec` — **1,476 vectors whose expected values come
from `tomllib`**, generated by `scripts/gen-toml-vectors.py` and regenerated
byte-identically in CI. This module is exactly why that discipline is worth
paying for twice: it shipped wrong from 1.0.0 to 1.5.2 with a green suite,
because every TOML assertion in that suite had been written by reading bayan's
output and writing it down.

Ten mutations — one per part of the fix — were each confirmed to turn the suite
red. Two initially did not, and closing those gaps found that the hand-written
"mneme repro 2" test could not actually detect the bug it was written for.

### One thing found while fixing it

The new escaped-quote rule in the array capture shipped **without a bound** and
read one byte past the end of a document ending in `a = ["x\`. An adversarial
review of the fix caught it before release. The guard is now a property test:
eight documents, truncated at every length, asserting no key, value or section
name reaches past its source buffer.
