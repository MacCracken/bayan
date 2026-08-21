#!/usr/bin/env python3
"""Verify the standard-14 font metric tables checked into src/pdf.cyr.

WHY THIS EXISTS SEPARATELY FROM gen-widths.py. The generator derives the tables
from groff's afmtodit-generated Adobe metrics, so it needs groff installed.
That is fine for regenerating — a rare, deliberate act — but it is the wrong
dependency for a CI gate: the property CI must hold is "the tables in
src/pdf.cyr are correct", and that can be established without groff by decoding
them and checking against values documented independently of it.

So: this script always runs and needs nothing but the Python stdlib.
gen-widths.py's byte-for-byte regeneration diff is a strictly stronger check
and runs additionally wherever groff happens to be available.

Checks performed:
  1. Structure — ten tables, each exactly 448 characters drawn only from the
     base64 alphabet, plus a 96-character WinAnsi block.
  2. Documented Adobe widths — spot values from the Core-14 AFM set.
  3. The five CP1252 holes (0x81 0x8D 0x8F 0x90 0x9D) carry no glyph in any
     WinAnsi-encoded face. Symbol and ZapfDingbats are exempt: they use their
     own built-in encodings, where those codes are real glyphs.
  4. No table has collapsed to mostly zeros — a floor the spot checks alone
     would not catch if they happened to miss the damaged codes.
  5. The WinAnsi 0x80..0x9F block decodes to exactly what Python's own cp1252
     codec says, which is an entirely independent source.

Usage:  check-widths.py [path/to/pdf.cyr]     (default: src/pdf.cyr)
"""
import re
import sys

ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
IDX = {c: i for i, c in enumerate(ALPHA)}

# Suffix in src/pdf.cyr -> PostScript face name. The four Courier faces are not
# tabled; _pdff_width answers them arithmetically.
TABLED = {
    "HELV": "Helvetica",
    "HELV_B": "Helvetica-Bold",
    "HELV_O": "Helvetica-Oblique",
    "HELV_BO": "Helvetica-BoldOblique",
    "TIMES": "Times-Roman",
    "TIMES_B": "Times-Bold",
    "TIMES_I": "Times-Italic",
    "TIMES_BI": "Times-BoldItalic",
    "SYMBOL": "Symbol",
    "ZAPF": "ZapfDingbats",
}

# Documented Adobe Core-14 advance widths, in 1/1000 em. These are stable
# published values, not something read back out of the artifact under test —
# checking a file against itself would prove nothing.
SPOT = [
    ("Helvetica", " ", 278), ("Helvetica", "A", 667), ("Helvetica", "!", 278),
    ("Helvetica", "#", 556), ("Helvetica", "W", 944), ("Helvetica", "i", 222),
    ("Helvetica", "m", 833), ("Helvetica", "0", 556), ("Helvetica", "z", 500),
    ("Helvetica-Bold", "A", 722), ("Helvetica-Bold", " ", 278),
    ("Helvetica-Oblique", "A", 667),
    ("Helvetica-BoldOblique", "A", 722),
    ("Times-Roman", "A", 722), ("Times-Roman", " ", 250),
    ("Times-Roman", "i", 278), ("Times-Roman", "W", 944),
    ("Times-Roman", "#", 500), ("Times-Roman", "m", 778),
    ("Times-Bold", "A", 722), ("Times-Italic", "A", 611),
    ("Times-BoldItalic", "A", 667),
]

# CP1252 has no glyph at these five codes, so every WinAnsi-encoded face must
# report 0 there. This is the ordering trap _pdff_width's
# undefined-before-monospace check exists for: without it the four Courier
# faces answer 600 at exactly these codes and disagree with the other six.
HOLES = [0x81, 0x8D, 0x8F, 0x90, 0x9D]

# Symbol and ZapfDingbats are SYMBOLIC faces: they carry their own built-in
# encoding rather than WinAnsi, so their tables are indexed by that encoding
# and the CP1252 holes are meaningful glyphs there (ZapfDingbats has real
# widths at 0x81 and 0x8D). Excluding them is a fact about the encoding, not a
# waiver — applying the rule to them was this checker's own bug on first run.
SYMBOLIC = {"Symbol", "ZapfDingbats"}


def decode(s):
    """448 base64 chars -> widths for codes 32..255 (index 0 == code 32)."""
    return [IDX[s[2 * k]] * 64 + IDX[s[2 * k + 1]] for k in range(len(s) // 2)]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "src/pdf.cyr"
    src = open(path, encoding="utf-8").read()
    errors = []

    found = dict(re.findall(r'var _PDF_W_(\w+) = "([^"]*)";', src))
    missing = set(TABLED) - set(found)
    extra = set(found) - set(TABLED)
    if missing:
        errors.append(f"missing width tables: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected width tables: {sorted(extra)}")

    widths = {}
    for sfx, raw in found.items():
        name = TABLED.get(sfx)
        if name is None:
            continue
        if len(raw) != 448:
            errors.append(f"{name}: table is {len(raw)} chars, expected 448")
            continue
        bad = sorted({c for c in raw if c not in IDX})
        if bad:
            errors.append(f"{name}: non-base64 characters in table: {bad}")
            continue
        widths[name] = decode(raw)

    # 2. documented Adobe widths
    for face, ch, want in SPOT:
        if face not in widths:
            continue
        got = widths[face][ord(ch) - 32]
        if got != want:
            errors.append(f"{face}[{ch!r}] = {got}, expected {want}")

    # 3 + 4. the Courier family is answered arithmetically, so what we can check
    # here is that the holes are holes in every tabled WinAnsi face.
    for face, w in widths.items():
        if face in SYMBOLIC:
            continue
        for h in HOLES:
            if w[h - 32] != 0:
                errors.append(
                    f"{face}: code {hex(h)} is undefined in CP1252 but has "
                    f"width {w[h - 32]}")

    # A sanity floor: a table that decoded to mostly zeros would pass the spot
    # checks if they happened to miss it.
    for face, w in widths.items():
        nz = sum(1 for x in w if x)
        if nz < 180:
            errors.append(f"{face}: only {nz}/224 codes carry a width — "
                          f"the table looks truncated or corrupt")

    # 5. the WinAnsi high block, against Python's own cp1252 codec
    m = re.search(r'var _PDF_WINANSI_HI = "([^"]*)";', src)
    if not m:
        errors.append("missing _PDF_WINANSI_HI block")
    else:
        blk = m.group(1)
        if len(blk) != 96:
            errors.append(f"_PDF_WINANSI_HI is {len(blk)} chars, expected 96")
        else:
            for k in range(32):
                got = (IDX[blk[3 * k]] * 4096 + IDX[blk[3 * k + 1]] * 64
                       + IDX[blk[3 * k + 2]])
                b = 0x80 + k
                try:
                    want = ord(bytes([b]).decode("cp1252"))
                except UnicodeDecodeError:
                    want = 0
                if got != want:
                    errors.append(
                        f"WinAnsi {hex(b)} decodes to U+{got:04X}, "
                        f"cp1252 says U+{want:04X}")

    if errors:
        print(f"FAIL: {len(errors)} problem(s) in {path}", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print(f"{path}: {len(widths)} width tables + the WinAnsi block verified "
          f"({len(SPOT)} documented Adobe widths, {len(HOLES)} undefined codes "
          f"per face, 32 cp1252 codepoints)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
