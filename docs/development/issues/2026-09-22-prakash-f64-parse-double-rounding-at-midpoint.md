# `bayan_f64_from_json` does not invert `bayan_f64_to_json`: the slow path double-rounds at the midpoint

**Filed by**: prakash (optics library; found in its 2.4.9 audit, filed at 2.5.0)
**Date**: 2026-09-22
**Version**: bayan 1.5.6 (as vendored by `cyrius deps` at cyrius 6.6.6);
`_d_decimal_to_f64` confirmed byte-identical in `src/dtoa.cyr` at `main` (fd46aa9)
**Severity**: Low–Medium — silently wrong values (exactly 1 ULP), not a crash. It
contradicts a documented guarantee, and a JSON round-trip that changes the bits
breaks any consumer that hashes, diffs or equality-tests decoded values.
**Status**: Open

## What happens

`src/dtoa.cyr` documents the parser as

> correctly rounded for the vast majority incl. every value bayan_f64_to_json emits

The second half is false. For roughly 2 in 100,000 doubles, `bayan_f64_to_json`
emits a string that is correct — Python's `float()` reads every one of them back
to the original bits — and `bayan_f64_from_json` decodes that string to a
neighbouring double. The encoder is right. The decoder is wrong.

## Reproduction

```cyrius
# repro.cyr — bayan_f64_from_json does not invert bayan_f64_to_json.
# Exit status = number of the four doubles that fail to round-trip (4 today, 0 when fixed).
include "lib/bayan.cyr"

fn say(s): i64 { syscall(1, 1, s, strlen(s)); return 0; }
fn hex(v): i64 {
    var b[20];
    store8(&b, 48); store8(&b + 1, 120);
    for (var i = 0; i < 16; i = i + 1) {
        var d = (v >> ((15 - i) * 4)) & 15;
        if (d < 10) { store8(&b + 2 + i, 48 + d); } else { store8(&b + 2 + i, 87 + d); }
    }
    syscall(1, 1, &b, 18);
    return 0;
}
# 1 if `bits` fails to survive to_json -> from_json.
fn rt_fails(bits): i64 {
    var b[64];
    var n = bayan_f64_to_json(bits, &b);
    store8(&b + n, 0);
    var back = bayan_f64_from_json(&b);
    hex(bits); say("  -> \""); syscall(1, 1, &b, n); say("\"  -> "); hex(back);
    if (back == bits) { say("  ok\n"); return 0; }
    say("  WRONG ("); if (back > bits) { say("+"); } else { say("-"); }
    say("1 ULP)\n");
    return 1;
}
fn main(): i64 {
    alloc_init();
    var bad = 0;
    bad = bad + rt_fails(0x3E1BDA70DB50D19F);   # 1.621274542797433e-9
    bad = bad + rt_fails(0x6900CF5CDB6F39DB);   # 6.28282780197287e+197
    bad = bad + rt_fails(0x39DEB5CC3FA3A223);   # 6.056508755376114e-30
    bad = bad + rt_fails(0x3D97CEB69538C823);   # 5.413192751330368e-12
    return bad;
}
var rc = main();
syscall(60, rc);
```

Observed on x86_64 Linux, cyrius 6.6.6 — **exit 4**:

```
0x3e1bda70db50d19f  -> "1.621274542797433e-9"  -> 0x3e1bda70db50d1a0  WRONG (+1 ULP)
0x6900cf5cdb6f39db  -> "6.28282780197287e+197"  -> 0x6900cf5cdb6f39dc  WRONG (+1 ULP)
0x39deb5cc3fa3a223  -> "6.056508755376114e-30"  -> 0x39deb5cc3fa3a224  WRONG (+1 ULP)
0x3d97ceb69538c823  -> "5.413192751330368e-12"  -> 0x3d97ceb69538c824  WRONG (+1 ULP)
```

Independent check, for each string: Python `struct.unpack('<Q', struct.pack('<d',
float(s)))` returns the left-hand bits.

## Measured

`bayan_f64_to_json` → `bayan_f64_from_json` over 10⁶ random doubles per sampler,
xorshift64 seeded `0x9E3779B97F4A7C15`:

| Sampler | Round-trip failures |
|---|---|
| uniform random bit patterns, all finite positive doubles | **22 / 1,000,000** |
| uniform significand, biased exponent uniform in 970..1076 (\|x\| ≈ 1e-16..1e16) | **1 / 1,000,000** |

(prakash measured 2 in 200,000 in that band in 2.4.9 with a different sampler —
seeded values pushed through its own `rgb_to_json`. The rate depends on the
distribution; it is never zero in any band.)

For all 23 failures above, plus the 4 known values:

- Python's `float()` parses bayan's emitted string back to the **original** bits (27/27).
- **None** takes the Clinger fast path; every one has \|E\| > 22 or W ≥ 2⁵³.
- The error is **exactly 1 ULP**, in **both** directions: 13 high, 14 low.
- The correct double is **always odd** (27/27) and bayan returns its **even**
  neighbour. By chance that is 2⁻²⁷.

## Root cause: double rounding, then a false tie

The slow path forms W·10^E as a 64-bit DiyFp (`_d_mul_hi` against the cached
power, and again against the residual 10^r), then `_d_diyfp_to_f64` rounds those
64 bits to 53. That is two roundings. Replaying the slow path with bayan's own
helpers (`_d_decexp_index`, `_d_sig`, `_d_binexp`, `_d_mul_hi`, `_d_pow10_i`),
**all 27 failures leave the 11 dropped bits EXACTLY at the halfway pattern,
`low == 0x400`**:

```
     14 low=1024 m-want_sig=-1 m_odd=0 decoded-want=-1
     13 low=1024 m-want_sig=0  m_odd=1 decoded-want=1
cases 27: dropped bits EXACTLY halfway 27, above halfway 0
```

The exact decimal values sit **0.33–2.04 units of the 64-bit significand's last
bit** from the midpoint (computed exactly with Python `fractions.Fraction`). So the
first rounding — plus the approximation error of the cached power and the two
rounded `_d_mul_hi` products — lands them ON the midpoint. `_d_diyfp_to_f64` then
takes `low == halfway` as a true tie and rounds half to even. That is right when
the correct answer happens to be the even neighbour, and wrong when it is the odd
one. That is the parity signature above.

A decimal with E < 0 can equal a binary midpoint only if 5^\|E\| divides W, so for
nearly every input the tie branch is taken on a value that is not a tie.

⚠ **Fixing only the `low == 0x400` case would not be enough.** The farthest
failure is 2.04 LSB from the midpoint, so the computation's error exceeds one
LSB. A value 2 LSB on one side can come out 1 LSB on the other, and then no tie
branch runs at all. Nothing in these 27 shows that yet (`above halfway 0`). But the
ambiguity window is at least ±2 LSB wide, not a single point.

## Why the suite does not see it

- `tests/vectors.tcyr` is the right kind of test — a Python oracle, round-trip
  and parse(python) both — but `tests/fixtures/numeric/f64.vec` has **328 lines**.
  At 2.2 × 10⁻⁵ per value, that fixture has about a 0.7% chance of containing a
  failing value.
- `_dtoa_rt` in `tests/bayan.tcyr` checks hand-picked values, and the explicit
  parse pins (`0.5`, `0.333333`, `0.1`, `1e-9`) are all short decimals.

## Suggested fix

This is a report, not a request for a specific shape:

1. **Treat a window around the midpoint as undecided**, not just `low == 0x400`.
   When \|low − 0x400\| ≤ the slow path's error bound (≥ 2 LSB here; derive it from
   the cached-power precision and the two rounded products), decide exactly. Build
   the candidate midpoint M = (2m + 1)·2^(e − 1) and compare W·10^E against it in
   integers (W·5^E·2^(E−e+1) vs 2m+1, moving the negative powers to the other
   side). The integers get large at the exponent extremes, so this needs a bignum
   (Clinger's AlgorithmM, or the `bigcomp` step of David Gay's `strtod`). A ±2 window
   is 5 of the 2048 low-bit patterns, so the exact path runs for about 1 value in
   400. It must be correct, not fast.
2. **Or replace the slow path with Eisel–Lemire** (Lemire, *Number Parsing at a
   Gigabyte per Second*, 2021): 128-bit products against a 128-bit power-of-five
   table, with an explicit test that reports when the result cannot be decided,
   and an exact fallback for those. It is the standard modern answer to exactly
   this defect — Go's `strconv` (1.16+), Rust's `core` float parser and
   `fast_float` all use it.
3. **Either way, add the oracle coverage that would have caught it**: the 27
   vectors below as permanent pins, and a Python-generated round-trip fixture or
   fuzz target large enough to see a 10⁻⁵ event (≥ 10⁶ values; `tests/bayan.fcyr`
   may be the natural home). Until then, change the `src/dtoa.cyr` header claim.

## Test vectors

| # | Correct bits (Python `float()`) | String bayan emits | bayan decodes to | Error |
|---|---|---|---|---|
| 1 | `0x3e1bda70db50d19f` | `1.621274542797433e-9` | `0x3e1bda70db50d1a0` | +1 ULP |
| 2 | `0x6900cf5cdb6f39db` | `6.28282780197287e+197` | `0x6900cf5cdb6f39dc` | +1 ULP |
| 3 | `0x39deb5cc3fa3a223` | `6.056508755376114e-30` | `0x39deb5cc3fa3a224` | +1 ULP |
| 4 | `0x3d97ceb69538c823` | `5.413192751330368e-12` | `0x3d97ceb69538c824` | +1 ULP |
| 5 | `0x648cab0b1af1b70d` | `2.268960681969623e+176` | `0x648cab0b1af1b70c` | -1 ULP |
| 6 | `0x39b6a9ca23916f49` | `1.117384033173974e-30` | `0x39b6a9ca23916f48` | -1 ULP |
| 7 | `0x2e0e00f30598d2b5` | `7.541299607260034e-87` | `0x2e0e00f30598d2b4` | -1 ULP |
| 8 | `0x31858342d5584921` | `3.896249127662247e-70` | `0x31858342d5584920` | -1 ULP |
| 9 | `0x2a6b0c5bbb70c97f` | `2.358691174571055e-104` | `0x2a6b0c5bbb70c980` | +1 ULP |
| 10 | `0x311975ba7e2c8985` | `3.602444916265846e-72` | `0x311975ba7e2c8986` | +1 ULP |
| 11 | `0x1f7d1049467164ed` | `5.292147622049392e-157` | `0x1f7d1049467164ec` | -1 ULP |
| 12 | `0x6a0d7ab053f360c9` | `7.220771039042403e+202` | `0x6a0d7ab053f360ca` | +1 ULP |
| 13 | `0x0139570cafd19a87` | `9.23786520951051e-303` | `0x0139570cafd19a86` | -1 ULP |
| 14 | `0x7097d4a9aa392df5` | `2.367847325017567e+234` | `0x7097d4a9aa392df6` | +1 ULP |
| 15 | `0x5886a9ea130b654b` | `2.857588316145595e+118` | `0x5886a9ea130b654a` | -1 ULP |
| 16 | `0x7e1cd475c5d5ca81` | `3.016748988549019e+299` | `0x7e1cd475c5d5ca80` | -1 ULP |
| 17 | `0x4ecafb685b4391f9` | `3.724466833043056e+71` | `0x4ecafb685b4391f8` | -1 ULP |
| 18 | `0x5216f8adccb560fd` | `2.856052993406979e+87` | `0x5216f8adccb560fc` | -1 ULP |
| 19 | `0x0a8a73e4bca35ef5` | `6.88182903070455e-258` | `0x0a8a73e4bca35ef6` | +1 ULP |
| 20 | `0x541527a5d721736d` | `1.129663429840676e+97` | `0x541527a5d721736c` | -1 ULP |
| 21 | `0x259cd2ac3f0f59b9` | `1.663259973966709e-127` | `0x259cd2ac3f0f59ba` | +1 ULP |
| 22 | `0x697d82300891d01b` | `1.411708210369543e+200` | `0x697d82300891d01c` | +1 ULP |
| 23 | `0x55677d02c359e7b1` | `2.630392443164597e+103` | `0x55677d02c359e7b0` | -1 ULP |
| 24 | `0x6c781e0ef124c88f` | `3.247638607483073e+214` | `0x6c781e0ef124c88e` | -1 ULP |
| 25 | `0x3e6ba05eed8329cd` | `5.145827025736034e-8` | `0x3e6ba05eed8329ce` | +1 ULP |
| 26 | `0x271c78c45296a011` | `2.756486299691583e-120` | `0x271c78c45296a010` | -1 ULP |
| 27 | `0x4c855b5aba134b09` | `4.289892475427113e+60` | `0x4c855b5aba134b0a` | +1 ULP |

Generated with `bayan_f64_to_json` from the correct bits; the "decodes to" column
is `bayan_f64_from_json` of the emitted string. Vectors 1–4 are prakash's known
cases; 5–27 are every failure in the full-range sampler above.

## Consumer status

**prakash is not blocked.** It pins the defect so the fix announces itself:
`tests/hardening.tcyr` asserts that `1.621274542797433e-9` decodes to
`0x3E1BDA70DB50D1A0` — the WRONG, +1 ULP result — and `src/serialize.cyr` carries
a caveat that a float field is not guaranteed to round-trip bit-exactly.

⚠ **prakash action required when this is fixed.** That hardening assertion will
fail on the first `cyrius deps` that vendors the fix. It is meant to: delete it
and the `src/serialize.cyr` caveat, and restore the unqualified round-trip claim.
