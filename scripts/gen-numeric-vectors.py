#!/usr/bin/env python3
"""Generate arithmetic test vectors for u128 and dtoa from an independent oracle.

The expected values come from Python's arbitrary-precision integers and its f64
formatting, NOT from bayan — checking an implementation against itself proves
only that it is self-consistent. This is the method that caught bayan_u256_mul
dropping carries in 1.5.1 (220 of 400 random products were wrong while every
single-limb test passed).

Emits a line-oriented text file that tests/bayan.tcyr reads at run time, so the
vector count can grow without the .tcyr file growing with it.

Format, one operation per line, all values hex, no 0x prefix:

    OP alo ahi blo bhi rlo rhi     for binary ops
    SH alo ahi n    rlo rhi        for shifts
    DV alo ahi blo bhi qlo qhi mlo mhi
    MM a b m r                     u64 mulmod
    PM b e m r                     u64 powmod
    CMP alo ahi blo bhi gt ge lt le

Regenerate with:  python3 scripts/gen-numeric-vectors.py tests/fixtures/numeric
"""
import os
import random
import sys

M128 = (1 << 128) - 1
M64 = (1 << 64) - 1


def parts(v):
    return v & M64, (v >> 64) & M64


def interesting_128():
    """Values that historically break 128-bit code."""
    v = [
        0, 1, 2,
        M64, M64 + 1, M64 - 1,          # the limb boundary, both sides
        1 << 63, (1 << 63) - 1,          # the sign bit of the low limb
        1 << 64, 1 << 127, (1 << 127) - 1,
        M128, M128 - 1,
        0x0123456789ABCDEF,
        0xFFFFFFFFFFFFFFFF0000000000000000,
        0x00000000000000010000000000000000,
        12345, 1000000007,
    ]
    random.seed(15251)
    for _ in range(60):
        v.append(random.getrandbits(random.choice([1, 8, 32, 63, 64, 65, 96, 127, 128])))
    return v


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    vals = interesting_128()
    lines = []

    def emit(*a):
        lines.append(" ".join(f"{x:x}" for x in a[1:]) if False else
                     a[0] + " " + " ".join(f"{x:x}" for x in a[1:]))

    random.seed(999)
    pairs = [(a, b) for a in vals for b in vals]
    random.shuffle(pairs)
    pairs = pairs[:400]

    for a, b in pairs:
        alo, ahi = parts(a)
        blo, bhi = parts(b)
        # wrapping arithmetic, which is what a fixed-width type must do
        for op, r in (("ADD", (a + b) & M128),
                      ("SUB", (a - b) & M128),
                      ("MUL", (a * b) & M128),
                      ("AND", a & b),
                      ("OR",  a | b),
                      ("XOR", a ^ b)):
            rlo, rhi = parts(r)
            emit(op, alo, ahi, blo, bhi, rlo, rhi)
        emit("CMP", alo, ahi, blo, bhi,
             1 if a > b else 0, 1 if a >= b else 0,
             1 if a < b else 0, 1 if a <= b else 0)
        if b != 0:
            q, m = a // b, a % b
            qlo, qhi = parts(q)
            mlo, mhi = parts(m)
            emit("DV", alo, ahi, blo, bhi, qlo, qhi, mlo, mhi)

    # NOT is unary
    for a in vals:
        alo, ahi = parts(a)
        rlo, rhi = parts((~a) & M128)
        emit("NOT", alo, ahi, 0, 0, rlo, rhi)

    # Shifts, including 0, the limb boundary, and >= width. A shift count at or
    # past the width is where fixed-width shift code usually goes wrong,
    # because the hardware shift instruction takes the count modulo the width.
    random.seed(31337)
    for a in vals:
        alo, ahi = parts(a)
        for n in [0, 1, 31, 32, 63, 64, 65, 96, 127, 128, 129, 200, 255]:
            lo, hi = parts((a << n) & M128 if n < 128 else 0)
            emit("SHL", alo, ahi, n, lo, hi)
            lo, hi = parts((a >> n) if n < 128 else 0)
            emit("SHR", alo, ahi, n, lo, hi)

    # u64 modular arithmetic
    random.seed(777)
    for _ in range(200):
        m = random.getrandbits(random.choice([8, 32, 63, 64])) or 1
        a = random.getrandbits(64)
        b = random.getrandbits(64)
        emit("MM", a, b, m, (a * b) % m)
    for _ in range(120):
        m = random.getrandbits(random.choice([8, 32, 63])) or 1
        base = random.getrandbits(64)
        e = random.getrandbits(random.choice([1, 8, 16, 32]))
        emit("PM", base, e, m, pow(base, e, m))

    p = os.path.join(out_dir, "u128.vec")
    with open(p, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {p} ({len(lines)} vectors)")

    # --- dtoa: f64 round-trip -------------------------------------------
    # `bits` is the IEEE-754 double as a u64; `text` is what a correct
    # shortest-round-trip formatter should produce, per Python's repr, which is
    # itself shortest-round-trip.
    import struct
    dl = []
    seed_vals = [
        0.0, 1.0, -1.0, 0.5, -0.5, 2.0, 10.0, 100.0, 0.1, 0.2, 0.3,
        1.5, 3.14159265358979, 2.718281828459045,
        1e-5, 1e-10, 1e10, 1e100, 1e-100, 1e308, 5e-324, 2.2250738585072014e-308,
        123456789.0, 0.000123456, 1234567890123456.0,
        9007199254740992.0, 9007199254740993.0,
        -0.0,
    ]
    random.seed(2718)
    for _ in range(300):
        b = random.getrandbits(64)
        f = struct.unpack("<d", struct.pack("<Q", b))[0]
        if f != f or f in (float("inf"), float("-inf")):
            continue
        seed_vals.append(f)
    for f in seed_vals:
        b = struct.unpack("<Q", struct.pack("<d", f))[0]
        dl.append(f"{b:x} {repr(f)}")
    p2 = os.path.join(out_dir, "f64.vec")
    with open(p2, "w") as f:
        f.write("\n".join(dl) + "\n")
    print(f"wrote {p2} ({len(dl)} vectors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
