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

### Not yet measured

Compression (the Flate hooks), multi-page documents at scale, and the
real-world reader path — `/usr/share/doc/nasm/nasmdoc.pdf`, 357 pages and 5,706
objects, parses in about 0.17 s but is not a checked-in fixture, so it is not a
gate.
