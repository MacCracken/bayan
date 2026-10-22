#!/usr/bin/env python3
"""Generate the TOML tree vectors (bayan 1.11.0) from an independent oracle.

`bayan_toml_v_parse` reads TOML 1.0.0 into json's value tree, and its contract is Python's
`tomllib`: a document tomllib accepts parses to the tree tomllib builds, and a document tomllib
refuses is refused. Each vector is a document and tomllib's answer, never bayan's. The flat parser in
src/toml.cyr returned raw bytes for six releases while its suite stayed green, because every
assertion in it had been written by reading bayan's output.

Format, one vector per line:

    <hex document> TAB <expected>

`<expected>` is `E` for a refused document, else the tree in a canonical form that the harness in
tests/vectors.tcyr (`run_toml_tree`) writes for bayan's tree:

    {<hex key>=<value>;...}   table, keys in document order
    [<value>;...]             array
    S<hex bytes>              string
    I<decimal>                integer
    F<16 hex digits>          float, its IEEE-754 bits (nan and -nan included)
    B1 / B0                   boolean
    D<kind>:<value>           date or time; kind 1 offset date-time, 2 local date-time,
                              3 local date, 4 local time (TOML_DT_*). The value is normalized,
                              because tomllib keeps values, not text: `T` between date and time, the
                              fraction as six digits (truncated, as tomllib truncates), and the
                              offset as +HH:MM, so `Z` and `-00:00` are `+00:00`.

Where bayan cannot follow tomllib, the vector says what bayan does instead (ADR 0013):
  * an integer outside i64: tomllib returns a Python int; the expectation is `E`;
  * nesting past 128 containers, the root table counting as 1: `E`;
  * bytes that are not UTF-8: tomllib.load raises UnicodeDecodeError; `E`.
A document that makes tomllib raise RecursionError is left out.

The documents come from four sources, all deterministic (fixed seeds):
  1. HAND: one or more documents per rule of the TOML spec and of tomllib's table model;
  2. GEN: random documents over a small key alphabet, so tables collide, keys repeat and
     headers reopen tables, both the accepted and the refused way;
  3. MUT: GEN documents with one to three byte-level edits;
  4. the documents of tests/fixtures/toml/strings.vec, every one of which tomllib accepts.

Usage:
    python3 scripts/gen-toml-tree-vectors.py <outdir>               # writes <outdir>/tree.vec
    python3 scripts/gen-toml-tree-vectors.py <outdir> --gen N --seed S --no-hand
        # a differential run of N generated (and N mutated) documents from seed S
"""
import datetime
import os
import random
import struct
import sys
import tomllib

MAX_DEPTH = 128
I64_MIN = -(2 ** 63)
I64_MAX = 2 ** 63 - 1


# ---------------------------------------------------------------------------
# The oracle's answer, in the canonical form
# ---------------------------------------------------------------------------

def _time(t):
    return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}.{t.microsecond:06d}"


def _date(d):
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def ser(v):
    if isinstance(v, bool):
        return "B1" if v else "B0"
    if isinstance(v, int):
        return f"I{v}"
    if isinstance(v, float):
        return "F" + struct.pack(">d", v).hex()
    if isinstance(v, str):
        return "S" + v.encode("utf-8").hex()
    if isinstance(v, datetime.datetime):
        body = _date(v) + "T" + _time(v)
        if v.tzinfo is None:
            return "D2:" + body
        mins = int(v.utcoffset().total_seconds()) // 60
        sign = "+" if mins >= 0 else "-"
        mins = abs(mins)
        return f"D1:{body}{sign}{mins // 60:02d}:{mins % 60:02d}"
    if isinstance(v, datetime.date):
        return "D3:" + _date(v)
    if isinstance(v, datetime.time):
        return "D4:" + _time(v)
    if isinstance(v, list):
        return "[" + "".join(ser(x) + ";" for x in v) + "]"
    if isinstance(v, dict):
        return "{" + "".join(k.encode("utf-8").hex() + "=" + ser(x) + ";" for k, x in v.items()) + "}"
    raise TypeError(type(v))


def fits(v, level):
    """True if bayan's tree can hold v: every int in i64, no container past MAX_DEPTH."""
    if isinstance(v, bool):
        return True
    if isinstance(v, int):
        return I64_MIN <= v <= I64_MAX
    if isinstance(v, (list, dict)):
        if level > MAX_DEPTH:
            return False
        items = v.values() if isinstance(v, dict) else v
        return all(fits(x, level + 1) for x in items)
    return True


def expect(doc):
    """tomllib's answer for the document `doc` (bytes) in the canonical form, or None to skip."""
    try:
        text = doc.decode("utf-8")
    except UnicodeDecodeError:
        return "E"
    try:
        tree = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return "E"
    except RecursionError:
        return None
    if not fits(tree, 1):
        return "E"
    return ser(tree)


# ---------------------------------------------------------------------------
# 1. HAND — documents aimed at each rule
# ---------------------------------------------------------------------------

def hand():
    d = []
    add = d.append
    # Whitespace, newlines, comments, statements.
    for s in ["", "\n", "\r\n", " \t\n", "# c\n", "#\n", "# c", "a = 1", "a = 1\n", "a = 1\r\n",
              "a = 1 # c\n", "a=1\n", "a\t=\t1\n", " a = 1\n", "a = 1\rb = 2\n", "a = 1\r",
              "a = 1 b = 2\n", "a = 1\n\n\nb = 2\n", "= 1\n", "a =\n", "a\n", "a = # c\n",
              "# c\r\n", "# c\rx\n", "# \x7f\n", "# \x00\n", "# \x1f\n", "# \t ok\n",
              "a = 1 #\x01\n", "\ufeffa = 1\n", "a = 1\n\x00", "\x00", "[a]\n\x0c", "a = 1 # é\n"]:
        add(s)
    # Keys.
    for s in ['"a" = 1\n', "'a' = 1\n", '"" = 1\n', "'' = 1\n", '"a b" = 1\n', "a b = 1\n",
              "a.b = 1\n", "a . b = 1\n", "a .b = 1\n", "a. b = 1\n", "a..b = 1\n", ".a = 1\n",
              "a. = 1\n", '"a.b" = 1\n', 'a."b.c".d = 1\n', "a.'b.c'.d = 1\n", '"""a""" = 1\n',
              "'''a''' = 1\n", "é = 1\n", '"é" = 1\n', "1 = 1\n", "1.2 = 1\n", "-_ = 1\n",
              "true = 1\n", "inf = 1\n", "a-b_C9 = 1\n", 'a = 1\n"a" = 2\n', "a = 1\n'a' = 2\n",
              '"\\u0061" = 1\na = 2\n', 'a = 1\nA = 2\n', '"a\\nb" = 1\n', "'a\\nb' = 1\n",
              '"\\x" = 1\n', "a.b.c.d.e.f = 1\n", "a = 1\na.b = 2\n", "a.b = 1\na = 2\n",
              "a.b = 1\na.c = 2\n", "a.b = 1\na.b.c = 2\n", "a.b.c = 1\na.b = 2\n"]:
        add(s)
    # Strings.
    for s in ['a = "x"\n', 'a = "\\b\\t\\n\\f\\r\\"\\\\"\n', 'a = "\\u00e9\\U0001F600"\n',
              'a = "\\ud800"\n', 'a = "\\U00110000"\n', 'a = "\\u12"\n', 'a = "\\uZZZZ"\n',
              'a = "\\e"\n', 'a = "\\x41"\n', 'a = "\\ "\n', 'a = "\t"\n', 'a = "\x01"\n',
              'a = "\x7f"\n', 'a = "a\nb"\n', 'a = "a\rb"\n', 'a = "x\n', 'a = "x', "a = 'x'\n",
              "a = 'a\\nb'\n", "a = 'a\tb'\n", "a = 'a\x01b'\n", "a = 'x\n", "a = ''\n", 'a = ""\n',
              'a = """\nx"""\n', 'a = """\r\nx"""\n', 'a = """\n\nx"""\n', 'a = """x\r\ny"""\n',
              'a = """x\ry"""\n', 'a = """x\\\n   y"""\n', 'a = """x\\  \n\n  y"""\n',
              'a = """x\\ y"""\n', 'a = """x\\\r\n  y"""\n', 'a = """x\\', 'a = """x\\  ',
              'a = """a""""\n', 'a = """a"""""\n', 'a = """a""""""\n', 'a = """""""\n',
              'a = """"""\n', 'a = """\n"""\n', 'a = """x""" """y"""\n', 'a = """\t"""\n',
              'a = """\x01"""\n', "a = '''\nx'''\n", "a = '''x''''\n", "a = '''x'''''\n",
              "a = '''x''''''\n", "a = '''\r\nx\r\ny'''\n", "a = '''x\ry'''\n", "a = '''x\\y'''\n",
              "a = '''\x7f'''\n", "a = '''x", 'a = "é漢😀"\n', 'a = "x" "y"\n', 'a = "x"y\n']:
        add(s)
    # Bytes that are not UTF-8 (tomllib.load would raise UnicodeDecodeError), and the edges of it.
    for b in [b'a = "\xc3"\n', b'a = "\xed\xa0\x80"\n', b'a = "\xf4\x90\x80\x80"\n',
              b'a = "\xc0\x80"\n', b'a = "\xe0\x80\x80"\n', b"a = '\xff'\n", b"# \xff\n",
              b'a = "\xf0\x9f\x98"\n', b'a = "\xf0\x9f\x98\x80"\n', b'a = "\xef\xbf\xbf"\n',
              b'a = "\xf4\x8f\xbf\xbf"\n', b'"\xc3\xa9\xff" = 1\n', b"a = '''\xc3'''\n",
              b'a = "\xe2\x82"\n', b"# \xc3\xa9\n", b"# \xc3\n", b"[\xc3\xa9]\n"]:
        add(b)
    # Integers.
    for s in ["0", "+0", "-0", "1", "+1", "-1", "123", "1_000", "1__000", "_1", "1_", "01", "00",
              "-01", "0x0", "0x1F", "0xdead_BEEF", "0x_1", "0x", "0xg", "-0x1", "+0x1", "0X1",
              "0o17", "0o8", "0b101", "0b2", "0b", "0o", "0x7FFFFFFFFFFFFFFF", "0x8000000000000000",
              "9223372036854775807", "9223372036854775808", "-9223372036854775808",
              "-9223372036854775809", "99999999999999999999999", "0b" + "1" * 63, "0b1" + "0" * 63,
              "0o777777777777777777777", "0o1000000000000000000000", "1 2", "12abc", "1e", "1E5",
              "1_2_3", "+", "-", "++1", "--1", "1.", ".1", "1.e5", "1.0_", "1._0", "0.0", "-0.0",
              "+0.0", "1.5", "1e5", "1e+5", "1e-5", "1E05", "1e0_5", "1_0.0_1e1_0", "3.14159",
              "6.02e23", "1e308", "1e309", "-1e309", "1e-400", "4.9e-324", "2.5e-324",
              "0.1000000000000000055511151231257827", "1" + "0" * 400 + ".0", "0." + "0" * 400 + "1",
              "inf", "+inf", "-inf", "nan", "+nan", "-nan", "infinity", "Inf", "NaN", "in",
              "0e5", "-0e5", "1e5.5", "1.5.5", "0x1.5", "true", "false", "True", "truex", "tru",
              "falsey", "1,", "[1]"]:
        add("a = " + s + "\n")
    # Dates and times.
    for s in ["1979-05-27T07:32:00Z", "1979-05-27t07:32:00z", "1979-05-27 07:32:00Z",
              "1979-05-27T00:32:00-07:00", "1979-05-27T00:32:00.999999-07:00",
              "1979-05-27T00:32:00.9999999999+07:00", "1979-05-27T07:32:00",
              "1979-05-27T07:32:00.5", "1979-05-27", "07:32:00", "00:32:00.999999", "07:32:00.",
              "07:32", "7:32:00", "07:32:60", "24:00:00", "23:59:59", "1979-05-27T07:32",
              "1979-05-27T25:00:00", "1979-05-27 25:00:00", "1979-13-27", "1979-00-27",
              "1979-05-32", "1979-05-00", "1979-02-29", "1980-02-29", "1900-02-29", "2000-02-29",
              "0000-01-01", "0001-01-01", "9999-12-31", "1979-04-31", "1979-05-27T07:32:00+24:00",
              "1979-05-27T07:32:00+23:59", "1979-05-27T07:32:00-00:00", "1979-05-27T07:32:00+0700",
              "1979-05-27T07:32:00+07", "1979-05-27T07:32:00Zx", "1979-05-27 # c",
              "1979-05-27 07:32:00 # c", "1979-05-27x", "1979-5-27", "79-05-27", "1979-05-27T",
              "1979-05-27 T07:32:00", "1979-05-27T07:32:00.Z", "[1979-05-27, 07:32:00]",
              "[1979-05-27 07:32:00]", "{d = 1979-05-27}", "1979-05-27T07:32:00 Z"]:
        add("a = " + s + "\n")
    # Arrays.
    for s in ["[]", "[ ]", "[\n]", "[1]", "[1,]", "[1,2]", "[1 , 2 , ]", "[,]", "[1,,2]",
              "[,1]", "[1 2]", "[\n1,\n2,\n]", "[ # c\n1 # c\n, # c\n2 # c\n]", "[1, 'a', 2.0, true]",
              "[[1, 2], [3, [4]]]", "[{a = 1}, {b = 2}]", "[1", "[1,", "[\n", "[1]]", "[[]]",
              "[ [ ] , ]", "[1\n,2]", "[1 # \x01\n]", "[1\r\n,2]", "[1\r,2]", "[{}]", "[{a=1},]"]:
        add("a = " + s + "\n")
    # Inline tables.
    for s in ["{}", "{ }", "{a = 1}", "{a = 1,}", "{a = 1, b = 2}", "{a = 1 b = 2}", "{a.b = 1}",
              "{a.b = 1, a.c = 2}", "{a = 1, a = 2}", "{a = 1, a.b = 2}", "{a.b = 1, a = 2}",
              "{a = {b = 1}, a.c = 2}", "{a = [1], a.b = 2}", "{a = {}, b = {}}", "{a\n= 1}",
              "{a = 1\n}", "{\na = 1}", "{a = 1,\nb = 2}", "{a = [\n1]}", "{a = 1 # c\n}",
              "{a = \"\"\"x\ny\"\"\"}", "{,}", "{a = 1,,}", "{a}", "{a =}", "{= 1}", "{a = 1",
              "{a = {b = {c = {}}}}", "{'a b' = 1, \"c.d\" = 2}"]:
        add("t = " + s + "\n")
    # Tables, arrays of tables, and tomllib's table model.
    for s in ["[a]\n", "[ a ]\n", "[a]\n[a]\n", "[a]\n[b]\n[a]\n", "[a.b]\n[a]\n",
              "[a]\n[a.b]\n", "[a.b]\n[a.b]\n", "[\"a\".'b']\n", "[a.\"b.c\"]\n", "[ a . b ]\n",
              "[a]x\n", "[a] # c\n", "[a]]\n", "[[a]\n", "[a\n", "[]\n", "[.]\n", "[a.]\n",
              "[ [a]]\n", "[[a] ]\n", "[[ a ]]\n", "[[a]]\n[[a]]\n", "[[a]]\n[a]\n", "[a]\n[[a]]\n",
              "[[a]]\nx = 1\n[[a]]\nx = 2\n", "[[a.b]]\n[[a.b]]\n", "[[a]]\n[[a.b]]\n[[a]]\n[[a.b]]\n",
              "[[a]]\n[a.b]\nx = 1\n[[a]]\n[a.b]\nx = 2\n", "[[a]]\n[a.b]\n[a.b]\n",
              "a = 1\n[a]\n", "a = 1\n[a.b]\n", "a = {}\n[a]\n", "a = {}\n[a.b]\n", "a = []\n[[a]]\n",
              "a = [1]\n[[a]]\n", "a = [{}]\n[[a]]\n", "a = [{}]\n[a.b]\n", "a.b = 1\n[a]\n",
              "a.b = 1\n[a.b]\n", "a.b.c = 1\n[a.b.d]\n", "a.b.c = 1\n[a.b]\n", "a.b = 1\n[a.c]\n",
              "[a]\nb.c = 1\n[a.b]\n", "[a]\nb.c = 1\n[a.b.d]\n", "[a]\nb.c = 1\nb.d = 2\n",
              "[a.b.c]\n[a]\nb.x = 1\n", "[a.b]\n[a]\nb.x = 1\n", "[a.b]\nc = 1\n[a]\nb.d = 2\n",
              "[a]\nb = 1\n[a.b]\n", "[a]\nb = {}\n[a.b]\n", "[a]\nb = {}\nb.c = 1\n",
              "[a]\nb = []\n[[a.b]]\n", "[[a]]\nb.c = 1\n[[a]]\nb.c = 2\n", "[[a]]\nb.c = 1\n[a.b]\n",
              "[[a]]\nb = 1\nb = 2\n", "[[a.b]]\n[a]\nb.c = 1\n", "[[a.b]]\n[a]\n", "[a]\n[[a.b]]\n",
              "[x.y]\n[x]\ny.z = 1\n", "[a.b]\nx = 1\n[a.b.c]\n[a.b]\n", "[[a]]\n[[a.b]]\nc = 1\n",
              "[a]\n[a.b]\n[a.b.c]\n[a.d]\n[b]\n", "[[x.y]]\n[x]\n[[x.y]]\n", "[[x.y]]\n[[x]]\n",
              "[t]\na.b = 1\n[t.a.c]\n", "[t]\na.b = 1\n[t.a]\n", "[t]\n[t.a]\nb = 1\n[t]\n",
              "a.b = 1\nc = 2\n[d]\na.b = 3\n", "[[a]]\n[[a.a]]\n[[a.a.a]]\n",
              "[[a]]\na = 1\n", "[[a]]\n[a.a]\n[[a]]\n[a.a]\n", "[a]\n[a.b]\n[a.b.c]\n[a]\n",
              "[a]\nb.c.d = 1\n[a.b.c.e]\n", "[a]\nb.c.d = 1\n[a.b.c]\n", "[a]\nb.c.d = 1\n[a.b]\n"]:
        add(s)
    # The input ends where a key, a value or a closing bracket is due.
    for s in ["[", "[[", "[a", "[[a", "[[a]", "a.", "a. ", "a =", "a = [", "a = [1,", "a = {",
              "a = {b", "a = {b.", "a = {b =", "a = {b = 1,", "a = {b = 1", '"a', "'a", 'a = "', "a = '"]:
        add(s)
    # Depth: 128 levels are allowed, 129 are not (the root table is level 1).
    add("a = " + "[" * 127 + "]" * 127 + "\n")
    add("a = " + "[" * 128 + "]" * 128 + "\n")
    add("a = " + "{b = " * 127 + "1" + "}" * 127 + "\n")
    add("a = " + "{b = " * 128 + "1" + "}" * 128 + "\n")
    add(".".join(["k"] * 128) + " = 1\n")
    add(".".join(["k"] * 129) + " = 1\n")
    add("[" + ".".join(["k"] * 127) + "]\n")
    add("[" + ".".join(["k"] * 128) + "]\n")
    add("[[" + ".".join(["k"] * 126) + "]]\n")
    add("[[" + ".".join(["k"] * 127) + "]]\n")
    add("[" + ".".join(["k"] * 120) + "]\n" + ".".join(["j"] * 8) + " = 1\n")
    add("[" + ".".join(["k"] * 120) + "]\n" + ".".join(["j"] * 9) + " = 1\n")
    add("[" + ".".join(["k"] * 120) + "]\nx = " + "[" * 7 + "]" * 7 + "\n")
    add("[" + ".".join(["k"] * 120) + "]\nx = " + "[" * 8 + "]" * 8 + "\n")
    return [s.encode("utf-8") if isinstance(s, str) else s for s in d]


# ---------------------------------------------------------------------------
# 2. GEN — random documents
# ---------------------------------------------------------------------------

KEYS = ["a", "b", "c", "x", "y"]


class Gen:
    def __init__(self, r):
        self.r = r

    def pick(self, xs):
        return xs[self.r.randrange(len(xs))]

    def chance(self, p):
        return self.r.random() < p

    def key_part(self):
        n = self.r.random()
        if n < 0.75:
            return self.pick(KEYS) if self.chance(0.8) else self.pick(["k-1", "K_2", "9", "_", "a-b"])
        body = self.pick(KEYS + ["a.b", "a b", "é", "", "x\\ty", "q\\\"q"])
        if n < 0.9:
            return '"' + body + '"'
        return "'" + body.replace("\\", "").replace('"', "") + "'"

    def key(self):
        parts = [self.key_part() for _ in range(1 if self.chance(0.6) else self.r.randint(2, 3))]
        dot = self.pick([".", ".", " . ", ". "])
        return dot.join(parts)

    def text(self, basic, ml):
        out = []
        for _ in range(self.r.randint(0, 6)):
            n = self.r.random()
            if n < 0.4:
                out.append(self.pick(["a", "b", "z", " ", "0", "#", "=", "[", "]", ",", "{", "}"]))
            elif n < 0.55:
                out.append(self.pick(["é", "漢", "😀", "\t"]))
            elif n < 0.75 and basic:
                out.append(self.pick(["\\n", "\\t", '\\"', "\\\\", "\\u00e9", "\\U0001F600", "\\b",
                                      "\\f", "\\r", "\\u0000", "\\u007f"]))
            elif n < 0.85 and ml:
                out.append(self.pick(["\n", "\r\n", '"', "'", '""', "''"]))
                if basic and self.chance(0.3):
                    out.append(self.pick(["\\\n", "\\  \n  ", "\\\r\n"]))
            else:
                out.append(self.pick(["x", "y", "-", "."]))
        return "".join(out)

    def string(self):
        n = self.r.random()
        if n < 0.45:
            return '"' + self.text(True, False) + '"'
        if n < 0.65:
            return "'" + self.text(False, False).replace("'", "") + "'"
        if n < 0.85:
            lead = "\n" if self.chance(0.4) else ""
            return '"""' + lead + self.text(True, True) + '"""'
        lead = "\n" if self.chance(0.4) else ""
        return "'''" + lead + self.text(False, True) + "'''"

    def integer(self):
        n = self.r.random()
        if n < 0.5:
            v = self.r.choice([0, 1, 7, 42, 1000, 123456789, I64_MAX, I64_MIN,
                               self.r.randint(-10 ** 6, 10 ** 6), self.r.randint(-2 ** 63, 2 ** 63 - 1)])
            if self.chance(0.02):
                v = self.r.choice([I64_MAX + 1, I64_MIN - 1])   # past i64: tomllib's int, bayan's E
            digits = str(abs(v))
            if len(digits) > 3 and self.chance(0.3):
                digits = digits[0] + "_" + digits[1:]
            sign = "-" if v < 0 else ("+" if self.chance(0.2) else "")
            return sign + digits
        if n < 0.7:
            return "0x" + self.pick(["0", "1F", "dead_beef", "7FFFFFFFFFFFFFFF", "00ff", "7fff_ffff_ffff_ffff"])
        if n < 0.85:
            return "0o" + self.pick(["0", "17", "755", "777_777"])
        return "0b" + self.pick(["0", "1", "1010", "1_0_1"])

    def float_(self):
        return self.pick(["0.0", "-0.0", "1.5", "+1.5", "-2.25", "1e10", "1E-10", "6.02e+23",
                          "1_000.000_1", "3.141592653589793", "1e400", "-1e400", "1e-400",
                          "inf", "+inf", "-inf", "nan", "+nan", "-nan", "0.1", "5e-324",
                          "1.7976931348623157e308", "1.7976931348623159e308", "2.2250738585072011e-308",
                          str(self.r.uniform(-1e6, 1e6)), repr(self.r.random() * 10 ** self.r.randint(-30, 30))])

    def datetime_(self):
        y = self.r.choice([1, 1979, 2000, 1900, 2024, 9999, self.r.randint(1, 9999)])
        mo = self.r.randint(1, 12)
        da = self.r.randint(1, 31) if self.chance(0.2) else self.r.randint(1, 28)
        date = f"{y:04d}-{mo:02d}-{da:02d}"
        t = f"{self.r.randint(0, 23):02d}:{self.r.randint(0, 59):02d}:{self.r.randint(0, 59):02d}"
        if self.chance(0.4):
            t += "." + "".join(self.pick("0123456789") for _ in range(self.r.randint(1, 9)))
        n = self.r.random()
        if n < 0.25:
            return date
        if n < 0.4:
            return t
        sep = self.pick(["T", "T", "t", " "])
        dt = date + sep + t
        if n < 0.6:
            return dt
        off = self.pick(["Z", "z", "+00:00", "-00:00", "+05:30", "-07:00", "+23:59"])
        return dt + off

    def value(self, depth):
        n = self.r.random()
        if depth > 3:
            n = n * 0.75
        if n < 0.25:
            return self.string()
        if n < 0.4:
            return self.integer()
        if n < 0.5:
            return self.float_()
        if n < 0.55:
            return self.pick(["true", "false"])
        if n < 0.65:
            return self.datetime_()
        if n < 0.85:
            return self.array(depth + 1)
        return self.inline(depth + 1)

    def ws(self):
        return self.pick(["", " ", " ", "  ", "\t"])

    def array(self, depth):
        vals = [self.value(depth) for _ in range(self.r.randint(0, 4))]
        out = "["
        for i, v in enumerate(vals):
            if self.chance(0.2):
                out += self.pick(["\n", "\n  ", " # c\n", "\r\n"])
            out += self.ws() + v + self.ws()
            if i < len(vals) - 1 or self.chance(0.2):
                out += ","
        if self.chance(0.2):
            out += "\n"
        return out + "]"

    def inline(self, depth):
        pairs = [self.key() + self.ws() + "=" + self.ws() + self.value(depth)
                 for _ in range(self.r.randint(0, 3))]
        return "{" + self.ws() + ("," + self.ws()).join(pairs) + self.ws() + "}"

    def kv(self):
        return self.key() + self.ws() + "=" + self.ws() + self.value(0)

    def header(self):
        k = self.key()
        if self.chance(0.4):
            return "[[" + self.ws() + k + self.ws() + "]]"
        return "[" + self.ws() + k + self.ws() + "]"

    def document(self):
        lines = []
        for _ in range(self.r.randint(0, 4)):
            lines.append(self.kv())
        for _ in range(self.r.randint(0, 4)):
            lines.append(self.header())
            for _ in range(self.r.randint(0, 3)):
                lines.append(self.kv())
        out = []
        nl = "\r\n" if self.chance(0.15) else "\n"
        for ln in lines:
            if self.chance(0.1):
                out.append(self.pick(["", "# comment", "  # é"]))
            if self.chance(0.15):
                ln = ln + self.ws() + "# c"
            out.append(self.ws() + ln)
        text = nl.join(out)
        if self.chance(0.8):
            text += nl
        return text.encode("utf-8")


# ---------------------------------------------------------------------------
# 3. MUT — byte-level edits
# ---------------------------------------------------------------------------

ALPHABET = b'[]{}=,."\'#\n \t\\0123456789aeftnx_+-:TZ\r\x00\x7f\xc3\xa9'


def mutate(r, doc):
    b = bytearray(doc)
    for _ in range(r.randint(1, 3)):
        n = r.random()
        if n < 0.3 and b:
            del b[r.randrange(len(b))]
        elif n < 0.6:
            b.insert(r.randint(0, len(b)), ALPHABET[r.randrange(len(ALPHABET))])
        elif n < 0.75 and b:
            b[r.randrange(len(b))] = ALPHABET[r.randrange(len(ALPHABET))]
        else:
            lines = bytes(b).split(b"\n")
            if len(lines) > 1:
                i = r.randrange(len(lines))
                j = r.randrange(len(lines))
                if r.random() < 0.5:
                    lines.insert(j, lines[i])
                else:
                    lines[i], lines[j] = lines[j], lines[i]
                b = bytearray(b"\n".join(lines))
    return bytes(b)


# ---------------------------------------------------------------------------
# 4. The string vectors' documents
# ---------------------------------------------------------------------------

def string_vector_docs(path):
    docs = []
    with open(path, "r", encoding="ascii") as f:
        for line in f:
            fields = line.split()
            if len(fields) >= 2:
                docs.append(bytes.fromhex(fields[1]))
    return docs


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    outdir = args[0]
    ngen, seed, with_hand = 800, 1100, True
    i = 1
    while i < len(args):
        if args[i] == "--gen":
            ngen = int(args[i + 1])
            i += 2
        elif args[i] == "--seed":
            seed = int(args[i + 1])
            i += 2
        elif args[i] == "--no-hand":
            with_hand = False
            i += 1
        else:
            sys.exit(f"unknown argument {args[i]}")

    docs = []
    if with_hand:
        docs.extend(hand())
        here = os.path.dirname(os.path.abspath(__file__))
        docs.extend(string_vector_docs(os.path.join(here, "..", "tests", "fixtures", "toml", "strings.vec")))
    r = random.Random(seed)
    g = Gen(r)
    gen = [g.document() for _ in range(ngen)]
    docs.extend(gen)
    docs.extend(mutate(r, gen[r.randrange(len(gen))]) for _ in range(ngen))

    os.makedirs(outdir, exist_ok=True)
    seen = set()
    n_ok = n_err = n_skip = 0
    with open(os.path.join(outdir, "tree.vec"), "w", encoding="ascii", newline="\n") as f:
        for doc in docs:
            if doc in seen:
                continue
            seen.add(doc)
            want = expect(doc)
            if want is None:
                n_skip += 1
                continue
            if want == "E":
                n_err += 1
            else:
                n_ok += 1
            f.write(doc.hex() + "\t" + want + "\n")
    print(f"wrote {n_ok + n_err} vectors: {n_ok} accepted by tomllib, {n_err} refused, {n_skip} skipped")


if __name__ == "__main__":
    main()
