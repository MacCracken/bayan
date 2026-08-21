#!/usr/bin/env python3
"""Generate the PDF fixtures used by tests/bayan.tcyr and the CI oracle step.

Reference files exercise the reader; bad-* files must be REJECTED and exist so
the rejection paths are proven reachable rather than merely written down.

Regenerate with:  python3 scripts/gen-pdf-fixtures.py tests/fixtures/pdf
"""
import sys, zlib, os

OUT = sys.argv[1] if len(sys.argv) > 1 else "."


def build(compress=False, corrupt=None, npages=1):
    text_ops = []
    for p in range(npages):
        ops = (f"BT /F1 24 Tf 72 760 Td (Hello bayan page {p+1}) Tj ET\n"
               f"BT /F1 11 Tf 72 730 Td (The quick brown fox jumps over the lazy dog.) Tj ET\n"
               f"BT /F1 11 Tf 72 714 Td (Escapes: \\(parens\\) and a backslash \\\\ here.) Tj ET\n")
        text_ops.append(ops.encode("latin-1"))

    objs = {}
    kids = " ".join(f"{4+2*p} 0 R" for p in range(npages))
    objs[1] = b"<</Type/Catalog/Pages 2 0 R>>"
    objs[2] = f"<</Type/Pages/Kids [{kids}]/Count {npages}>>".encode()
    objs[3] = b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"
    for p in range(npages):
        objs[4 + 2 * p] = (
            f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
            f"/Contents {5+2*p} 0 R/Resources<</Font<</F1 3 0 R>>>>>>"
        ).encode()
        body = text_ops[p]
        if compress:
            body = zlib.compress(body)
            head = f"<</Length {len(body)}/Filter/FlateDecode>>".encode()
        else:
            head = f"<</Length {len(body)}>>".encode()
        objs[5 + 2 * p] = head + b"\nstream\n" + body + b"\nendstream"

    if corrupt == "length":
        # /Length one byte short — endstream no longer lands where it claims
        k = 5
        d = objs[k]
        i = d.index(b"/Length ") + 8
        j = d.index(b">>", i)
        n = int(d[i:j].split(b"/")[0])
        objs[k] = d[:i] + str(n - 1).encode() + d[j:]

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"

    if corrupt == "xref":
        offsets[3] += 2  # nudge one offset off the object header

    xref_off = len(out)
    maxnum = max(objs)
    size = maxnum + 1
    if corrupt == "size":
        size = maxnum  # /Size must exceed the highest object number
    out += b"xref\n0 " + str(maxnum + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for num in range(1, maxnum + 1):
        if num in offsets:
            out += f"{offsets[num]:010d} 00000 n \n".encode()
        else:
            out += b"0000000000 65535 f \n"
    out += b"trailer<</Size " + str(size).encode() + b"/Root 1 0 R>>\nstartxref\n"
    out += str(xref_off).encode() + b"\n%%EOF\n"
    return bytes(out)


def png_predict(rows, rowlen):
    """Apply PNG Up-predictor (filter type 2) to each row."""
    out = bytearray()
    prev = bytearray(rowlen)
    for r in rows:
        out.append(2)
        out += bytes((r[i] - prev[i]) & 0xFF for i in range(rowlen))
        prev = bytearray(r)
    return bytes(out)


def build15(predictor=True):
    content = (b"BT /F1 24 Tf 72 760 Td (Hello from PDF 1.5) Tj ET\n"
               b"BT /F1 11 Tf 72 730 Td (This page lives behind an xref stream.) Tj ET\n"
               b"BT /F1 11 Tf 72 714 Td (Objects 1, 2, 3 are inside an object stream.) Tj ET\n")
    cstream = zlib.compress(content)

    # Objects 1 (catalog), 2 (pages), 3 (font) go INSIDE an object stream (obj 6).
    inner = {
        1: b"<</Type/Catalog/Pages 2 0 R>>",
        2: b"<</Type/Pages/Kids[4 0 R]/Count 1>>",
        3: b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/WinAnsiEncoding>>",
    }
    hdr, bodies = [], bytearray()
    for num in sorted(inner):
        hdr.append(f"{num} {len(bodies)}")
        bodies += inner[num] + b" "
    hdr_bytes = (" ".join(hdr) + "\n").encode()
    objstm_payload = hdr_bytes + bytes(bodies)
    objstm_z = zlib.compress(objstm_payload)

    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    off = {}

    def add(num, body):
        off[num] = len(out)
        out.extend(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

    # 4 = page dict, 5 = content stream, 6 = the ObjStm, 7 = the XRef stream
    add(4, b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
           b"/Contents 5 0 R/Resources<</Font<</F1 3 0 R>>>>>>")
    add(5, f"<</Length {len(cstream)}/Filter/FlateDecode>>".encode()
           + b"\nstream\n" + cstream + b"\nendstream")
    add(6, f"<</Type/ObjStm/N {len(inner)}/First {len(hdr_bytes)}"
           f"/Length {len(objstm_z)}/Filter/FlateDecode>>".encode()
           + b"\nstream\n" + objstm_z + b"\nendstream")

    # --- the xref stream itself (object 7) ---
    xref_off = len(out)
    size = 8  # objects 0..7
    W = (1, 4, 2)
    rowlen = sum(W)

    def row(t, f2, f3):
        return (t.to_bytes(W[0], "big") + f2.to_bytes(W[1], "big")
                + f3.to_bytes(W[2], "big"))

    rows = [row(0, 0, 65535)]                       # 0: free head
    for n in (1, 2, 3):                             # type 2: inside ObjStm 6
        rows.append(row(2, 6, sorted(inner).index(n)))
    for n in (4, 5, 6):                             # type 1: real offsets
        rows.append(row(1, off[n], 0))
    rows.append(row(1, xref_off, 0))                # 7: the xref stream itself

    raw = b"".join(rows)
    if predictor:
        data = zlib.compress(png_predict(rows, rowlen))
        parms = f"/DecodeParms<</Predictor 12/Columns {rowlen}>>"
    else:
        data = zlib.compress(raw)
        parms = ""

    xd = (f"<</Type/XRef/Size {size}/W[{W[0]} {W[1]} {W[2]}]/Root 1 0 R"
          f"/Filter/FlateDecode{parms}/Length {len(data)}>>").encode()
    out.extend(f"7 0 obj\n".encode() + xd + b"\nstream\n" + data
               + b"\nendstream\nendobj\n")
    out.extend(b"startxref\n" + str(xref_off).encode() + b"\n%%EOF\n")
    return bytes(out)



# --- encoding fixtures: /Differences, base encodings, /ToUnicode -------------
#
# One page per shape, uncompressed throughout, because tests/bayan.tcyr runs
# with NO inflate hook installed (it asserts as much) and a Flate-wrapped
# /ToUnicode would make the encoding tests measure the missing hook instead.

def _simple(objs):
    """Catalog + page tree + a single page whose /Contents is object 5."""
    objs[1] = b"<</Type/Catalog/Pages 2 0 R>>"
    objs[2] = b"<</Type/Pages/Kids [4 0 R]/Count 1>>"
    return objs


def _assemble(objs):
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
    xref_off = len(out)
    size = max(objs) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for n in range(1, size):
        out += ("%010d 00000 n \n" % offsets.get(n, 0)).encode()
    out += (f"trailer<</Size {size}/Root 1 0 R>>\nstartxref\n"
            f"{xref_off}\n%%EOF\n").encode()
    return bytes(out)


def _stream(body):
    return f"<</Length {len(body)}>>".encode() + b"\nstream\n" + body + b"\nendstream"


def build_enc_simple():
    """Three simple fonts: /Differences over WinAnsi, MacRoman, Standard."""
    content = (b"BT /F1 12 Tf 72 760 Td (\x01\x02\x03 ABC \x04) Tj ET\n"
               b"BT /F2 12 Tf 72 740 Td (\x8e\xa5\xd0\xdb) Tj ET\n"
               b"BT /F3 12 Tf 72 720 Td ('q` \xd0 \xae\xaf) Tj ET\n")
    objs = _simple({})
    objs[4] = (b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 5 0 R"
               b"/Resources<</Font<</F1 3 0 R/F2 6 0 R/F3 7 0 R>>>>>>")
    objs[5] = _stream(content)
    objs[3] = (b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica"
               b"/Encoding<</Type/Encoding/BaseEncoding/WinAnsiEncoding"
               b"/Differences[1/eacute/germandbls/Euro 4/fi]>>>>")
    objs[6] = b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/MacRomanEncoding>>"
    objs[7] = b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/StandardEncoding>>"
    return _assemble(objs)


# Exercises every CMap construct the extractor reads: a codespace range that
# sets the code width, a bfchar (including a ligature destination), a bfrange
# in its consecutive form, and a bfrange in its array form carrying both a
# surrogate pair and a two-codepoint destination.
TOUNICODE = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
2 beginbfchar
<0003> <0020>
<0009> <FB01>
endbfchar
2 beginbfrange
<0024> <002D> <0041>
<0040> <0042> [<0058> <D83D DE00> <0059005A>]
endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""

# CIDs spelling "ABC A<fi>X<emoji>YZ J" once mapped through TOUNICODE.
ENC_CIDS = "0024002500260003002400090040004100420003002d"


def build_enc_type0(with_cmap=True):
    objs = _simple({})
    objs[4] = (b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 5 0 R"
               b"/Resources<</Font<</F1 3 0 R>>>>>>")
    objs[5] = _stream(b"BT /F1 12 Tf 72 760 Td <" + ENC_CIDS.encode() + b"> Tj ET\n")
    tu = b"/ToUnicode 7 0 R" if with_cmap else b""
    objs[3] = (b"<</Type/Font/Subtype/Type0/BaseFont/ArialMT/Encoding/Identity-H"
               b"/DescendantFonts[6 0 R]" + tu + b">>")
    objs[6] = (b"<</Type/Font/Subtype/CIDFontType2/BaseFont/ArialMT"
               b"/CIDSystemInfo<</Registry(Adobe)/Ordering(Identity)/Supplement 0>>"
               b"/DW 1000>>")
    if with_cmap:
        objs[7] = _stream(TOUNICODE)
    return _assemble(objs)


def build_badlen(length):
    """A structurally valid file whose object 4 declares an absurd /Length.

    9223372036854775799 is the largest value the number lexer admits (its range
    guard runs before the multiply-accumulate). With an additive reach check
    `start + n > len` this wrapped to a large negative, passed the guard, and
    `load8(buf + e)` then read ~9.2 exabytes below the buffer — a verified
    SIGSEGV from a 400-byte file. The reader must refuse it and stay alive.
    """
    objs = {
        1: b"<</Type/Catalog/Pages 2 0 R>>",
        2: b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        3: b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
           b"/Contents 4 0 R/Resources<<>>>>",
        4: f"<</Length {length}>>".encode() + b"\nstream\nHELLO\nendstream",
    }
    out = bytearray(b"%PDF-1.4\n")
    off = {}
    for k in sorted(objs):
        off[k] = len(out)
        out += f"{k} 0 obj\n".encode() + objs[k] + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 5\n0000000000 65535 f \n"
    for k in range(1, 5):
        out += f"{off[k]:010d} 00000 n \n".encode()
    out += b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n" + str(x).encode() + b"\n%%EOF\n"
    return bytes(out)


CASES = {
    # --- valid: the reader must parse all of these ---
    "ref-good.pdf":      lambda: build(),
    "ref-flate.pdf":     lambda: build(compress=True),
    "ref-3page.pdf":     lambda: build(npages=3),
    "ref-15-objstm.pdf": lambda: build15(predictor=True),
    "ref-15-nopred.pdf": lambda: build15(predictor=False),
    "ref-enc-simple.pdf": lambda: build_enc_simple(),
    "ref-enc-type0.pdf":  lambda: build_enc_type0(with_cmap=True),
    "ref-enc-nocmap.pdf": lambda: build_enc_type0(with_cmap=False),
    # --- invalid: the reader (and the oracle) must REJECT all of these ---
    "bad-xref.pdf":      lambda: build(corrupt="xref"),
    "bad-length.pdf":    lambda: build(corrupt="length"),
    "bad-size.pdf":      lambda: build(corrupt="size"),
    "bad-huge-length.pdf": lambda: build_badlen(9223372036854775799),
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for name, fn in CASES.items():
        p = os.path.join(out, name)
        with open(p, "wb") as f:
            f.write(fn())
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
