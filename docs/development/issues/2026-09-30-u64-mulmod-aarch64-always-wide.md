# `bayan_u64_mulmod` on aarch64 runs the 128-step bit-serial division on every call

**Status:** 🟡 **OPEN** — found by abaco 2.4.9's project audit; not repaired.
**Placement:** unpinned.
**Discovered:** 2026-09-30, abaco 2.4.9 project audit (the aarch64 cross-target pass under
qemu-aarch64, finding `gap-aarch64-cross-target-mulmod-wide-perf`: `is_prime`, `next_prime`,
`prev_prime` and `mod_pow` far slower on aarch64 than on x86_64)
**Severity:** Medium — a silent performance gap, far past the "> 2×" line for Medium in cyrius's
issue severity guide (`docs/development/issues/README.md`). For moduli below 2^63 it is
1,984–2,345× slower than x86_64 under qemu, an estimated 270–340× on hardware. Every answer is
correct.
**Affects:** bayan 1.0.2 – 1.5.9, aarch64 only. Measured on 1.5.9 (`VERSION`; cyrius 6.6.11
pin). The rest of the range is read from the tags, not measured: the aarch64 branch has gone
through the u128 shift-subtract pipeline since 1.0.2 added it (inline through 1.5.1, through
`_u64_mulmod_wide` from 1.5.2), and `src/u128.cyr` is byte-identical from 1.5.2 to 1.5.9.
Consumers get it through cyrius's `lib/bayan.cyr`. The 6.6.11 snapshot bundles 1.5.8 and 6.6.12
bundles 1.5.9, and the mulmod code is the same in both.

## Summary

On aarch64, `bayan_u64_mulmod(a, b, m)` always goes to `_u64_mulmod_wide`. That function forms
the full 128-bit product and then calls `bayan_u128_mod`, whose hardware path is x86-only. So
every call runs 128 rounds of shift-and-subtract, with three to five helper calls per round. It
does this even after both operands are reduced, when the quotient is known to fit in 64 bits and
x86 needs only one `div`. `bayan_u64_powmod` makes up to two such calls per exponent bit. The
answers are right. The time is not.

Per call, reduced operands, bayan 1.5.9. Each figure is the median of three runs of the repro.
Run-to-run spread on the mulmod rows was up to about 5% on both targets. A reviewer's rerun on
the same machine came within 3% of every mulmod, powmod and Miller–Rabin figure:

| row | x86_64 | aarch64 (qemu) | qemu ÷ x86 |
|---|---|---|---|
| integer loop iteration (calibration) | 1.5 ns | 10.3 ns | 6.9× |
| `(a*b) % m` helper call (calibration) | 4.0 ns | 29.4 ns | 7.3× |
| mulmod, 31-bit m | 8.2 ns | 17.3 µs | 2,115× |
| mulmod, 62-bit m | 9.2 ns | 18.3 µs | 1,984× |
| mulmod, 64-bit m | 54.2 ns | 17.7 µs | 327× |
| powmod, 31-bit m, e = m − 1 | 340 ns | 798 µs | 2,345× |
| powmod, 62-bit m, e = m − 1 | 782 ns | 1.74 ms | 2,228× |
| powmod, 64-bit m, e = 2^62 + 1 | 3.61 µs | 1.15 ms | 318× |
| Miller–Rabin(2^53 − 111) ×200, abaco's shape | 1.85 ms | 4.28 s | 2,316× |

The two calibration rows put the emulation cost at 6.9–7.3×. Dividing by it gives an estimated
native gap of 270–340× for every modulus below 2^63. This is an estimate. qemu does not slow
every instruction mix by the same factor, and no aarch64 hardware was available.

The 64-bit row is smaller only because x86_64 is slow there too. For m ≥ 2^63, x86 also takes
`_u64_mulmod_wide`, but its `bayan_u128_divmod` has a hardware `div`, so that costs 54 ns rather
than 17.7 µs. That x86 path is not part of this filing.

Machine: AMD Ryzen 7 5800H, Linux 7.2.7, qemu-aarch64 11.1.1 (user mode). bayan rows use
cyrius 6.6.11, bayan's pin. abaco rows use cyrius 6.6.12, abaco's pin.

## Reproduction

`repros/2026-09-30-u64-mulmod-aarch64-always-wide.cyr` prints two kinds of row. The exit code is
the number of wrong rows.

```
cyrius build --aarch64 docs/development/issues/repros/2026-09-30-u64-mulmod-aarch64-always-wide.cyr /tmp/mulmod_a64
qemu-aarch64 /tmp/mulmod_a64; echo "exit=$?"   # -> 3 on 1.5.9: the three speed rows
cyrius build docs/development/issues/repros/2026-09-30-u64-mulmod-aarch64-always-wide.cyr /tmp/mulmod_x86
/tmp/mulmod_x86; echo "exit=$?"                 # -> 0: x86_64 is the control
```

- **Correctness rows (4).** These compare `bayan_u64_mulmod` with `_u64_mulmod_wide`, which is
  right for every input and is checked against Python by `tests/vectors.tcyr`. The rows are an
  edge grid (22 moduli × 13 × 13 operands, 3,718 triples) and 10,000 seeded random triples for
  each of three classes: m of 1–32 bits, 33–63 bits and 64 bits, half of each class with
  unreduced operands. All four pass today. They are there so that a fix cannot trade
  correctness for speed.
- **Speed rows (3).** Each compares the per-call time of `bayan_u64_mulmod` on reduced operands
  with a plain-Cyrius `(a * b) % m` helper call timed in the same process. That helper is one
  call, one multiply and one divide, the floor any mulmod pays. A row is wrong above 50× that
  floor. Today x86_64 sits at 2×, 2× and 13–14× (31-, 62- and 64-bit m). aarch64 sits at
  584–642× on all three, over seven runs.

aarch64 under qemu on 1.5.9:

```
speed: reduced-operand mulmod vs a plain-Cyrius (a*b)%m call
        integer loop iteration       10.5 ns
        floor: (a*b)%m helper call   29.2 ns
  WRONG mulmod, 31-bit modulus       17454.2 ns/call  = 595x floor
  WRONG mulmod, 62-bit modulus       18141.3 ns/call  = 619x floor
  WRONG mulmod, 64-bit modulus       17603.6 ns/call  = 600x floor
information (not counted)
        powmod, 31-bit m, e = m-1    792548.1 ns/call
        powmod, 62-bit m, e = m-1    1735431.5 ns/call
        powmod, 64-bit m, e = 2^62+1 1137079.9 ns/call
        Miller-Rabin(2^53-111) x200  4262903 us total, 200 of 200 say prime
rows wrong: 3
```

All inputs are integer bit patterns or come from a seeded splitmix64, so the program means the
same thing on every toolchain. It takes about 10 s under qemu.

## What a consumer sees

abaco's `is_prime` (`src/ntheory.cyr`) runs 12 Miller–Rabin witnesses. Each one goes through
`mod_pow`, which calls `bayan_u64_powmod`. `next_prime` and `prev_prime` call `is_prime` once per
candidate. I timed abaco 2.4.9's own code (cyrius 6.6.12, which bundles bayan 1.5.9) on
`is_prime(9007199254740881)` ×200. Over six runs each (three by the author, three on review), it
took **1.95–2.20 ms** on x86_64 and **4.27–4.34 s** on aarch64 under qemu. That is about
2,000–2,100× raw. Divided by the 6.9–7.3× emulation factor above, it gives an estimated
270–310× on hardware. The audit's finding says "~300x slower on aarch64", which agrees.

## Root cause

`src/u128.cyr` at 1.5.9:

- **:536–540**, the aarch64 branch of `bayan_u64_mulmod`. It does
  `result = _u64_mulmod_wide(a, b, m);` unconditionally. By then :517–525 have already
  established 0 ≤ a, b < m < 2^63, so the product is below m².
- **:496–507**, `_u64_mulmod_wide`. It forms the product with `bayan_u128_mul`, which is inline
  arithmetic and cheap, then calls `bayan_u128_mod` → `bayan_u128_divmod`.
- **:327–423**, `bayan_u128_divmod`. The hardware path for a divisor that fits in 64 bits
  (:356–386) sits under `#ifdef CYRIUS_ARCH_X86`. aarch64 always falls to the loop at :391–417.
  That loop runs 128 rounds. Each round calls `_u128_lshr64` twice (:394, :399/:400), then
  `_u64_ugt` or `_u64_uge` (:404–405; `_u64_uge` calls `_u64_ugt` again unless the two are
  equal), and calls `_u64_ugt` once more when it subtracts (:409). That is 384–640 helper calls
  per mulmod. At roughly the 29.4 ns floor-call cost under qemu, that comes to 11–19 µs, which
  is consistent with the 17.3–18.3 µs measured.
- **:548–567**, `bayan_u64_powmod`. It calls `bayan_u64_mulmod` at :559 and :563. For a base
  ≥ 2^63 or a modulus ≥ 2^63 it also calls `_u64_mulmod_wide` directly at :556.

The aarch64 branch never had a fast path. It took its shape from two correctness fixes. 1.0.2
guarded the raw x86 `mul`/`div` bytes, which had been raising SIGILL on aarch64, and gave
aarch64 the u128 pipeline. 1.5.2 fixed the x86 SIGFPE and kept aarch64 on the wide path,
"which is what aarch64 always did" (its comment at :488–489). Neither bayan's CI nor abaco's runs
aarch64. cyrius's VR-01 lib-test gate does, and it caught the 1.0.2 SIGILL, but it checks
pass/fail. The suite's results are correct on aarch64, so no pass/fail gate could see the
timing.

## Earlier filings

- Nothing in bayan's `docs/development/issues/` or `archived/` covers u128 or mulmod. The open
  filing is about json `obj_get`. The seven archived ones cover json, yaml, toml, distlib and
  f64 parsing.
- cyrius `docs/development/issues/archived/stdlib-math-recommendations-from-abaco.md` **P1-1**
  (April 2026, before the carve) asked for a hardware mulmod. It already said: "On aarch64,
  `umulh` + `madd` + software Knuth division (or defer to a helper) can still be faster than
  the current iterative path." The triage accepted the x86 `div` fast path in `u128_mod`, and
  the aarch64 half was never built. This filing is that half. It is filed here because bayan
  has owned `u128` since the 1.0.0 carve.
- abaco's `docs/audit/2026-09-30-audit.md` deferred the finding upstream as
  `gap-aarch64-cross-target-mulmod-wide-perf`. This file is the upstream record.

## Proposed fix (tested)

On aarch64, do the whole mulmod in registers in one `asm` block. It sits at the top of
`bayan_u64_mulmod`, right after the `m == 0` check:

1. `udiv`/`msub` reduce a and b mod m. These are unsigned, so the block takes every input with
   m ≠ 0, including unreduced operands and m ≥ 2^63.
2. `mul` and `umulh` form the 128-bit product hi:lo. Because a, b < m, hi < m.
3. The remainder of hi:lo by m comes from Knuth's Algorithm D with two 32-bit digits. This is
   Hacker's Delight 2nd ed. fig. 9-3 `divlu` (TAOCP vol. 2 §4.3.1), remainder only: normalise
   by `clz`, two `udiv` digit steps, each with its standard correction loop, then shift back.

That is four `udiv` in all, with no loop over bits and no calls. The block uses x0–x15 only and
writes `result` at `[x29, #-32]`. That is local index 3, the slot the x86 block already pins,
and the frame convention `lib/atomic.cyr`'s aarch64 blocks use. Cyrius never enables regalloc
on aarch64 or in a function containing `asm` (cyrius `src/frontend/parse_fn.cyr`), so the slot
is fixed. The machine words came from llvm-mc 22.1.8 (`-triple=aarch64-linux-gnu`) and were read
back with `aarch64-linux-gnu-objdump`. The branch offsets are the assembler's, not hand-counted.
`bayan_u64_powmod` :556 changes to `bayan_u64_mulmod(base, 1, m)`. On x86 that call still takes
the wide path, so x86 behaviour is unchanged. On aarch64 it avoids one bit-serial call per
powmod.

The core, in mnemonics (x0 = a, x1 = b, x2 = m):

```
    udiv  x3, x0, x2 ; msub x0, x3, x2, x0     // a mod m
    udiv  x3, x1, x2 ; msub x1, x3, x2, x1     // b mod m
    mul   x3, x0, x1                            // u0 = lo
    umulh x4, x0, x1                            // u1 = hi < m
    clz   x5, x2 ; lsl x2, x2, x5               // s; v = m << s
    lsr   x6, x2, #32 ; and x7, x2, #0xffffffff // vn1, vn0
    lsl   x8, x4, x5 ; neg x9, x5 ; lsr x9, x3, x9
    cmp   x5, #0 ; csel x9, xzr, x9, eq ; orr x8, x8, x9   // un32 (s = 0 safe)
    lsl   x10, x3, x5 ; lsr x11, x10, #32 ; and x10, x10, #0xffffffff  // un1, un0
    movz  x15, #1, lsl #32                      // b = 2^32
    udiv  x12, x8, x6 ; msub x13, x12, x6, x8   // q1, rhat
L1: cmp x12, x15 ; b.hs L2                      // q1 >= b ?
    mul x14, x12, x7 ; lsl x9, x13, #32 ; orr x9, x9, x11
    cmp x14, x9 ; b.ls L3                       // q1*vn0 <= b*rhat + un1 ?
L2: sub x12, x12, #1 ; add x13, x13, x6 ; cmp x13, x15 ; b.lo L1
L3: lsl x9, x8, #32 ; orr x9, x9, x11 ; msub x9, x12, x2, x9    // un21
    udiv  x12, x9, x6 ; msub x13, x12, x6, x9   // q0, rhat
L4: ... the same correction with un0 ...
L6: lsl x8, x9, #32 ; orr x8, x8, x10 ; msub x8, x12, x2, x8 ; lsr x8, x8, x5
    stur  x8, [x29, #-32]                       // result
```

The full diff against `src/` is at the end of this section.

**Correctness, measured.** Every check below compares against `_u64_mulmod_wide` unless it
says otherwise. All were run on x86_64 and on aarch64 under qemu, with 0 mismatches on both:

- 1,000,000 random triples, with modulus bit length uniform over 1–64 and half of them
  unreduced.
- 3,718 edge-grid triples.
- 10,000 random powmod cases against a powmod built on `_u64_mulmod_wide`.
- 50,000 of the aarch64 triples, dumped and checked against Python's exact `(a * b) % m`.
  This check is independent of bayan.

The harness can fail. With the first correction step's `sub x12, x12, #1` replaced by `nop`, it
reports 92 edge, 3,364 random and 613 powmod mismatches.

**Suite, on the fixed copy.** `cyrius test` runs 4 files, all passing on x86_64 and with
`cyrius test --aarch64`, which runs under qemu:

- `pdf_flate.tcyr`: 19/19
- `vectors.tcyr`: 13/13. That includes 12,334 u128 checks, among them 200 mulmod and 120 powmod
  vectors from Python, with 0 wrong.
- `bayan.tcyr`: 1,281/1,281
- `src/test.cyr`: 3/3

The pristine copy gives the same counts. `cyrius fmt --check src/u128.cyr` passes, `cyrius lint`
reports 0 warnings and `cyrius vet` is clean. `cyrius distlib --all` changes `dist/bayan.cyr`
and `dist/bayan-u128.cyr`, which have to be regenerated with the fix. abaco's
`tests/test_ntheory.tcyr`, built with `--no-deps` against that regenerated bundle, passes 171/171
on both targets. `--no-deps` drops the manifest's stdlib includes, so they are written out at the
top of the test.

**Speed, measured** under qemu (median of three runs):

| row | 1.5.9 | fixed | speed-up |
|---|---|---|---|
| mulmod, 31-bit m | 17.3 µs | 51.1 ns | 339× |
| mulmod, 62-bit m | 18.3 µs | 57.4 ns | 318× |
| mulmod, 64-bit m | 17.7 µs | 62.0 ns | 286× |
| powmod, 31 / 62 / 64-bit m | 798 µs / 1.74 ms / 1.15 ms | 2.36 / 5.52 / 4.18 µs | 339× / 316× / 275× |
| Miller–Rabin(2^53 − 111) ×200 | 4.28 s | 12.75 ms | 336× |
| abaco 2.4.9 `is_prime(9007199254740881)` ×200 | 4.34 s | 13.88 ms | 313× |

With the fix the repro exits 0. aarch64-under-qemu is then 6.2× x86_64 on mulmod (31- and
62-bit m) and 6.9× on the Miller–Rabin row, which is about the emulation factor alone. On x86_64
the patch changes only powmod's unreduced-base line. The x86 repro binaries are the same size
and differ in two bytes, that call's target, so the x86 timings agree with 1.5.9 within
run-to-run noise (31-bit mulmod 8.2–8.6 ns on both).

**Not verified.** It was not run on aarch64 hardware. It was not built for arm64 Mach-O or with
the native aarch64 compiler (`cycc-native-aarch64`), which also define `CYRIUS_ARCH_AARCH64`.
agnos is not an aarch64 target: only cyrius's x86_64 and cx drivers read `CYRIUS_TARGET_AGNOS`.
The block touches only x0–x15. That keeps it clear of x18, which macOS reserves, and of x28,
where cyrius's arm64 Mach-O prologue parks argv. cyrius's release gate runs on aarch64 hardware
(`pi`) and arm64 macOS (`ecb`), per its `docs/development/cycle-discipline.md`, so both can be
checked there.

**Minimum alternative (also tested).** A portable fast path in the existing aarch64 branch,
with no asm:

```
    if (m <= 3037000499) { result = (a * b) % m; }   # isqrt(2^63 - 1): a*b < m^2 < 2^63
    else { result = _u64_mulmod_wide(a, b, m); }
```

It is exact in signed i64, because 3037000499² = 9223372030926249001 < 2^63. It passes the same
1,000,000-triple and edge checks on both targets. It takes the 31-bit row to 62.6 ns (277×), but
the 62- and 64-bit rows are unchanged, so the repro exits 2. **It does not fix abaco's case:**
Miller–Rabin on 2^53 − 111 still takes 4.29 s, because that modulus is above 3.04e9. One
mutation, raising the bound to 3037000999, is caught only by the edge grid: 1 mismatch, at
m = 3037000501.

A third route was considered and not measured: an aarch64 fast path inside `bayan_u128_divmod`
for a 64-bit divisor, in x86's two-step shape. It would also speed up `bayan_u128_div` and
`bayan_u128_mod` themselves. It needs the quotient as well, not only the remainder.

<details><summary>Full diff against <code>src/</code> (tested)</summary>

```diff
--- a/src/u128.cyr
+++ b/src/u128.cyr
@@ -485,9 +485,10 @@
 # Operands are reduced up front when that is provably safe with
 # Cyrius's SIGNED `%` (both operands and the modulus below 2^63),
 # which is the overwhelmingly common case and costs two hardware
-# divisions. Anything else goes through the wide path, which is
-# what aarch64 always did. Callers that already reduce — Miller-
-# Rabin, Pollard rho, RSA — pay only the two extra divisions.
+# divisions. Anything else goes through the wide path. aarch64
+# takes neither: its asm block reduces with the unsigned `udiv`.
+# Callers that already reduce — Miller-Rabin, Pollard rho, RSA —
+# pay only the two extra divisions.
 # The wide fallback: full 128-bit product, then a 128-bit
 # remainder by shift-subtract. Correct for every input including
 # unreduced operands and a modulus at or above 2^63. Kept in its
@@ -508,11 +509,85 @@
 
 fn bayan_u64_mulmod(a, b, m): i64 {
     var result = 0;
-    # NOTE: `result` must stay local index 3 — the x86 asm block below
-    # addresses a/b/m/result at fixed frame offsets. Locals declared AFTER it
-    # take higher indices and do not disturb those slots; a local declared
-    # before it would shift every offset and silently corrupt the block.
+    # NOTE: `result` must stay local index 3 — the x86 and aarch64 asm blocks
+    # below address it at a fixed frame offset ([rbp-32] / [x29, #-32]). Locals
+    # declared AFTER it take higher indices and do not disturb that slot; a
+    # local declared before it would shift every offset and silently corrupt
+    # the blocks.
     if (m == 0) { return 0; }
+    #ifdef CYRIUS_ARCH_AARCH64
+    # aarch64 has no 128/64 divide, so the remainder of the 128-bit product
+    # (mul + umulh) is taken by Knuth's Algorithm D with two 32-bit digits
+    # (TAOCP vol. 2, 4.3.1; Hacker's Delight 2nd ed., fig. 9-3 `divlu`,
+    # remainder only), in registers: four udiv, no loop over bits, no calls.
+    # Operands are reduced first with udiv/msub, which is unsigned, so this
+    # handles every input with m != 0 — unreduced operands and m >= 2^63
+    # included. Through 1.5.9 every aarch64 call went to _u64_mulmod_wide
+    # instead, whose 128-step shift-subtract in bayan_u128_divmod cost
+    # ~17-18 us per call under qemu-aarch64 against ~51-63 ns for this block.
+    # Locals: a(0)=[x29,#-8], b(1)=[x29,#-16], m(2)=[x29,#-24],
+    #         result(3)=[x29,#-32]. Scratch x0-x15 only (caller-saved).
+    asm {
+        param_load(x0, 0);        # a
+        param_load(x1, 1);        # b
+        param_load(x2, 2);        # m
+        0x03; 0x08; 0xC2; 0x9A;   #      udiv x3, x0, x2
+        0x60; 0x80; 0x02; 0x9B;   #      msub x0, x3, x2, x0
+        0x23; 0x08; 0xC2; 0x9A;   #      udiv x3, x1, x2
+        0x61; 0x84; 0x02; 0x9B;   #      msub x1, x3, x2, x1
+        0x03; 0x7C; 0x01; 0x9B;   #      mul x3, x0, x1
+        0x04; 0x7C; 0xC1; 0x9B;   #      umulh x4, x0, x1
+        0x45; 0x10; 0xC0; 0xDA;   #      clz x5, x2
+        0x42; 0x20; 0xC5; 0x9A;   #      lsl x2, x2, x5
+        0x46; 0xFC; 0x60; 0xD3;   #      lsr x6, x2, #32
+        0x47; 0x7C; 0x40; 0x92;   #      and x7, x2, #0xffffffff
+        0x88; 0x20; 0xC5; 0x9A;   #      lsl x8, x4, x5
+        0xE9; 0x03; 0x05; 0xCB;   #      neg x9, x5
+        0x69; 0x24; 0xC9; 0x9A;   #      lsr x9, x3, x9
+        0xBF; 0x00; 0x00; 0xF1;   #      cmp x5, #0x0
+        0xE9; 0x03; 0x89; 0x9A;   #      csel x9, xzr, x9, eq
+        0x08; 0x01; 0x09; 0xAA;   #      orr x8, x8, x9
+        0x6A; 0x20; 0xC5; 0x9A;   #      lsl x10, x3, x5
+        0x4B; 0xFD; 0x60; 0xD3;   #      lsr x11, x10, #32
+        0x4A; 0x7D; 0x40; 0x92;   #      and x10, x10, #0xffffffff
+        0x2F; 0x00; 0xC0; 0xD2;   #      mov x15, #0x100000000
+        0x0C; 0x09; 0xC6; 0x9A;   #      udiv x12, x8, x6
+        0x8D; 0xA1; 0x06; 0x9B;   #      msub x13, x12, x6, x8
+        0x9F; 0x01; 0x0F; 0xEB;   # L1:  cmp x12, x15
+        0xC2; 0x00; 0x00; 0x54;   #      b.cs L2
+        0x8E; 0x7D; 0x07; 0x9B;   #      mul x14, x12, x7
+        0xA9; 0x7D; 0x60; 0xD3;   #      lsl x9, x13, #32
+        0x29; 0x01; 0x0B; 0xAA;   #      orr x9, x9, x11
+        0xDF; 0x01; 0x09; 0xEB;   #      cmp x14, x9
+        0xA9; 0x00; 0x00; 0x54;   #      b.ls L3
+        0x8C; 0x05; 0x00; 0xD1;   # L2:  sub x12, x12, #0x1
+        0xAD; 0x01; 0x06; 0x8B;   #      add x13, x13, x6
+        0xBF; 0x01; 0x0F; 0xEB;   #      cmp x13, x15
+        0xC3; 0xFE; 0xFF; 0x54;   #      b.cc L1
+        0x09; 0x7D; 0x60; 0xD3;   # L3:  lsl x9, x8, #32
+        0x29; 0x01; 0x0B; 0xAA;   #      orr x9, x9, x11
+        0x89; 0xA5; 0x02; 0x9B;   #      msub x9, x12, x2, x9
+        0x2C; 0x09; 0xC6; 0x9A;   #      udiv x12, x9, x6
+        0x8D; 0xA5; 0x06; 0x9B;   #      msub x13, x12, x6, x9
+        0x9F; 0x01; 0x0F; 0xEB;   # L4:  cmp x12, x15
+        0xC2; 0x00; 0x00; 0x54;   #      b.cs L5
+        0x8E; 0x7D; 0x07; 0x9B;   #      mul x14, x12, x7
+        0xA8; 0x7D; 0x60; 0xD3;   #      lsl x8, x13, #32
+        0x08; 0x01; 0x0A; 0xAA;   #      orr x8, x8, x10
+        0xDF; 0x01; 0x08; 0xEB;   #      cmp x14, x8
+        0xA9; 0x00; 0x00; 0x54;   #      b.ls L6
+        0x8C; 0x05; 0x00; 0xD1;   # L5:  sub x12, x12, #0x1
+        0xAD; 0x01; 0x06; 0x8B;   #      add x13, x13, x6
+        0xBF; 0x01; 0x0F; 0xEB;   #      cmp x13, x15
+        0xC3; 0xFE; 0xFF; 0x54;   #      b.cc L4
+        0x28; 0x7D; 0x60; 0xD3;   # L6:  lsl x8, x9, #32
+        0x08; 0x01; 0x0A; 0xAA;   #      orr x8, x8, x10
+        0x88; 0xA1; 0x02; 0x9B;   #      msub x8, x12, x2, x8
+        0x08; 0x25; 0xC5; 0x9A;   #      lsr x8, x8, x5
+        0xA8; 0x03; 0x1E; 0xF8;   #      stur x8, [x29, #-32]
+    }
+    return result;
+    #endif
     var wide = 0;
     if (m < 0) { wide = 1; }        # modulus >= 2^63 read as unsigned
     if (a < 0) { wide = 1; }        # operand  >= 2^63 read as unsigned
@@ -533,11 +608,6 @@
         0x48; 0x89; 0x55; 0xE0;   # mov [rbp-32], rdx   ; result = rem
     }
     #endif
-    #ifdef CYRIUS_ARCH_AARCH64
-    # Portable path — the same helper the wide fallback uses, so both targets
-    # compute the identical answer for every input.
-    result = _u64_mulmod_wide(a, b, m);
-    #endif
     return result;
 }
 
@@ -550,10 +620,11 @@
     if (m == 1) { return 0; }
     var result = 1;
     # `base % m` is the SIGNED remainder, so it is only the unsigned one when
-    # both are below 2^63. Outside that, let mulmod's wide path do the
-    # reduction rather than feeding it a negative value (1.5.2).
+    # both are below 2^63. Outside that, let mulmod do the reduction (its
+    # wide path on x86, unsigned udiv on aarch64) rather than feeding it a
+    # negative value (1.5.2).
     if (base >= 0 && m > 0) { base = base % m; }
-    else { base = _u64_mulmod_wide(base, 1, m); }
+    else { base = bayan_u64_mulmod(base, 1, m); }
     while (exp > 0) {
         if ((exp & 1) == 1) {
             result = bayan_u64_mulmod(result, base, m);
```

</details>

## Consumer-side workaround

None. abaco's `mod_pow` (`src/ntheory.cyr:14–19`) calls `bayan_u64_powmod` and
`bayan_u64_mulmod` directly. `_mr_witness` (:23), `is_prime` (:50), `next_prime` (:98) and
`prev_prime` (:111) all go through it. abaco has no aarch64 CI lane, which is its own audit
finding `gap-aarch64-cross-target-no-aarch64-gate`, so it ships the slow path unmeasured.
