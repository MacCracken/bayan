# 0001 — Flate compression via consumer-installed hooks, not a sankoch dependency

**Status**: Accepted
**Date**: 2026-08-21

## Context

`bayan_pdf_*` (1.5.0) needs DEFLATE both ways. `FlateDecode` is the dominant
stream filter in real PDFs — a PDF-1.5 cross-reference stream is itself
compressed, so a reader without it cannot open a modern file at all — and
`FlateEncode` is worth roughly **7.9×** on text content streams, measured on
mneme's real output (10,302 raw bytes → 1,306 compressed).

Cyrius's stdlib already ships the implementation: `lib/sankoch.cyr` provides
`zlib_decompress(src, src_len, dst, dst_cap)` and `zlib_compress(...)`, both
well-tested. Adding `include "lib/sankoch.cyr"` to `src/pdf.cyr` would be one
line.

The constraint that makes this a real decision is bayan's position in the
stack. **bayan folds INTO cyrius's stdlib** — `dist/bayan.cyr` is vendored back
as `cyrius/lib/bayan.cyr` per the sandhi pattern — and cyrius's compiler is
single-pass, so a module may only reference symbols defined earlier. A hard
dependency from a folded module onto another stdlib module constrains the
ordering of the stdlib itself, permanently, in the consuming project rather
than in this one.

Secondary: `[deps].stdlib` is what every consumer of the dist bundle must
supply. Adding `sankoch` charges its weight to every downstream user of
`json` or `u128`, none of whom asked for a compressor.

## Decision

`src/pdf.cyr` does **not** include or depend on `lib/sankoch.cyr`. Compression
is reached through two function pointers the consumer installs:

```cyrius
bayan_pdf_set_inflate(&zlib_decompress);   # fn(src, src_len, dst, dst_cap)
bayan_pdf_set_deflate(&zlib_compress);
```

The hook is invoked with `fncall4`. Both are four integer arguments, which is
squarely inside `fncallN`'s supported envelope — it cannot pass f64, structs by
value, or variadics.

With no hook installed:

- the **writer** emits uncompressed streams and omits `/Filter`. The output is
  still a fully valid PDF, just larger.
- the **reader** fails on a Flate stream with a message naming
  `bayan_pdf_set_inflate`, rather than a generic parse error or, worse, empty
  output.

`[deps].stdlib` is unchanged, and `[lib.pdf]` stays a single-module closure.

## Consequences

- **Positive** — no ordering constraint is imposed on cyrius's stdlib by the
  fold. `[lib.pdf]` is the cleanest sublib in the bundle: 9,356 lines with 9
  stdlib leaves and no sibling module riding along. Consumers who never touch
  PDF pay nothing.
- **Positive** — the consumer chooses the *policy*, not just the
  implementation. That matters for untrusted input: sankoch's ratio-capped
  entry (`zlib_decompress_with_ratio_cap`) has a different arity than the hook,
  so a consumer wanting a decompression-bomb limit installs their own wrapper.
- **Negative** — it does not work out of the box. A caller who forgets the hook
  gets a valid-but-large writer and a reader that refuses compressed files.
  This is mitigated by making the failure loud and specific, never silent, and
  by documenting it in the README and the module header.
- **Negative** — the four-argument signature cannot express the ratio cap, so
  **bayan's own defence against decompression bombs is weaker than sankoch's**:
  it is the destination cap bayan passes plus a per-document total budget
  (`_PDF_MAX_INFTOT`), not a ratio limit. This is written down in the README as
  an obligation on the consumer rather than left to be discovered.
- **Neutral** — the two paths must both be tested, or the untested one rots.
  `tests/bayan.tcyr` covers hook-absent (valid uncompressed output, loud reader
  error) and `tests/pdf_flate.tcyr` covers hook-present, in **separate binaries**
  so neither can mask the other.

## Alternatives considered

- **`include "lib/sankoch.cyr"` directly.** Simplest, and rejected on the fold
  hazard above. Worth noting the failure mode would not be a compile error in
  *this* repo — it would surface later, in cyrius, as a stdlib ordering
  constraint that is expensive to undo once the fold has shipped.
- **Add `sankoch` to `[deps].stdlib`.** Avoids the include but still charges
  every bayan consumer for it, and still leaves the folded module referencing
  symbols the fold cannot guarantee are in scope first.
- **Vendor a DEFLATE implementation into `pdf.cyr`.** Rejected outright: a
  second, less-tested copy of a compressor already in the stdlib, and the exact
  "no consumer hand-rolls a second one" antipattern this library exists to end.
- **Make the hook signature match `zlib_decompress_with_ratio_cap` (5 args)**
  so the ratio cap is expressible. Rejected because it forces every consumer to
  write a shim even for the common trusted-input case; the 4-argument form
  binds directly to `&zlib_decompress`. The cost is documented instead.
