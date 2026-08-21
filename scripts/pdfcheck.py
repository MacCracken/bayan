#!/usr/bin/env python3
"""pdfcheck.py — strict, dependency-free PDF structural validator + text extractor.

bayan's acceptance oracle for `bayan_pdf_*`. Deliberately NOT a lenient reader:
real-world viewers (poppler/mupdf) reconstruct a broken xref by scanning for
`N 0 obj`, which hides exactly the bugs this gate exists to catch (off-by-one
offsets, wrong /Length, stale /Size). Every offset is checked against the byte
it claims to point at.

Uses only the Python stdlib (`zlib` covers FlateDecode).

Usage:
    pdfcheck.py FILE.pdf              # validate; non-zero exit on any error
    pdfcheck.py FILE.pdf --text       # also print extracted text
    pdfcheck.py FILE.pdf --json       # machine-readable report
"""

import sys, re, zlib, json, argparse


class PdfError(Exception):
    pass


# --- tokenizer -------------------------------------------------------------

WS = b"\x00\t\n\x0c\r "
DELIM = b"()<>[]{}/%"


class Lexer:
    def __init__(self, buf, pos=0):
        self.buf = buf
        self.pos = pos

    def skip_ws(self):
        b = self.buf
        n = len(b)
        while self.pos < n:
            c = b[self.pos]
            if c in WS:
                self.pos += 1
            elif c == 0x25:  # '%' comment
                while self.pos < n and b[self.pos] not in b"\r\n":
                    self.pos += 1
            else:
                return

    def parse(self):
        """Parse one PDF object at the cursor."""
        self.skip_ws()
        b = self.buf
        if self.pos >= len(b):
            raise PdfError("unexpected EOF while parsing object")
        c = b[self.pos]

        if c == 0x2F:  # '/' name
            return self._name()
        if c == 0x28:  # '(' literal string
            return self._lit_string()
        if b[self.pos:self.pos + 2] == b"<<":
            return self._dict()
        if c == 0x3C:  # '<' hex string
            return self._hex_string()
        if c == 0x5B:  # '[' array
            return self._array()
        if b[self.pos:self.pos + 4] == b"true":
            self.pos += 4
            return True
        if b[self.pos:self.pos + 5] == b"false":
            self.pos += 5
            return False
        if b[self.pos:self.pos + 4] == b"null":
            self.pos += 4
            return None
        return self._number_or_ref()

    def _name(self):
        b = self.buf
        self.pos += 1
        start = self.pos
        while self.pos < len(b) and b[self.pos] not in WS and b[self.pos] not in DELIM:
            self.pos += 1
        raw = b[start:self.pos]
        # #xx hex escapes are legal inside names
        out = bytearray()
        i = 0
        while i < len(raw):
            if raw[i] == 0x23 and i + 2 < len(raw):
                try:
                    out.append(int(raw[i + 1:i + 3], 16))
                    i += 3
                    continue
                except ValueError:
                    pass
            out.append(raw[i])
            i += 1
        return Name(bytes(out).decode("latin-1"))

    def _lit_string(self):
        b = self.buf
        self.pos += 1
        depth = 1
        out = bytearray()
        while self.pos < len(b):
            c = b[self.pos]
            if c == 0x5C:  # backslash
                self.pos += 1
                if self.pos >= len(b):
                    break
                e = b[self.pos]
                mapping = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
                if e in mapping:
                    out.append(mapping[e])
                    self.pos += 1
                elif e in b"()\\":
                    out.append(e)
                    self.pos += 1
                elif 0x30 <= e <= 0x37:  # octal
                    oct_digits = bytearray()
                    while len(oct_digits) < 3 and self.pos < len(b) and 0x30 <= b[self.pos] <= 0x37:
                        oct_digits.append(b[self.pos])
                        self.pos += 1
                    out.append(int(oct_digits, 8) & 0xFF)
                elif e in b"\r\n":  # line continuation
                    self.pos += 1
                    if e == 0x0D and self.pos < len(b) and b[self.pos] == 0x0A:
                        self.pos += 1
                else:
                    out.append(e)
                    self.pos += 1
                continue
            if c == 0x28:
                depth += 1
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    return bytes(out)
            out.append(c)
            self.pos += 1
        raise PdfError("unterminated literal string")

    def _hex_string(self):
        b = self.buf
        self.pos += 1
        start = self.pos
        while self.pos < len(b) and b[self.pos] != 0x3E:
            self.pos += 1
        if self.pos >= len(b):
            raise PdfError("unterminated hex string")
        digits = bytes(ch for ch in b[start:self.pos] if ch not in WS)
        self.pos += 1
        if len(digits) % 2:
            digits += b"0"
        try:
            return bytes.fromhex(digits.decode("ascii"))
        except ValueError:
            raise PdfError("bad hex string")

    def _array(self):
        self.pos += 1
        out = []
        while True:
            self.skip_ws()
            if self.pos >= len(self.buf):
                raise PdfError("unterminated array")
            if self.buf[self.pos] == 0x5D:  # ']'
                self.pos += 1
                return out
            out.append(self.parse())

    def _dict(self):
        self.pos += 2
        out = {}
        while True:
            self.skip_ws()
            if self.pos >= len(self.buf):
                raise PdfError("unterminated dict")
            if self.buf[self.pos:self.pos + 2] == b">>":
                self.pos += 2
                return out
            key = self.parse()
            if not isinstance(key, Name):
                raise PdfError(f"dict key is not a name: {key!r}")
            out[key.v] = self.parse()

    def _number_or_ref(self):
        b = self.buf
        start = self.pos
        while self.pos < len(b) and b[self.pos] not in WS and b[self.pos] not in DELIM:
            self.pos += 1
        tok = b[start:self.pos]
        if not tok:
            raise PdfError(f"unparsable token at offset {start}: {b[start:start+20]!r}")
        # "N G R" indirect reference lookahead
        if re.fullmatch(rb"\d+", tok):
            save = self.pos
            self.skip_ws()
            s2 = self.pos
            while self.pos < len(b) and b[self.pos] not in WS and b[self.pos] not in DELIM:
                self.pos += 1
            tok2 = b[s2:self.pos]
            if re.fullmatch(rb"\d+", tok2):
                save2 = self.pos
                self.skip_ws()
                if self.pos < len(b) and b[self.pos] == 0x52:  # 'R'
                    self.pos += 1
                    return Ref(int(tok), int(tok2))
                self.pos = save2
            self.pos = save
            return int(tok)
        if re.fullmatch(rb"[+-]?\d+", tok):
            return int(tok)
        if re.fullmatch(rb"[+-]?(\d*\.\d*|\d+)", tok):
            return float(tok)
        raise PdfError(f"unparsable token at offset {start}: {tok!r}")


class Name:
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __repr__(self):
        return f"/{self.v}"

    def __eq__(self, o):
        return isinstance(o, Name) and o.v == self.v

    def __hash__(self):
        return hash(("name", self.v))


class Ref:
    __slots__ = ("num", "gen")

    def __init__(self, num, gen):
        self.num = num
        self.gen = gen

    def __repr__(self):
        return f"{self.num} {self.gen} R"

    def __eq__(self, o):
        return isinstance(o, Ref) and o.num == self.num and o.gen == self.gen

    def __hash__(self):
        return hash(("ref", self.num, self.gen))


class Stream:
    __slots__ = ("d", "raw")

    def __init__(self, d, raw):
        self.d = d
        self.raw = raw


# --- document --------------------------------------------------------------

class Pdf:
    def __init__(self, buf):
        self.buf = buf
        self.errors = []
        self.warnings = []
        self.xref = {}
        self.trailer = {}
        self._cache = {}
        self._parse()

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warnings.append(m)

    def _parse(self):
        buf = self.buf
        if not buf.startswith(b"%PDF-"):
            raise PdfError("missing %PDF- header")
        self.version = buf[5:8].decode("latin-1", "replace")

        if b"%%EOF" not in buf:
            self.err("missing %%EOF marker")

        m = None
        for m in re.finditer(rb"startxref\s+(\d+)", buf):
            pass
        if not m:
            raise PdfError("no startxref found")
        xref_off = int(m.group(1))
        if xref_off <= 0 or xref_off >= len(buf):
            raise PdfError(f"startxref offset {xref_off} out of range (file is {len(buf)} bytes)")

        self._read_xref(xref_off, set())

        if "Root" not in self.trailer:
            self.err("trailer has no /Root")

        # Every xref offset must land exactly on "N G obj" for the right N.
        for num, off in sorted(self.xref.items()):
            if off is None:
                continue
            if isinstance(off, tuple):
                # Type-2 entry: the object lives inside an object stream, so it
                # has no file offset to check. Validate the container instead —
                # its own xref entry is checked by this same loop, and the
                # payload is checked when the object is resolved.
                if off[0] != "instream" or off[1] not in self.xref:
                    self.err(f"object {num}: object-stream container "
                             f"{off[1]} is not in the xref")
                continue
            if off < 0 or off >= len(buf):
                self.err(f"object {num}: xref offset {off} out of range")
                continue
            tail = buf[off:off + 64]
            om = re.match(rb"(\d+)\s+(\d+)\s+obj", tail)
            if not om:
                self.err(
                    f"object {num}: xref offset {off} does not point at an object header "
                    f"(found {tail[:24]!r})"
                )
            elif int(om.group(1)) != num:
                self.err(
                    f"object {num}: xref offset {off} points at object {int(om.group(1))} instead"
                )

        size = self.trailer.get("Size")
        if isinstance(size, int):
            highest = max(self.xref) if self.xref else 0
            if size < highest + 1:
                self.err(f"trailer /Size {size} is <= highest object number {highest} (must be > it)")

    def _read_xref(self, off, seen):
        if off in seen:
            self.err(f"xref loop at offset {off}")
            return
        seen.add(off)
        buf = self.buf
        lx = Lexer(buf, off)
        lx.skip_ws()
        if buf[lx.pos:lx.pos + 4] == b"xref":
            lx.pos += 4
            while True:
                lx.skip_ws()
                if buf[lx.pos:lx.pos + 7] == b"trailer":
                    lx.pos += 7
                    tr = Lexer(buf, lx.pos).parse()
                    if not isinstance(tr, dict):
                        raise PdfError("trailer is not a dictionary")
                    for k, v in tr.items():
                        self.trailer.setdefault(k, v)
                    if "Prev" in tr and isinstance(tr["Prev"], int):
                        self._read_xref(tr["Prev"], seen)
                    return
                hm = re.match(rb"(\d+)\s+(\d+)", buf[lx.pos:lx.pos + 40])
                if not hm:
                    raise PdfError(f"malformed xref subsection header at {lx.pos}")
                start, count = int(hm.group(1)), int(hm.group(2))
                lx.pos += hm.end()
                lx.skip_ws()
                for i in range(count):
                    ent = buf[lx.pos:lx.pos + 20]
                    em = re.match(rb"(\d{10}) (\d{5}) ([nf])", ent)
                    if not em:
                        raise PdfError(
                            f"malformed xref entry for object {start+i} at {lx.pos}: {ent!r}"
                        )
                    # Entries must be exactly 20 bytes: 18 + 2-char EOL.
                    if len(ent) == 20 and ent[18:20] not in (b" \r", b" \n", b"\r\n"):
                        self.warn(
                            f"xref entry for object {start+i} is not 20 bytes "
                            f"with a standard EOL (got {ent[18:20]!r})"
                        )
                    if em.group(3) == b"n":
                        self.xref.setdefault(start + i, int(em.group(1)))
                    lx.pos += 20
        else:
            # cross-reference stream
            obj = self._parse_indirect_at(off)
            if not isinstance(obj, Stream):
                raise PdfError(f"offset {off} is neither an xref table nor an xref stream")
            self._read_xref_stream(obj)
            if "Prev" in obj.d and isinstance(obj.d["Prev"], int):
                self._read_xref(obj.d["Prev"], seen)

    def _read_xref_stream(self, st):
        d = st.d
        for k, v in d.items():
            if k not in ("Length", "Filter", "DecodeParms", "W", "Index", "Type"):
                self.trailer.setdefault(k, v)
        data = self._decode_stream(st, "xref stream")
        w = [int(x) for x in d.get("W", [])]
        if len(w) != 3:
            raise PdfError("xref stream /W is not a 3-element array")
        size = d.get("Size", 0)
        index = d.get("Index", [0, size])
        rowlen = sum(w)
        if rowlen == 0:
            raise PdfError("xref stream /W sums to zero")
        pos = 0
        for i in range(0, len(index), 2):
            start, count = int(index[i]), int(index[i + 1])
            for j in range(count):
                if pos + rowlen > len(data):
                    self.err("xref stream data is shorter than /Index implies")
                    return
                row = data[pos:pos + rowlen]
                pos += rowlen
                f = []
                o = 0
                for width in w:
                    f.append(int.from_bytes(row[o:o + width], "big") if width else None)
                    o += width
                typ = f[0] if w[0] else 1
                if typ == 1:
                    self.xref.setdefault(start + j, f[1])
                elif typ == 2:
                    self.xref.setdefault(start + j, ("instream", f[1], f[2]))

    def _parse_indirect_at(self, off):
        buf = self.buf
        m = re.match(rb"(\d+)\s+(\d+)\s+obj", buf[off:off + 64])
        if not m:
            raise PdfError(f"no object header at offset {off}")
        lx = Lexer(buf, off + m.end())
        val = lx.parse()
        lx.skip_ws()
        if buf[lx.pos:lx.pos + 6] == b"stream":
            if not isinstance(val, dict):
                raise PdfError(f"stream at {off} has a non-dictionary head")
            p = lx.pos + 6
            # EOL after `stream` must be CRLF or LF — never a bare CR.
            if buf[p:p + 2] == b"\r\n":
                p += 2
            elif buf[p:p + 1] == b"\n":
                p += 1
            elif buf[p:p + 1] == b"\r":
                self.err(f"stream at {off}: bare CR after 'stream' keyword (spec requires LF or CRLF)")
                p += 1
            length = val.get("Length")
            if isinstance(length, Ref):
                length = self.resolve(length)
            if not isinstance(length, int):
                raise PdfError(f"stream at {off} has no integer /Length")
            raw = buf[p:p + length]
            if len(raw) != length:
                self.err(f"stream at {off}: /Length {length} runs past EOF")
            after = buf[p + length:p + length + 20]
            # Exactly ONE optional EOL may separate the data from `endstream`;
            # that EOL is not part of the stream. Matching `\s*` here would let
            # an off-by-N /Length slide through, since the swallowed bytes look
            # like separator whitespace. Verified by mutation: /Length - 1 must
            # fail this check.
            if not re.match(rb"(\r\n|\r|\n)?endstream", after):
                self.err(
                    f"stream at {off}: /Length {length} does not reach 'endstream' "
                    f"(found {after[:16]!r}) — the byte count is wrong"
                )
            return Stream(val, raw)
        return val

    def resolve(self, o, depth=0):
        if depth > 64:
            raise PdfError("reference chain too deep")
        if not isinstance(o, Ref):
            return o
        key = (o.num, o.gen)
        if key in self._cache:
            return self._cache[key]
        ent = self.xref.get(o.num)
        if ent is None:
            self.err(f"reference to object {o.num} which is not in the xref")
            return None
        self._cache[key] = None  # cycle guard
        if isinstance(ent, tuple) and ent[0] == "instream":
            val = self._from_objstm(ent[1], ent[2], o.num)
        else:
            val = self._parse_indirect_at(ent)
        self._cache[key] = val
        return self.resolve(val, depth + 1) if isinstance(val, Ref) else val

    def _from_objstm(self, container, idx, want):
        st = self.resolve(Ref(container, 0))
        if not isinstance(st, Stream):
            self.err(f"object stream {container} is not a stream")
            return None
        data = self._decode_stream(st, f"object stream {container}")
        n = self.resolve(st.d.get("N"))
        first = self.resolve(st.d.get("First"))
        if not isinstance(n, int) or not isinstance(first, int):
            self.err(f"object stream {container} missing /N or /First")
            return None
        hdr = Lexer(data, 0)
        pairs = []
        for _ in range(n):
            a = hdr.parse()
            b = hdr.parse()
            pairs.append((a, b))
        for num, rel in pairs:
            if num == want:
                return Lexer(data, first + rel).parse()
        self.err(f"object {want} not found inside object stream {container}")
        return None

    def _decode_stream(self, st, what="stream"):
        data = st.raw
        filt = self.resolve(st.d.get("Filter"))
        if filt is None:
            return data
        filters = filt if isinstance(filt, list) else [filt]
        parms = self.resolve(st.d.get("DecodeParms"))
        parms_list = parms if isinstance(parms, list) else [parms]
        for i, f in enumerate(filters):
            f = self.resolve(f)
            nm = f.v if isinstance(f, Name) else str(f)
            if nm in ("FlateDecode", "Fl"):
                try:
                    data = zlib.decompress(data)
                except zlib.error:
                    try:
                        data = zlib.decompressobj().decompress(data)
                        self.warn(f"{what}: FlateDecode stream is truncated but partially recoverable")
                    except zlib.error as e:
                        self.err(f"{what}: FlateDecode failed ({e})")
                        return b""
            elif nm in ("ASCIIHexDecode", "AHx"):
                hx = bytes(c for c in data.split(b">")[0] if c not in WS)
                if len(hx) % 2:
                    hx += b"0"
                data = bytes.fromhex(hx.decode("ascii"))
            elif nm in ("ASCII85Decode", "A85"):
                import base64 as _b64
                body = data.strip()
                if body.startswith(b"<~"):
                    body = body[2:]
                data = _b64.a85decode(body, adobe=False, ignorechars=WS.decode("latin-1"))
            else:
                self.warn(f"{what}: unsupported filter /{nm}; leaving data encoded")
                return data
            p = parms_list[i] if i < len(parms_list) else None
            p = self.resolve(p)
            if isinstance(p, dict) and self.resolve(p.get("Predictor", 1)) not in (None, 1):
                data = self._unpredict(data, p)
        return data

    def _unpredict(self, data, p):
        pred = self.resolve(p.get("Predictor", 1))
        colors = self.resolve(p.get("Colors", 1)) or 1
        bpc = self.resolve(p.get("BitsPerComponent", 8)) or 8
        columns = self.resolve(p.get("Columns", 1)) or 1
        if pred < 10:
            return data
        bpp = max(1, (colors * bpc + 7) // 8)
        rowlen = (columns * colors * bpc + 7) // 8
        out = bytearray()
        prev = bytearray(rowlen)
        pos = 0
        while pos + 1 + rowlen <= len(data):
            ft = data[pos]
            row = bytearray(data[pos + 1:pos + 1 + rowlen])
            pos += 1 + rowlen
            for i in range(rowlen):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if ft == 0:
                    pass
                elif ft == 1:
                    row[i] = (row[i] + a) & 0xFF
                elif ft == 2:
                    row[i] = (row[i] + b) & 0xFF
                elif ft == 3:
                    row[i] = (row[i] + ((a + b) >> 1)) & 0xFF
                elif ft == 4:
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    row[i] = (row[i] + pr) & 0xFF
            out += row
            prev = row
        return bytes(out)

    # --- page tree ---------------------------------------------------------

    def pages(self):
        root = self.resolve(self.trailer.get("Root"))
        if not isinstance(root, dict):
            self.err("/Root does not resolve to a dictionary")
            return []
        t = self.resolve(root.get("Type"))
        if t != Name("Catalog"):
            self.err(f"/Root /Type is {t!r}, expected /Catalog")
        node = self.resolve(root.get("Pages"))
        if not isinstance(node, dict):
            self.err("catalog /Pages does not resolve to a dictionary")
            return []
        out = []
        self._walk(node, out, set(), {})
        declared = self.resolve(node.get("Count"))
        if isinstance(declared, int) and declared != len(out):
            self.err(f"/Pages /Count is {declared} but the tree holds {len(out)} page(s)")
        return out

    def _walk(self, node, out, seen, inherited):
        nid = id(node)
        if nid in seen:
            self.err("cycle in the page tree")
            return
        seen.add(nid)
        inh = dict(inherited)
        for k in ("Resources", "MediaBox", "CropBox", "Rotate"):
            if k in node:
                inh[k] = node[k]
        t = self.resolve(node.get("Type"))
        if t == Name("Page"):
            merged = dict(inh)
            merged.update(node)
            out.append(merged)
            return
        kids = self.resolve(node.get("Kids"))
        if kids is None:
            self.err(f"page-tree node has neither /Type /Page nor /Kids (type={t!r})")
            return
        if not isinstance(kids, list):
            self.err("/Kids is not an array")
            return
        for k in kids:
            kid = self.resolve(k)
            if isinstance(kid, dict):
                self._walk(kid, out, seen, inh)
            else:
                self.err(f"/Kids entry {k!r} does not resolve to a dictionary")

    def page_content(self, page):
        c = self.resolve(page.get("Contents"))
        if c is None:
            return b""
        streams = c if isinstance(c, list) else [c]
        out = b""
        for s in streams:
            s = self.resolve(s)
            if isinstance(s, Stream):
                out += self._decode_stream(s, "content stream") + b"\n"
            elif s is not None:
                self.err(f"/Contents entry is not a stream: {s!r}")
        return out

    def page_text(self, page):
        """Extract text, applying the page's font /Differences-free assumption.

        Handles Tj, TJ, ', and " operators. Good enough to prove round-tripping;
        it is not a layout engine.
        """
        content = self.page_content(page)
        out = []
        lx = Lexer(content, 0)
        stack = []
        n = len(content)
        while lx.pos < n:
            lx.skip_ws()
            if lx.pos >= n:
                break
            c = content[lx.pos]
            if c in b"(<[/" or (c in b"+-." or 0x30 <= c <= 0x39):
                try:
                    save = lx.pos
                    stack.append(lx.parse())
                    if lx.pos == save:
                        lx.pos += 1
                except PdfError:
                    lx.pos += 1
                    stack.clear()
                continue
            start = lx.pos
            while lx.pos < n and content[lx.pos] not in WS and content[lx.pos] not in DELIM:
                lx.pos += 1
            op = content[start:lx.pos]
            if not op:
                lx.pos += 1
                continue
            if op == b"Tj" and stack:
                v = stack[-1]
                if isinstance(v, bytes):
                    out.append(v.decode("latin-1"))
            elif op == b"TJ" and stack:
                v = stack[-1]
                if isinstance(v, list):
                    for e in v:
                        if isinstance(e, bytes):
                            out.append(e.decode("latin-1"))
                        elif isinstance(e, (int, float)) and e < -120:
                            out.append(" ")
            elif op in (b"'", b'"') and stack:
                for v in reversed(stack):
                    if isinstance(v, bytes):
                        out.append("\n" + v.decode("latin-1"))
                        break
            elif op in (b"Td", b"TD", b"T*", b"ET"):
                out.append("\n")
            stack.clear()
        text = "".join(out)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def check(path, want_text=False):
    with open(path, "rb") as f:
        buf = f.read()
    report = {"file": path, "bytes": len(buf), "errors": [], "warnings": []}
    try:
        pdf = Pdf(buf)
    except PdfError as e:
        report["errors"].append(f"FATAL: {e}")
        return report
    report["version"] = pdf.version
    report["objects"] = len(pdf.xref)
    try:
        pages = pdf.pages()
        report["pages"] = len(pages)
        texts = []
        for i, p in enumerate(pages):
            mb = pdf.resolve(p.get("MediaBox"))
            if not (isinstance(mb, list) and len(mb) == 4):
                pdf.err(f"page {i}: /MediaBox missing or malformed ({mb!r})")
            res = pdf.resolve(p.get("Resources"))
            if not isinstance(res, dict):
                pdf.err(f"page {i}: /Resources missing or not a dictionary")
            texts.append(pdf.page_text(p))
        report["text"] = "\n".join(texts)
        if want_text:
            report["text_shown"] = True
    except PdfError as e:
        pdf.err(f"page tree: {e}")
    report["errors"] = pdf.errors
    report["warnings"] = pdf.warnings
    return report


def main():
    ap = argparse.ArgumentParser(description="Strict PDF validator (bayan acceptance oracle)")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--text", action="store_true", help="print extracted text")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    a = ap.parse_args()

    rc = 0
    reports = []
    for path in a.files:
        r = check(path, a.text)
        reports.append(r)
        if r["errors"]:
            rc = 1
        if a.json:
            continue
        status = "FAIL" if r["errors"] else "OK"
        print(f"[{status}] {path}  ({r['bytes']} bytes, PDF-{r.get('version','?')}, "
              f"{r.get('objects','?')} objects, {r.get('pages','?')} pages)")
        for e in r["errors"]:
            print(f"   error:   {e}")
        for w in r["warnings"]:
            print(f"   warning: {w}")
        if a.text:
            print("--- extracted text ---")
            print(r.get("text", ""))
            print("--- end ---")
    if a.json:
        print(json.dumps(reports, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
