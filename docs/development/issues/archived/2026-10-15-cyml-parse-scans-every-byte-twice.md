# `bayan_cyml_parse` scans the document for `[[entries]]` twice, one function call per byte each time, and takes about twice as long as it did before 1.5.1

> **RESOLVED — bayan 1.6.0 (2026-10-15).** The proposed fix landed as arm D: the two passes stay,
> and each finds the next marker with `_cyml_next_entries`, which walks to a newline and compares
> the marker only there (`_cyml_is_entries` is removed). 0.39× 1.5.14's time on 69-, 95- and
> 300-entry fonts (fastest of 9 interleaved rounds, both parsers in one binary). A differential of
> 4,601,648 parses (40,000 random token documents at every prefix length) against the 1.5.14 parser
> found 0 differences on x86_64 and on aarch64 under qemu. Both follow-ups are done:
> `tests/bayan.tcyr` carries this repro's 12 documents plus adjacent markers past byte 0, checked
> from every offset against a copy of the old test, and `tests/bayan.bcyr` has a
> `cyml_parse (95-entry font, 8.8KB)` row. The adjacent-markers note is pinned unchanged and placed
> in roadmap 1.7.0. The `---` search note is placed in 1.6.1.

**Status:** resolved in 1.6.0.
**Placement:** unpinned.
**Discovered:** 2026-10-15, bannermanor 1.8.1 (its issue 0006, open since 2026-08-25: `font_load_file` became ~45% slower when cyrius 6.5.35 brought in bayan 1.5.2).
**Severity:** Low. Performance only: every result is correct. It is the whole of a regression a consumer has carried for two months, and the fix is a local change to one function.
**Affects:** bayan 1.5.1 through 1.5.14, measured on 1.5.14 (HEAD `47a9638`). The two scans are in `bayan_cyml_parse`, `src/cyml.cyr:209` and `:224`. They arrived with 1.5.1's "TWO PASSES" change (`:190`).

## Summary

`bayan_cyml_parse(data, len)` finds the `[[entries]]` markers by calling `_cyml_is_entries(data, len, i)` at every byte offset `i` (`src/cyml.cyr:206-215`). 1.5.1 removed the fixed 256-slot array (rightly: it truncated documents with more entries). To allocate exactly, it counts the markers in one pass and fills the offsets in a second (`:217-232`). The second pass repeats the first, call for call.

So since 1.5.1 the parser makes about two `_cyml_is_entries` calls per input byte. 1.4.0 made one. For bannermanor's `fonts/block.cyml` (4,452 bytes, 69 entries) that is about 7,250 calls against 3,600. The per-byte function call is the dominant cost of the parse.

Measured on bannermanor's four font files, with the compiler, the rest of the stdlib and the input fixed, and only the parser varied:

| parser | `block.cyml` | `clean.cyml` (10,950 B, 95 entries) | vs 1.5.14 |
|---|---|---|---|
| bayan 1.0.1 (one pass, fixed 256 slots) | 41.7 µs | 85.7 µs | 0.48–0.56× |
| **bayan 1.5.14 (two passes, call per byte)** | **77.6 µs** | **179.8 µs** | 1.00× |
| C: 1.5.14 with one pass and a growing array | 40.2 µs | 93.0 µs | 0.52–0.60× |
| **D: 1.5.14, two passes, newline-driven (proposed)** | **29.8 µs** | **60.1 µs** | **0.33–0.43×** |
| E: 1.5.14, one pass, newline-driven | 21.7 µs | 39.2 µs | 0.22–0.33× |

These are the fastest of 9 interleaved rounds of 2,000 parses each, on x86_64 with cyrius 6.7.11 and a loaded host (load average 8–11). Use the ratios, not the absolute times. The ratio column is the range over `block`, `slim`, `big` and `clean`.

- Arm C comes back to 1.0.1's time (within the noise), so the second pass is the whole regression.
- Arm D keeps 1.5.1's design (two passes, an exact allocation, no cap). It drops the per-byte call, and is faster than 1.0.1 ever was.

All five arms return identical docs on all four fonts. Arms B–E also agree on 1.5.1's leading-newline case and on a 300-entry document, which 1.0.1 gets wrong (1 entry instead of 2; 256 entries instead of 300).

## What a consumer sees

bannermanor (`bnrmr`, the banner renderer) parses a font with `bayan_cyml_parse` on every `--font NAME` render, and on every font for `--list-fonts`. Its B2 benchmark, `font_load_file(block.cyml)` (read, parse, decode), was 59 µs on bayan 1.0.1 and 86–91 µs on every bayan since 1.5.2. `bayan_cyml_parse` is 62–65% of it. Holding everything but `lib/bayan.cyr` fixed, the step is ~27 µs, ~45%.

That was measured at 1.5.2. bannermanor bisected the bundles at the time, but `src/cyml.cyr` did not change at 1.5.2. It changed at 1.4.0 (two lines of comment) and at 1.5.1. 1.5.2 was simply the first bundle a cyrius release folded in after 1.5.1. Diffing 1.4.0 → 1.5.1 leaves the two-pass scan as the only change on the parse path. The others are null checks in the accessors, the `_cyml_marker_at` refactor, `bayan_cyml_doc_entry`'s bounds check, and `expand_value` / file-read fixes that the parse does not call.

## Root cause

```cyrius
    var entry_count = 0;
    var i = 0;
    while (i < len) {
        if (_cyml_is_entries(data, len, i) == 1) {        # :209 — a call per byte
            entry_count = entry_count + 1;
            if (i == 0) { i = 12; } else { i = i + 13; }
        } else {
            i = i + 1;
        }
    }
    ...
        entry_starts = alloc(entry_count * 8);
        ...
        while (i < len && w < entry_count) {
            if (_cyml_is_entries(data, len, i) == 1) {    # :224 — the same calls again
```

`_cyml_is_entries` at `pos > 0` checks bounds, loads `data[pos]`, and returns 0 unless it is `\n`. Only at a newline does it call `_cyml_marker_at` for the 12-byte compare. So almost every call answers "not a newline". The work is a function call wrapped around one compare, done for every byte, twice.

A marker can only start at byte 0 or right after a newline. Finding the next newline is a tight loop with no call, and only at a newline is there anything to check.

## Proposed fix

Keep the two passes. Find each next marker with a helper that walks to the next newline and calls `_cyml_marker_at` only there:

```cyrius
# The smallest p >= i at which _cyml_is_entries(data, len, p) would answer 1,
# or len if there is none.
fn _cyml_next_entries(data, len, i): i64 {
    if (i == 0) {
        if (_cyml_marker_at(data, len, 0) == 1) { return 0; }
    }
    var p = i;
    while (p < len) {
        if (load8(data + p) == 10) {
            if (_cyml_marker_at(data, len, p + 1) == 1) { return p; }
        }
        p = p + 1;
    }
    return len;
}
```

and in `bayan_cyml_parse`, both passes become:

```cyrius
    var i = _cyml_next_entries(data, len, 0);
    while (i < len) {
        entry_count = entry_count + 1;                 # pass 2: store64(entry_starts + w * 8, i); w = w + 1;
        if (i == 0) { i = 12; } else { i = i + 13; }
        i = _cyml_next_entries(data, len, i);
    }
```

It returns the same offsets as `_cyml_is_entries` at every byte:
- **`pos > 0`:** `_cyml_is_entries` requires `data[pos] == '\n'` and a marker at `pos + 1`. `_cyml_marker_at`'s own `at + 12 > len` test is the old `pos + 13 > len`.
- **`pos == 0`:** the helper tries the flush marker first, then the loop covers a newline at byte 0.

The skip after a match (`12` at offset 0, `13` elsewhere) is unchanged. So is everything after the scan.

This is arm D above, 0.33–0.43× today's time. Arm E, one pass with a doubling array, is faster again (0.22–0.33×). But with `alloc` being a bump allocator, its growth leaves the outgrown arrays behind, which 1.5.1's exact allocation was written to avoid. D gets most of the gain without giving that up.

## Reproduction

`archived/repros/2026-10-15-cyml-parse-scans-every-byte-twice.cyr` includes `src/cyml.cyr` and carries `_repro_cyml_parse`: `bayan_cyml_parse` copied from 1.5.14 with only the two scans changed, as above. It runs 12 documents through both parsers:
- font-shaped documents of 1, 95 and 300 entries;
- 1.5.1's leading-newline case;
- a marker at byte 0, and adjacent markers;
- no entries, with and without a `---`;
- a marker cut off at end of input;
- CRLF and indented non-markers;
- empty input.

For each, it compares the docs field by field. **The exit code is the number of documents on which they differ**:

```
cyrius build docs/development/issues/archived/repros/2026-10-15-cyml-parse-scans-every-byte-twice.cyr /tmp/cymlscan
/tmp/cymlscan; echo "exit=$?"
```

On 1.5.14 (cyrius 6.7.9, the pin) it exits 0. The two large documents are also timed (fastest of 21 runs of 200 parses):

```
same    font-shaped, 95 entries  (95 entries, 8816 bytes)  bayan 113216 ns, patch 44956 ns, patch/bayan 0.39
same    font-shaped, 300 entries  (300 entries, 27676 bytes)  bayan 369020 ns, patch 147640 ns, patch/bayan 0.40
```

The timings are printed, not gated, because a loaded host moves them. The comparison was checked to fail: deleting the helper's byte-0 marker test makes it report two differing documents.

## Also seen, not changed by the fix

**Adjacent markers.** In `[[entries]]\n[[entries]]\nid=2\n---\nB\n`, the second marker is not found. The skip after a match lands on its `[`, and `_cyml_is_entries` only matches a marker preceded by a newline at the probe position. The marker's own trailing `\n` has been skipped. Both parsers return one entry whose header begins `[[entries]]`. An empty entry is unusual input, so this is a note, not a filing. A fix would make the skip 11 or 12 bytes so the marker's own newline is probed. That changes output, so it belongs with a CHANGELOG entry of its own.

**Every entry's `---` search** (`:295`) also calls a function per byte (`_cyml_is_delim`). It only covers each entry's header, though, which is short (`char = "a"` in a font), so it is a small share of the parse. Not measured separately.

## Follow-ups

- Move the repro's 12 documents into a `tests/bayan.tcyr` group, so the scan's edge cases stay pinned.
- `tests/bayan.bcyr` has no CYML row. A `bayan_cyml_parse` bench on a 4–11 KB multi-entry document would have shown this at 1.5.1.
- bannermanor will move its `[deps.bayan]` tag to the release that carries the fix, and record B2 before and after. Its issue 0006 closes then.
