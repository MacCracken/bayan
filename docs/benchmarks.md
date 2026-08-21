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

### Not yet measured

Compression (the Flate hooks), multi-page documents at scale, and the
real-world reader path — `/usr/share/doc/nasm/nasmdoc.pdf`, 357 pages and 5,706
objects, parses in about 0.17 s but is not a checked-in fixture, so it is not a
gate.
