# bayan — benchmarks

Captured by `cyrius bench` (`tests/bayan.bcyr`). Re-run it rather than
trusting these numbers: they are a snapshot of one machine, and the point
of recording them is to notice when something moves, not to advertise.

- **Host**: AMD Ryzen 7 5800H with Radeon Graphics
- **Toolchain**: cyrius 6.5.33 · **bayan**: 1.5.0 · x86_64 Linux
- **Timer floor**: 1.322us per clock read, measured and subtracted from every sample

Batched: each figure is a total divided by its iteration count, so the
clock overhead is amortised rather than charged per operation. min == max
because a batch yields a single sample.

## PDF — `bayan_pdf_*` (1.5.0)

| Operation | Avg | Iterations |
|---|---:|---:|
| `pdf_obj_parse (page dict, 97 bytes)` | 3.169us | 10000 |
| `pdf_text_width (120 chars, Helvetica)` | 2.398us | 100000 |
| `pdf_wrap (120 chars into a 200pt column)` | 2.627us | 10000 |
| `pdf_winansi (120 chars, ASCII fast path)` | 1.543us | 100000 |
| `pdf_to_bytes (1 page, 50 text runs)` | 87.319us | 1000 |
| `pdf_parse (1 page, ~6KB)` | 8.499us | 1000 |
| `pdf_extract_text (1 page, 50 runs)` | 241.723us | 1000 |

### Reading these

- **`pdf_obj_parse`** is the object grammar on a real page dictionary — nested
  dicts, an array, and three indirect references, each of which pays the
  three-token `N G R` lookahead with backtracking.
- **`pdf_text_width`** sums 1/1000-em advances and scales once at the end. The
  per-character cost is a two-character base64 decode out of the generated
  metric table; scaling per character instead would be no faster and would lose
  up to one milli-point each.
- **`pdf_wrap`** is the function that replaces mneme's character-count wrap. It
  measures greedily, so it costs roughly one `text_width` pass over the input.
- **`pdf_to_bytes`** serialises a full A4 page of 50 text runs, including the
  cross-reference table and the offset self-check that re-reads every recorded
  offset before returning.
- **`pdf_extract_text`** is the most expensive operation here, and legitimately
  so: it decodes the content stream, resolves the font for each `Tf`, and maps
  every byte through that font's encoding. It is also the one with the most
  headroom left.

## f64 parsing — `bayan_f64_parse` (1.5.7)

- **Toolchain**: cyrius 6.6.6 · **bayan**: 1.5.7 · same host.
- **Method**: this host is noisy (the same row has read 260 ns and 1,022 ns in
  consecutive `cyrius bench` runs), so these are the **minimum of 7 interleaved
  runs** of old and new builds of the same four rows, not one `cyrius bench`.

| Input | Tier | 1.5.6 | 1.5.7 |
|---|---|---:|---:|
| `2.718281828459045` | 1 (Clinger) | 258 ns | 285 ns |
| `1.7976931348623157e308` | 2 (DiyFp) | 414 ns | 479 ns |
| `1.621274542797433e-9` (issue vector 1, a near-tie) | 3 (exact) | 551 ns, **wrong** | 2.54 µs |
| `9007199254740993` (an exact binary tie) | 3 (exact) | 505 ns | 3.99 µs |

### Reading these

- **Tiers 1 and 2 are unchanged within noise.** The window test is a subtract,
  an absolute value and a compare.
- **Tier 3 is the whole cost of the fix, and it lands only where the old
  parser was not safe.** The old 551 ns on the near-tie was a wrong answer.
  The old 505 ns on the exact tie happened to be right, because 2⁵³+1 is a real
  tie and ties-to-even is what the old code did with every `low == halfway`.
- **How often tier 3 runs**, measured by instrumenting a copy: 0.6% of the
  inputs that reach tier 2 for Python shortest-repr strings (a shortest string
  sits near its double, far from a midpoint), and 1.8% for arbitrary 1–25 digit
  decimals. Weighted, that is tens of nanoseconds per parse.
- Tier 3's work is bounded on both axes. Digits: linear in the input, and past
  800 only scanned, never stored. Exponent: the number of shift steps grows
  with |exponent|, but the ±310/330 range gates return Inf or 0 before any
  shifting beyond that, and the scanner saturates the exponent. So `1e99999999`
  costs no more than `1e400`.

## f64 parsing — delegated to the stdlib's `f64_parse_n` (1.5.14)

- **Toolchain**: cyrius 6.7.9 · **bayan**: 1.5.13 vs 1.5.14, both built on the 6.7.9 pin · same host,
  under load from other work (the medians sit within 1% of the minimums, so the gap is not noise).
- **Method**: as above — the **minimum of 9 interleaved runs** of the two builds of `tests/bayan.bcyr`.

| Input | Tier | 1.5.13 | 1.5.14 | Δ |
|---|---|---:|---:|---:|
| `2.718281828459045` | 1 (Clinger) | 132 ns | 172 ns | +30% |
| `1.7976931348623157e308` | 2 (DiyFp) | 227 ns | 321 ns | +41% |
| `1.621274542797433e-9` (a near-tie) | 3 (exact) | 1.27 µs | 1.38 µs | +8.5% |
| `9007199254740993` (an exact binary tie) | 3 (exact) | 1.94 µs | 2.05 µs | +5.6% |

### Reading these

- **The answers did not move; the cost did.** The algorithm is the same (the stdlib core is a
  port of bayan's), so the delta is in how it is reached and how it reads its constants. Measured
  layer by layer in one binary (minimums of 4): tier 1 — 1.5.13's parser 135 ns, the stdlib core
  `_f64_parse_n` 137, `f64_parse_n` 151, `bayan_f64_parse` 171; tier 2 — 221, 282, 299, 345.
- **Tier 2's largest share is the stdlib's table read.** `lib/math.cyr` keeps its 87 cached
  powers as hex text and decodes one (16 hex digits) per lookup: ~50 ns against a ~3 ns load from
  bayan's table, which is built once on first use. The stdlib chose literals so there is nothing
  to initialise or race between threads.
- **The rest is three fronts.** `bayan_f64_parse` scans spaces, sign and the n/N/i/I letter;
  `f64_parse_n`'s strict front scans them again, and the core a third time — ~15–35 ns together.
  bayan keeps its own front because the stdlib's public entry is strict about `nan` / `inf` and
  bayan's readers are not.

## CYML parse — `bayan_cyml_parse` (1.6.0)

- **Toolchain**: cyrius 6.7.11 · **bayan**: 1.5.14 vs 1.6.0, both parsers in one binary · same host,
  load average ~1.7.
- **Method**: the fastest of 9 interleaved rounds × 21 runs of 200 parses per parser, the two
  alternating run by run. The documents are font-shaped (bannermanor's `fonts/*.cyml`): a `[font]`
  header, then *n* entries of an 8-row glyph each.

| Document | Bytes | 1.5.14 | 1.6.0 | 1.6.0 / 1.5.14 |
|---|---:|---:|---:|---:|
| 69 entries (the shape of `block.cyml`) | 6,424 | 75.1 µs | 29.7 µs | 0.39 |
| 95 entries (the size of `clean.cyml`) | 8,816 | 103.6 µs | 41.2 µs | 0.39 |
| 300 entries | 27,676 | 328.7 µs | 129.9 µs | 0.39 |

`tests/bayan.bcyr` gains the 95-entry row: `cyml_parse (95-entry font, 8.8KB)`, 43.6 µs in one
`cyrius bench` run on the same host (418.5 µs under qemu-aarch64).

### Reading these

- **1.5.1 to 1.5.14 tested every byte for a marker, in each of two passes.** 1.5.1 replaced a
  256-slot array, which silently truncated larger documents, with two passes: count the markers,
  allocate exactly, fill. Each pass called `_cyml_is_entries` at every byte offset, and nearly every
  call answered "not a newline". That made the parse about twice 1.4.0's one pass. bannermanor
  measured it as `font_load_file` ~45% slower from bayan 1.5.2 (the first bundle cyrius folded after
  1.5.1).
- **1.6.0 keeps the two passes and the exact allocation.** `_cyml_next_entries` walks to the next
  newline in a tight loop and compares the 12-byte marker only there. The issue measured a one-pass
  variant with a doubling array as faster again (0.22–0.33×). `alloc` is a bump allocator, though,
  so every outgrown array would stay behind, which 1.5.1's exact count was written to avoid.
- **The ratio is flat in document size** because both scans are linear. What changed is the cost
  per byte: a call and a return before, one load and one compare now.
- **Left for 1.6.1:** the `---` searches (each entry's, the single-entry file's, and
  `bayan_cyml_split`) still call `_cyml_is_delim` at every byte. An entry's header is short, so they
  are a small share of these numbers.

### Not yet measured

Compression (the Flate hooks), multi-page documents at scale, and the
real-world reader path — `/usr/share/doc/nasm/nasmdoc.pdf`, 357 pages and 5,706
objects, parses in about 0.17 s but is not a checked-in fixture, so it is not a
gate.
