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


def _divlu_steps(a, b, m):
    """For (a*b mod m) / m by Hacker's Delight 2nd ed. fig. 9-3 (`divlu`),
    per quotient digit: (corrections, estimate reached 2^32, left the
    correction loop because rhat reached 2^32, left it at rhat == 2^32
    EXACTLY where one more retest would have decremented the digit again).

    The last one is the exit only `rhat < 2^32` gets right: a loop that
    retested at rhat == 2^32 (`<=`) would read `rhat << 32` as 0 there."""
    B = 1 << 32
    p = (a % m) * (b % m)
    u1, u0 = p >> 64, p & M64
    s = 64 - m.bit_length()
    v = m << s
    vn1, vn0 = v >> 32, v & (B - 1)
    un32 = ((u1 << s) | (u0 >> (64 - s) if s else 0)) & M64
    un10 = (u0 << s) & M64
    out = []
    num = un32
    for low in (un10 >> 32, un10 & (B - 1)):
        q, rhat = divmod(num, vn1)
        dec, big, rexit, exact = 0, q >= B, False, False
        while q >= B or q * vn0 > B * rhat + low:
            q, rhat, dec = q - 1, rhat + vn1, dec + 1
            if rhat >= B:
                rexit = True
                exact = rhat == B and (q >= B or q * vn0 > low)
                break
        out.append((dec, big, rexit, exact))
        num = num * B + low - q * v
    return out


def mulmod_aimed(quota=8):
    """u64 mulmod triples aimed at the correction steps of the two-digit
    division bayan's aarch64 mulmod uses (1.5.10). Random rows almost never
    reach them: of the 200 MM rows main() emits first, 9 correct the first
    quotient digit, 3 correct the second one twice, and none has a digit
    estimate of 2^32. _divlu_steps only CHOOSES the inputs; the expected
    value is still Python's (a * b) % m.

    Each pick is also emitted with the largest representatives of the same
    residues below 2^64 (bit 63 set whenever m < 2^63), which is what the
    block's unsigned reduction has to undo. The first digit never needs a
    second correction for a product of reduced operands (the proof is in
    src/u128.cyr, above the aarch64 block), so there is no quota for it."""
    rnd = random.Random(15101)
    want = ["d1", "d1-s0", "big1", "d2x2-s0", "d2x2-s>0", "big2-s0", "big2-s>0",
            "rexit1", "rexit2-s0", "rexit2-s>0"]
    got = {t: 0 for t in want}
    rows = []
    for it in range(100000):
        if all(got[t] >= quota for t in want):
            break
        kind = it % 4
        if kind == 0:                                  # operands just below m
            L = rnd.randint(2, 64)
            m = rnd.getrandbits(L) | (1 << (L - 1))
            a = m - 1 - rnd.getrandbits(rnd.randint(1, 40)) % m
            b = m - 1 - rnd.getrandbits(rnd.randint(1, 64)) % m
        elif kind == 1:                                # m just below 2^64
            m = M64 - rnd.getrandbits(rnd.randint(1, 34))
            a = m - 1 - rnd.getrandbits(rnd.randint(1, 34))
            b = m - 1 - rnd.getrandbits(rnd.randint(1, 64)) % m
        elif kind == 2:                                # a*b just below m * 2^32
            L = rnd.randint(34, 64)
            m = rnd.getrandbits(L) | (1 << (L - 1))
            a = (1 << 32) + rnd.getrandbits(rnd.randint(1, L - 33))
            b = (m << 32) // a
        else:                                          # uniform
            L = rnd.randint(2, 64)
            m = rnd.getrandbits(L) | (1 << (L - 1))
            a, b = rnd.getrandbits(64) % m, rnd.getrandbits(64) % m
        if a >= m or b >= m:
            continue
        (d1, g1, r1, _), (d2, g2, r2, _) = _divlu_steps(a, b, m)
        sfx = "-s0" if m >> 63 else "-s>0"             # normalising shift 0 or not
        hit = []
        if d1 == 1: hit.append("d1-s0" if m >> 63 else "d1")
        if g1: hit.append("big1")
        if d2 == 2: hit.append("d2x2" + sfx)
        if g2: hit.append("big2" + sfx)
        if r1: hit.append("rexit1")
        if r2: hit.append("rexit2" + sfx)
        if not any(got[t] < quota for t in hit):
            continue
        for t in hit:
            got[t] += 1
        rows += _with_top_reps(a, b, m)
    assert all(got[t] >= quota for t in want), got
    return rows


def _with_top_reps(a, b, m):
    """(a, b, m), then the same residues at their largest representatives
    below 2^64, when that is a different triple (m near 2^64 may have none)."""
    raw = (a + (M64 - a) // m * m, b + (M64 - b) // m * m, m)
    return [(a, b, m)] + ([raw] if raw != (a, b, m) else [])


def mulmod_rhat_exact(quota=8):
    """u64 mulmod triples that leave a digit's correction loop at rhat == 2^32
    exactly, `quota` each for digit 1 and digit 2, with s = 0 and with s > 0
    (1.5.10). That exit is the one place where the routine's `rhat < 2^32`
    and a `<=` differ, and a random triple reaches it about once in 2^31, so
    mulmod_aimed never does. Built instead: take rhat = 2^32 - vn1 and an
    estimate q-hat large enough to need one correction, which fixes that
    digit's numerator; then find reduced a, b whose normalised product has
    it as its top bits. _divlu_steps confirms each pick, and the expected
    value is still Python's (a * b) % m."""
    B = 1 << 32
    rnd = random.Random(15103)
    rows = []
    for digit in (1, 2):
        for s0 in (True, False):
            got = 0
            while got < quota:
                if s0:
                    m = rnd.getrandbits(64) | (1 << 63)
                else:                                  # s in 1..8
                    L = rnd.randint(56, 63)
                    m = rnd.getrandbits(L) | (1 << (L - 1))
                s = 64 - m.bit_length()
                v = m << s
                vn1, vn0 = v >> 32, v & (B - 1)
                rh = B - vn1                           # rhat + vn1 == 2^32
                if rh >= vn1 or vn0 == 0:
                    continue
                qmin = rh * B // vn0 + 1               # q-hat * vn0 > rh * 2^32
                qmax = (v - 1 - rh) // vn1             # numerator below v
                if qmin > qmax:
                    continue
                num = rnd.randint(qmin, qmax) * vn1 + rh
                if digit == 1:                         # top 64 bits of u << s
                    lo, hi = num << (64 - s), (num + 1) << (64 - s)
                else:                                  # top 96 bits; q1 = k
                    t = rnd.getrandbits(rnd.randint(0, 12)) * v + num
                    lo, hi = t << (32 - s), (t + 1) << (32 - s)
                amin = lo // (m - 1) + 1
                if amin >= m:
                    continue
                a = rnd.randint(amin, min(m - 1, amin + (hi - lo)))
                b = -(-lo // a)
                if b >= m or a * b >= hi:
                    continue
                if not _divlu_steps(a, b, m)[digit - 1][3]:
                    continue
                got += 1
                rows += _with_top_reps(a, b, m)
    return rows


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

    # 1.5.10: aimed mulmod rows, and powmod over 64-bit moduli. Appended, with
    # their own Random instances, so every line above is unchanged.
    for a, b, m in mulmod_aimed() + mulmod_rhat_exact():
        emit("MM", a, b, m, (a * b) % m)
    rnd = random.Random(15102)
    for i in range(32):
        m = rnd.getrandbits(64) | (1 << 63)
        if i % 4 == 0:
            m = M64 - rnd.getrandbits(rnd.randint(1, 34))     # just below 2^64
        base = rnd.getrandbits(64)
        e = rnd.getrandbits(rnd.choice([8, 16, 32, 62]))
        emit("PM", base, e, m, pow(base, e, m))
    # Exponents at or above 2^63. Through 1.5.9 bayan_u64_powmod looped
    # `while (exp > 0)`, a signed test, so for each of these it never ran
    # and returned 1.
    rnd = random.Random(15104)
    for e in (1 << 63, (1 << 63) + 1, M64,
              (1 << 63) | rnd.getrandbits(63), M64 - rnd.getrandbits(32)):
        for m in (1, 2, 3, 1000000007, (1 << 61) - 1, (1 << 63) - 1,
                  1 << 63, (1 << 63) + 1, M64 - 58, M64):
            for base in (3, M64, rnd.getrandbits(64)):
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

    pl = f64_parse_vectors()
    p3 = os.path.join(out_dir, "f64parse.vec")
    with open(p3, "w") as f:
        f.write("\n".join(pl) + "\n")
    print(f"wrote {p3} ({len(pl)} vectors)")
    return 0


# --- dtoa: decimal -> f64 parsing, aimed at the HARD inputs (1.5.7) ---------
#
# f64.vec above holds 328 shortest-repr strings, which is the right kind of test
# and the wrong size: bayan's parser misrounded ~2 in 10^5 of those, so that
# fixture had about a 0.7% chance of containing a failing value, and it did
# not. Volume is the expensive way to see a 10^-5 event. This file aims
# instead: a string that lands within a few units of a rounding midpoint is
# exactly what a misrounding parser gets wrong. Measured at 1.5.7, the old
# parser gets 355 of these 7,736 lines wrong (and 27 of their round-trips).
#
# Format: `<hexbits> <text>`, text to end of line. Expected bits are Python's
# float(text), which is correctly rounded. Its own Random instance, so the
# u128/f64 sequences above are untouched.
import struct as _st
from fractions import Fraction


def _bits(x):
    return _st.unpack("<Q", _st.pack("<d", x))[0]


def _dbl(b):
    return _st.unpack("<d", _st.pack("<Q", b))[0]


def _exact_digits(fr):
    """A dyadic rational as (digits, ex) with fr == int(digits) * 10**ex, no
    trailing zeros. n / 2^k == n * 5^k / 10^k, so the expansion terminates."""
    n, d = fr.numerator, fr.denominator
    k = d.bit_length() - 1
    s = str(n * 5 ** k)
    ex = -k
    t = s.rstrip("0")
    ex += len(s) - len(t)
    return t, ex


def _sci(s, ex):
    """int(s) * 10**ex written as d.ddd...e<n>."""
    e = len(s) - 1 + ex
    if len(s) == 1:
        return f"{s}e{e}"
    return f"{s[0]}.{s[1:]}e{e}"


def _midpoint(b):
    """The exact midpoint between the positive double b and its successor; for
    DBL_MAX the successor is 2^1024, which makes it the overflow threshold."""
    lo = Fraction(_dbl(b))
    hi = Fraction(2) ** 1024 if b == 0x7FEFFFFFFFFFFFFF else Fraction(_dbl(b + 1))
    return (lo + hi) / 2


def f64_parse_vectors():
    rnd = random.Random(1757)
    out = []

    def emit(text):
        out.append(f"{_bits(float(text)):x} {text}")

    # 1. The 27 strings from issue 2026-09-22: bayan_f64_to_json's own output,
    #    which bayan_f64_from_json decoded to a neighbour.
    for t in ["1.621274542797433e-9", "6.28282780197287e+197", "6.056508755376114e-30",
              "5.413192751330368e-12", "2.268960681969623e+176", "1.117384033173974e-30",
              "7.541299607260034e-87", "3.896249127662247e-70", "2.358691174571055e-104",
              "3.602444916265846e-72", "5.292147622049392e-157", "7.220771039042403e+202",
              "9.23786520951051e-303", "2.367847325017567e+234", "2.857588316145595e+118",
              "3.016748988549019e+299", "3.724466833043056e+71", "2.856052993406979e+87",
              "6.88182903070455e-258", "1.129663429840676e+97", "1.663259973966709e-127",
              "1.411708210369543e+200", "2.630392443164597e+103", "3.247638607483073e+214",
              "5.145827025736034e-8", "2.756486299691583e-120", "4.289892475427113e+60"]:
        emit(t)

    # 2. Boundaries: the smallest subnormal and the underflow midpoint below
    #    it, the subnormal/normal seam, 2^53, the overflow threshold.
    for t in ["2e-324", "2.4e-324", "2.5e-324", "3e-324", "4e-324", "4.9e-324", "5e-324",
              "7e-324", "7.4e-324", "7.5e-324", "1e-323", "9.9e-324", "1e-400", "1e-342",
              "1e-343", "2.4703282292062327e-324", "2.4703282292062328e-324",
              "4.9406564584124654e-324", "2.2250738585072011e-308", "2.2250738585072012e-308",
              "2.2250738585072014e-308", "4.4501477170144023e-308", "4.4501477170144028e-308",
              "1.7976931348623157e308", "1.7976931348623158e308", "1.7976931348623159e308",
              "1.797693134862315807e308", "1.797693134862315808e308", "1.8e308", "1e309",
              "9007199254740993", "9007199254740993.0000000000000001",
              "9007199254740992.9999999999", "18446744073709551615", "18446744073709551616",
              "18446744073709551617", "99999999999999999999", "1000000000000000000000",
              "0.30000000000000004440892098500626161694526672363281249",
              "0.30000000000000004440892098500626161694526672363281251",
              "000000000000000000000000000001.5", "0.99999999999999999999999999999999999",
              "1.00000000000000000000000000000000000000001", "5e125", "4.78376e207",
              "996861.0387127432623", "3.55765406988301583688e4"]:
        emit(t)
    # the exact ties at each seam, written in full: they must round to EVEN
    for b in [0, 1, 0x000FFFFFFFFFFFFF, 0x0010000000000000, 0x433FFFFFFFFFFFFF,
              0x4340000000000000, 0x7FEFFFFFFFFFFFFE, 0x7FEFFFFFFFFFFFFF]:
        m = Fraction(_dbl(1)) / 2 if b == 0 else _midpoint(b)
        s, ex = _exact_digits(m)
        emit(_sci(s, ex))

    # 3. Near-midpoint decimals: every double's midpoint cut to 16..19
    #    significant digits, rounded down and up. These sit within a few units
    #    of the 64-bit significand's last bit of a tie: tier 2's whole problem.
    for i in range(700):
        if i < 600:
            b = rnd.randint(0x0010000000000000, 0x7FEFFFFFFFFFFFFE)
        else:
            b = rnd.randint(1, 0x000FFFFFFFFFFFFF)          # subnormal
        s, ex = _exact_digits(_midpoint(b))
        for nd in (16, 17, 18, 19):
            if len(s) <= nd:
                continue
            t = s[:nd]
            tex = ex + len(s) - nd
            emit(_sci(t, tex))
            u = str(int(t) + 1)
            if len(u) == nd:
                emit(_sci(u.rstrip("0") or "0", tex + len(u) - len(u.rstrip("0"))))

    # 4. Exact ties, in full (up to 767 significant digits), and each nudged by
    #    one unit past its last digit: only the full expansion can tell them apart.
    for i in range(64):
        if i < 48:
            b = rnd.randint(0x0010000000000000, 0x7FEFFFFFFFFFFFFE)
        else:
            b = rnd.randint(1, 0x000FFFFFFFFFFFFF)
        s, ex = _exact_digits(_midpoint(b))
        emit(_sci(s, ex))
        emit(_sci(s + "1", ex - 1))
        emit(_sci(str(int(s + "0") - 1), ex - 1))

    # 5. Past the exact tier's 800-digit buffer. A digit beyond 800 that breaks
    #    a tie; a tie zero-padded past 800; a tie -/+ one unit in EXACTLY the
    #    800th digit, which the scaling shifts can carry out of the buffer; and
    #    an integer part longer than the buffer.
    for i in range(16):
        b = rnd.randint(1, 0x0030000000000000) if i % 2 else rnd.randint(0x0010000000000000, 0x7FEFFFFFFFFFFFFE)
        s, ex = _exact_digits(_midpoint(b))
        k = max(1, 820 - len(s))
        emit(_sci(s + "0" * k + "1", ex - k - 1))
        emit(_sci(s + "0" * k, ex - k))
        if len(s) <= 800:
            pad = s + "0" * (800 - len(s))
            pex = ex - (800 - len(s))
            for dv in (1, -1):
                v = str(int(pad) + dv)
                if len(v) == 800:
                    emit(_sci(v.rstrip("0"), pex + len(v) - len(v.rstrip("0"))))
    for i in range(8):
        b = rnd.randint(0x4400000000000000, 0x7FEFFFFFFFFFFFFE)   # midpoint is an integer
        s, ex = _exact_digits(_midpoint(b))
        ip = s + "0" * ex
        pad = 820 - len(ip) + i
        emit(f"{ip}{'0' * pad}.{'1' if i % 2 else ''}e-{pad}")

    # 6. Random 1..25 significant digits over the whole exponent range, in both
    #    scientific and plain notation.
    for _ in range(1500):
        nd = rnd.randint(1, 25)
        d = str(rnd.randint(1, 9)) + "".join(str(rnd.randint(0, 9)) for _ in range(nd - 1))
        emit(_sci(d, rnd.randint(-345, 310) - nd + 1))
    for _ in range(300):
        ip = rnd.randint(0, 10 ** rnd.randint(0, 20))
        fp = "".join(str(rnd.randint(0, 9)) for _ in range(rnd.randint(1, 22)))
        emit(f"{ip}.{fp}")
    return out


if __name__ == "__main__":
    sys.exit(main())
