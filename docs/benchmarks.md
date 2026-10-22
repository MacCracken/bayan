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
  are a small share of these numbers. (Done in 1.6.1; see the next section.)

## CYML `---` search — `bayan_cyml_parse` / `bayan_cyml_split` (1.6.1)

- **Toolchain**: cyrius 6.7.12 · **bayan**: 1.6.0 vs 1.6.1, both modules in one binary · same host,
  **load average ~15**, so the times run high (the 1.6.0 parser's 95-entry font is 50.5 µs here
  against 41.2 µs in the table above). The ratios are interleaved run by run and held across two
  runs (within 0.01).
- **Method**: the fastest of 9 interleaved rounds of 200 calls per module.

| Document | Bytes | 1.6.0 | 1.6.1 | 1.6.1 / 1.6.0 |
|---|---:|---:|---:|---:|
| parse, 95-entry font | 8,816 | 50.5 µs | 46.1 µs | 0.91 |
| parse, 300-entry font | 27,676 | 159.3 µs | 143.5 µs | 0.90 |
| parse, one entry, 200-line header | 6,922 | 54.4 µs | 22.1 µs | 0.40 |
| parse, 50 entries × 20-line headers | 24,768 | 243.4 µs | 131.2 µs | 0.54 |
| `bayan_cyml_split`, 200-line header | 6,922 | 44.1 µs | 10.9 µs | 0.25 |

`tests/bayan.bcyr` gains the single-entry row: `cyml_parse (one entry, 200-line header, 6.9KB)`,
19.8 µs in one `cyrius bench` run (140.1 µs under qemu-aarch64).

### Reading these

- **The same change as 1.6.0's, applied to the delimiter.** `_cyml_next_delim` walks to the next
  newline and compares `---\n` only there. Before, each search called `_cyml_is_delim` at every
  byte.
- **What moves is the share of the input the search covers.** In a font, the delimiter search reads
  one header line per entry, and most of the bytes are glyph rows that only the marker scan reads,
  so the font rows move 9–10%. A single entry's header is nearly the whole document. `split` does
  nothing but the search, so it gains most.
- **The parse hops line to line throughout now.** What is left per byte is the newline walk itself,
  a load and a compare, in each marker pass and in the delimiter search.

## u128 divmod by a 64-bit divisor — `bayan_u128_divmod` (1.6.2)

- **Toolchain**: cyrius 6.7.12 · **bayan**: 1.6.1 vs 1.6.2 · `tests/mulmod_speed.cyr`'s method:
  fastest of 15 alternating ~2 ms windows, divmod against a plain one-multiply-one-divide call in
  the same process. Each call's dividend high word is the previous call's answer.

| Target | Divisor | 1.6.1 | 1.6.2 |
|---|---|---:|---:|
| aarch64 (qemu) | 31-bit | 701× (22.0 µs) | 7.3× (221 ns) |
| aarch64 (qemu) | 62-bit | 667× (21.1 µs) | 7.8× (236 ns) |
| aarch64 (qemu) | 64-bit | 645× (20.4 µs) | 7.9× (240 ns) |
| x86_64 | 31 / 62 / 64-bit | 6.5–6.6× (28 ns) | unchanged |

### Reading these

- **1.0.2 to 1.6.1 divided bit by bit on aarch64.** 1.0.2 put x86's two hardware `div` behind
  `#ifdef CYRIUS_ARCH_X86` (their bytes were trapping on aarch64), and aarch64 fell through to the
  portable loop: 128 shift-subtract rounds of three to five helper calls each. The cost gate had no
  divmod row, so nothing saw it.
- **1.6.2 is the same multiple as x86**, about 7× a bare division. Both are a call, the limb loads
  and the stores around the divide: two `div` on x86, one `udiv` and the two-digit division on
  aarch64. A digit's correction loop runs at most twice.
- **A divisor of 2^64 or more is still bit-serial on every target.** Nothing in bayan divides by
  one; the u64 helpers and the vectors' 64-bit-divisor rows are what the fast paths serve.

## Markdown — `bayan_markdown_*` (1.9.0)

- **Toolchain**: cyrius 6.7.12 · **bayan**: 1.9.0 · `tests/bayan.bcyr`, two runs each. The document
  is note-shaped: 12 sections of a heading, a paragraph with emphasis, a code span, an inline and a
  reference link and an entity, a tight list, a fenced block, a block quote and a GFM table, then
  the 12 definitions; 5,370 bytes. Each document gets a fresh arena (`reset_via`).

| Row | x86_64 | aarch64 (qemu) |
|---|---:|---:|
| `markdown_parse (12-section note, GFM, 5.4KB)` | 556–657 µs | 4.60 ms |
| `markdown_to_html (the same note's tree)` | 124–141 µs | 1.03 ms |
| `markdown parse + render (the same note)` | 683–767 µs | 5.51 ms |

### Reading these

- **8 to 10 MB/s to parse, on x86_64.** A first release, written for the spec's algorithm as the
  reference implementations lay it out, not yet profiled. Rendering costs about a fifth of parsing.
- **The cost grows with the input, on cmark's pathological inputs too.** `tests/markdown_scaling.cyr`
  times six of them at two sizes; the time ratio over the input ratio is 0.5–1.1 on both targets
  (a quadratic path measures about the input ratio, 8). The paths it guards, and what each cost
  before its fix, are in the CHANGELOG [1.9.0] entry.

## TOML into the tree — `bayan_toml_v_parse` (1.11.0)

- **Toolchain**: cyrius 6.7.16 · **bayan**: 1.11.0 · `tests/bayan.bcyr`. The document is
  Cargo-shaped: a package table with an array, 30 inline-table dependencies each holding an array,
  10 `[[bin]]` entries with a trailing comment, a dotted-key profile and a server table with a
  float and a date-time; 3,117 bytes. The tree parse gets a fresh arena each time (`reset_via`).

| Row | x86_64 |
|---|---:|
| `toml_v_parse (Cargo-shaped manifest, 3.1KB)` | ~102 µs |
| `toml_parse, flat (the same manifest)` | ~30 µs |

### Reading these

- **About 30 MB/s through the tree, about 3.4× the flat parse.** The two do different work. The
  tree parse checks every byte against TOML 1.0.0, decodes every string into a copy, splits arrays
  and inline tables into cells, and indexes every key. The flat parse validates nothing and keeps
  arrays and inline tables as raw text.
- **The cost grows with the input.** `tests/toml_scaling.cyr` times eight families at two sizes,
  8× apart; the time ratio over the input ratio is 0.8–1.0 (a quadratic path measures about 8).
  40,000 keys in one table, 429 KB, parse in about 28 ms.

### Not yet measured

Compression (the Flate hooks), multi-page documents at scale, and the
real-world reader path — `/usr/share/doc/nasm/nasmdoc.pdf`, 357 pages and 5,706
objects, parses in about 0.17 s but is not a checked-in fixture, so it is not a
gate.
