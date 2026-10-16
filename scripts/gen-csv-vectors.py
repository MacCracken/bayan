#!/usr/bin/env python3
"""Generate CSV vectors from an independent oracle: Python's `csv` module (1.7.0).

The expected values come from `csv.reader` and `csv.writer` with their
defaults (QUOTE_MINIMAL, a `"` quote, CRLF records), NOT from bayan. Until 1.7.0
src/csv.cyr was an RFC 4180 subset that dropped a trailing empty field, ended
records in LF, did not quote a field holding CR, and started a new field at the
text after a closing quote: four silent wrong answers, documented since 1.5.3
and fixed when this oracle arrived.

Format, one vector per line: a kind tag and hex-encoded fields, `-` for an empty
one. Counts are one hex byte.

    P <line> <n> <field 1> ... <field n>    bayan_csv_parse_line(line)
    W <n> <field 1> ... <field n> <line>    bayan_csv_write_line(fields)
    E <field> <escaped>                     bayan_csv_escape(field)

`P` lines are ones Python reads as exactly one record or none. bayan's parser
takes one line: a CR or LF ends the record only as the line's terminator (the
last byte, or CRLF as the last two). A line that Python splits into two records
at an unquoted line break mid-line is outside that contract and is not emitted;
src/csv.cyr says what bayan does with it.

Every line is verified with the oracle before it is written: a `P` line must
read back as its record, a `W` line must be what `csv.writer` writes, and a
written row must read back as itself. Generation aborts rather than emit a
vector that encodes a wrong belief.

Regenerate with:  python3 scripts/gen-csv-vectors.py tests/fixtures/csv
"""
import csv
import io
import os
import random
import sys


def hx(s):
    b = s.encode("utf-8")
    return b.hex() if b else "-"


def read(line):
    """The records Python reads from `line` (newline='' as the csv docs say)."""
    return list(csv.reader(io.StringIO(line, newline="")))


def write(row):
    buf = io.StringIO()
    csv.writer(buf).writerow(row)
    return buf.getvalue()


TOKENS = ["a", "b", "xyz", " ", ",", '"', "\r", "\n", "\t", "'", "é", '""', "\r\n", "1.5"]
RAW = ["a", "b", ",", ",", '"', '""', " ", "x", "\t", "'", '"a"', "é", "\r", "\n"]
ENDS = ["", "\r\n", "\n", "\r"]


def field(rnd):
    return "".join(rnd.choice(TOKENS) for _ in range(rnd.choice([0, 0, 1, 1, 2, 3, 4])))


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    rnd = random.Random(4180)
    lines, seen = [], set()

    def emit(rec):
        if rec not in seen:
            seen.add(rec)
            lines.append(rec)

    def p(line, rec):
        emit("P " + hx(line) + " " + f"{len(rec):02x}" + "".join(" " + hx(f) for f in rec))

    # The edges RFC 4180 and the 1.5.3 header name, and the shapes around them.
    fixed = ["a,", ",,", ",", "", "a", '""', '"a"b,c', 'a"b', ' "a"', '"abc', '"a""b"',
             "a,b\r\n", "a,b\n", "a,b\r", '"x\r\ny",z', 'a,"b"\r\n', '"a" ,b', "\r\n", "\n",
             "\r", "a,\r\n", ",\r\n", '"a"\r\n', '"x\r', '"x\n', 'a,"",b', '"",""', 'a,b,']
    for line in fixed:
        recs = read(line)
        assert len(recs) <= 1, (line, recs)
        p(line, recs[0] if recs else [])

    # Rows written by csv.writer, read back in each terminator form.
    rows = [[], [""], ["", ""], ["a", ""], ["", "a"]]
    for _ in range(700):
        rows.append([field(rnd) for _ in range(rnd.randint(1, 5))])
    for row in rows:
        w = write(row)
        assert read(w) == [row], (row, w)
        emit("W " + f"{len(row):02x}" + "".join(" " + hx(f) for f in row) + " " + hx(w))
        body = w[:-2]
        assert w.endswith("\r\n")
        for end in ENDS:
            line = body + end
            recs = read(line)
            if len(recs) == 1 and recs[0] == row:
                p(line, row)
            elif not row and recs == [] and end == "":
                p(line, [])

    # Raw lines, not written by any writer: stray quotes, text after a closing
    # quote, unterminated quotes, quotes mid-field. Kept only where Python reads
    # one record (or none) and any CR or LF outside quotes is the terminator.
    kept = 0
    for _ in range(40000):
        if kept >= 1500:
            break
        n = rnd.randint(0, 9)
        line = "".join(rnd.choice(RAW) for _ in range(n)) + rnd.choice(ENDS)
        try:
            recs = read(line)
        except csv.Error:
            continue
        if len(recs) > 1:
            continue
        before = len(lines)
        p(line, recs[0] if recs else [])
        kept += len(lines) - before

    # escape: what csv.writer makes of the field inside a row of two.
    fields = ["", "a", ",", '"', "\r", "\n", "\r\n", " a", "a ", "\t", "'", "é"]
    fields += [field(rnd) for _ in range(500)]
    for f in fields:
        w = write([f, "x"])
        assert w.endswith(",x\r\n"), (f, w)
        emit("E " + hx(f) + " " + hx(w[:-4]))

    p_ = os.path.join(out_dir, "csv.vec")
    with open(p_, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    counts = {k: sum(1 for l in lines if l[0] == k) for k in "PWE"}
    print(f"wrote {p_} ({len(lines)} vectors: {counts['P']} parse, {counts['W']} write, "
          f"{counts['E']} escape)")


if __name__ == "__main__":
    main()
