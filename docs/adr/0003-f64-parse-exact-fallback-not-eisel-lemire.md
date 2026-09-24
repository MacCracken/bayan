# 0003 — The f64 parser falls back to an exact decimal, not Eisel–Lemire

**Status**: Accepted
**Date**: 2026-09-23

## Context

`bayan_f64_parse` (and everything that decodes a JSON or YAML float through it)
was documented as "correctly rounded for the vast majority incl. every value
bayan_f64_to_json emits". The second half was false, and so, it turned out, was
the first: prakash reported that about 2 in 10⁵ doubles do not survive
`bayan_f64_to_json → bayan_f64_from_json`
([issue 2026-09-22](../development/issues/archived/2026-09-22-prakash-f64-parse-double-rounding-at-midpoint.md)),
and measuring it against Python's `float()` found three more ways to get a wrong
double (the 20th+ digit discarded, `[2⁻¹⁰⁷⁵, 2⁻¹⁰⁷⁴)` flushed to 0, the overflow
tie read as below itself).

The parser had two tiers: Clinger's exact fast path, then a DiyFp approximation
(the first ≤ 19 digits as a 64-bit significand, times a correctly rounded cached
power of ten, times the exact residual 10^r), rounded to 53 bits. Two rounded
products feed that final rounding, so its 64 bits are an approximation. The
error bound is < 5.01 units of the last bit (derived at `_D_WINDOW`). The
measured maximum is 3.25. Over 389,822 decimals built within a few units of a
midpoint, the approximation lands on the wrong side at a distance of 0 from
halfway 14,759 times, at distance 1 764 times, and at distance 2 172 times.

The constraints that make this a real choice:

- **Cyrius has `i64` only.** Comparisons and `/` are signed and `>>` is logical.
  There is no 128-bit type, so a 64×64→128 multiply is four 32-bit partial products.
- **Everything in `dtoa.cyr` is folded into cyrius's stdlib** (`dist/bayan.cyr` →
  `cyrius/lib/bayan.cyr`), so source size and tables are paid by every consumer.
- **Reentrancy**: the JSON parser's global-cursor bug
  ([2026-06-23](../development/issues/archived/2026-06-23-thoth-json-value-parser-global-cursor-not-thread-safe.md))
  is the reason new parse state goes on the caller's stack, not in globals.

## Decision

**Keep tiers 1 and 2. Let tier 2 answer only outside an explicit error window,
and send everything else to a third, exact tier.**

- Tier 2 returns `_D_UNDECIDED` when its dropped bits are within `_D_WINDOW = 16`
  units of the halfway pattern. That is 3× the derived bound and 5× the
  measured maximum. It also returns `_D_UNDECIDED` below 2⁻¹⁰⁷⁴, where the
  halfway point no longer fits in its 64 bits.
- When more than 19 significant digits were read, the true significand is in
  (W, W+1). Tier 2 answers only if W and W+1 round to the same double.
- Tier 3 is Go strconv's `decimal` (Nigel Tao's "simple decimal conversion"):
  the digits themselves in an 800-digit buffer, scaled into [0.5, 1) by exact
  binary shifts, then rounded once. A `trunc` flag records nonzero digits
  dropped past the buffer and breaks the one tie the stored digits cannot. Its
  state is 1.6 KB of caller stack. It uses no tables and no globals.

## Consequences

- **Positive**: the parser is correctly rounded for every input, and **its
  correctness does not depend on the window being tight**. A window that is too
  large only costs speed. The one way to break it is a window *below* the
  derived bound, and a factor-of-two slip in the derivation still falls inside 16.
- **Positive**: no new tables. The 87-entry 64-bit cached-power table is
  unchanged (and was re-verified against exact rationals: every entry within
  0.4965 ulp).
- **Positive**: two independent algorithms now live in the tree, which makes a
  Python-free self-check possible. `tests/dtoa.fcyr` checks tier 2's answers
  against tier 3 on 200,000 random decimals.
- **Negative**: tier 3 costs 2.5–4 µs where tier 2 costs ~0.3–0.5 µs. It runs for
  ~0.6% of shortest-repr inputs and ~1.8% of arbitrary decimals, which averages
  out to tens of nanoseconds per parse. Its cost is highest on long inputs near
  the subnormal range, but it is linear in the input, not in its exponent.
- **Negative**: ~250 more lines in `dtoa.cyr`, and so in the cyrius fold.
- **Neutral**: `_D_WINDOW` looks like a tuning knob and is not one below 6.
  Its comment carries the derivation, and the mutation record in the 1.5.7
  CHANGELOG shows that window 0 is red on every corpus.

## Alternatives considered

- **Fix only `low == halfway`.** This is the obvious one-line change, and the
  report warned against it. Measured on the near-midpoint sample above, it
  would still leave 936 wrong-side decisions at distances 1 and 2.
- **Eisel–Lemire** (Lemire 2021; Go ≥ 1.16, Rust `core`, `fast_float`). It is the
  standard modern answer, and it lost on cost rather than merit:
  1. It needs a 128-bit table of 5^q for q ∈ [−342, 308]: 1,302 u64 constants
     against today's 87, paid by every cyrius consumer through the fold.
  2. It **still needs an exact fallback**, because it reports inputs it cannot
     decide. Adopting it would shrink tier 3's traffic from ~1% to far less,
     but it would not remove tier 3.
  3. Every 64×64 product becomes four 32-bit partial products on `i64`, which
     is where a carry bug hides (`bayan_u256_mul` dropped carries in 46% of
     products for five releases).

  If profiling ever shows tier 3's rate matters, Eisel–Lemire can replace tier
  2 without touching tier 3. That is the right order for the work.
- **Always use the exact tier.** It is correct and simplest, but about 10×
  slower on every input Clinger does not take, which covers most scientific data.
- **Bignum comparison against a candidate** (Clinger's AlgorithmM, the `bigcomp`
  step of Gay's `strtod`). It verifies tier 2's candidate by comparing W·10^E
  with the midpoint (2m+1)·2^(e−1) in integers. That needs arbitrary-precision
  multiply and shift at ~2,500–4,000 bits (bayan's `bigint` is u256), plus
  separate care at the subnormal and overflow seams, where the candidate's
  exponent and the midpoint's exponent differ. The decimal method needs only
  single-digit arithmetic and computes the answer directly rather than
  checking one.
