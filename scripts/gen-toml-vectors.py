#!/usr/bin/env python3
"""Generate TOML string-decoding vectors from an independent oracle.

The expected values come from Python's `tomllib`, NOT from bayan. That
independence is the whole point, and this module is the reason it is worth
paying for twice: `src/toml.cyr` shipped from 1.0.0 to 1.5.2 returning the RAW
bytes between the quotes — escapes unresolved, literal strings still wearing
their quotes — while every test in the suite passed, because every test
compared bayan against bayan. Reported by mneme
(docs/development/issues/2026-08-22-mneme-toml-basic-strings-not-unescaped.md).

Mirrors scripts/gen-numeric-vectors.py in shape: a line-oriented text file
tests/vectors.tcyr reads at run time, so the vector count can grow without the
.tcyr file growing with it.

Format, one vector per line: a kind tag and hex-encoded fields.

    S <hex doc> <hex expected value of key `x`>
    A <hex doc> <hex expected FIRST ELEMENT of array `x`>
    P <hex doc> <hex table name> <hex key> <hex expected value>

`S` reads the value with `bayan_toml_get`; `A` reads it with
`bayan_toml_get_array` and takes element 0, so the element splitter — which
keeps its own quote-tracking state — is checked against the same oracle as the
scalar parsers rather than assumed to agree with them.

`P` (1.5.4) checks STRUCTURE: it looks the table up by name with
`bayan_toml_get_sections` and then the key inside it. That is what covers
quoted keys, dotted keys naming a table, and trimmed/unquoted header names —
none of which the S/A kinds can see, because all three are about WHERE a pair
lands rather than what its value is.

Hex rather than the text itself because both fields routinely contain
newlines, quotes, backslashes and non-UTF-8-looking bytes — an encoding that
needs its own escaping rules would be a second bug surface in the file whose
job is to check escaping.

Every line is verified with `tomllib` before it is written: if Python cannot
parse the document, or decodes it to something other than the recorded value,
generation aborts rather than emitting a vector that encodes a wrong belief.

Regenerate with:  python3 scripts/gen-toml-vectors.py tests/fixtures/toml
"""
import os
import random
import sys
import tomllib

# ---------------------------------------------------------------------------
# TOML escaping (the oracle's side of the contract)
# ---------------------------------------------------------------------------

_SIMPLE = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def esc_basic(s, keep_newline=False):
    """Escape `s` for a TOML basic string body."""
    out = []
    for ch in s:
        cp = ord(ch)
        if keep_newline and cp == 0x0A:
            out.append(ch)
        elif cp in _SIMPLE:
            out.append(_SIMPLE[cp])
        elif cp < 0x20 or cp == 0x7F:
            out.append("\\u%04X" % cp)
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Value corpus
# ---------------------------------------------------------------------------

def interesting_values():
    """Strings that historically break escape handling."""
    return [
        "",
        "plain",
        'say "hi"',
        "C:\\tmp",
        "C:\\\\tmp",
        "\\",
        "\\\\",
        '"',
        '""',
        '"""',
        "'",
        "''",
        "'''",
        "a\tb",
        "a\nb",
        "a\rb",
        "a\fb",
        "a\bb",
        "\x00" if False else "\x01",       # NUL cannot round-trip through a cstring
        "\x1f",
        "\x7f",
        # UTF-8 length boundaries, from both sides
        "\u007f",
        "\u0080",
        "\u07ff",
        "\u0800",
        "\uffff",
        "\U00010000",
        "\U0010ffff",
        "e\u0301",                          # combining mark
        "\u00e9",
        "\U0001F600",
        "caf\u00e9 \U0001F600 \u4e2d\u6587",
        # A value that ends in the delimiter char, which is where the
        # closing-delimiter scan gets it wrong.
        'ends with a quote"',
        "ends with two quotes\"\"",
        "ends with an apostrophe'",
        "ends with two apostrophes''",
        # Backslash adjacent to a quote — the shape in the mneme repro.
        'he said \\"hi\\"',
        "trailing backslash\\",
        "multi\nline\nvalue",
        "  leading and trailing  ",
    ]


def random_values(rng, n):
    """Random strings over an alphabet weighted toward the dangerous bytes."""
    alphabet = (
        list("abcdefgHIJK 0123456789")
        + ['"'] * 4
        + ["\\"] * 4
        + ["'"] * 3
        + ["\t", "\n", "\r", "\x01", "\x7f"]
        + ["\u00e9", "\u4e2d", "\U0001F600", "\u0080", "\u07ff", "\u0800"]
    )
    out = []
    for _ in range(n):
        ln = rng.choice([0, 1, 2, 3, 5, 8, 13, 21])
        out.append("".join(rng.choice(alphabet) for _ in range(ln)))
    return out


# ---------------------------------------------------------------------------
# Document forms
# ---------------------------------------------------------------------------

def _literal_ok(v, multiline=False):
    """TOML literal strings admit tab, and printable/non-ASCII characters only.

    Grammar (TOML 1.0.0): literal-char = %x09 / %x20-26 / %x28-7E / %x80-10FFFF,
    with newline additionally allowed inside `'''`. Control characters and DEL
    have no escape available in a literal string, so a value carrying one simply
    cannot be written that way — the form is skipped rather than emitted as a
    document with no oracle answer.
    """
    for ch in v:
        cp = ord(ch)
        if cp == 0x09:
            continue
        if cp == 0x0A and multiline:
            continue
        if cp < 0x20 or cp == 0x7F:
            return False
    return True


def forms(v):
    """Every legal TOML spelling of `v`, as (label, document) pairs.

    A form is skipped when the value cannot legally be written that way — a
    literal string cannot contain its own quote or a newline, a multi-line
    string cannot contain its full delimiter run, and so on. Skipping is
    deliberate: an illegal document would have no oracle answer to compare to.
    """
    out = []

    # Single-line basic: always legal, everything escapable.
    out.append(("basic", 'x = "%s"\n' % esc_basic(v)))

    # Single-line literal: no escapes at all, so `'` and control chars are out.
    if "'" not in v and _literal_ok(v):
        out.append(("literal", "x = '%s'\n" % v))

    # Multi-line basic, with and without the trimmed leading newline. A raw
    # newline is legal in the body, so keep_newline=True exercises the arm
    # where bayan used to trim the TRAILING one.
    body = esc_basic(v, keep_newline=True)
    if '"""' not in body:
        out.append(("ml-basic", 'x = """%s"""\n' % body))
        out.append(("ml-basic-nl", 'x = """\n%s"""\n' % body))
        # A body ending in the delimiter char is what the "closer is the last
        # three of the run" rule exists for; only 1 or 2 may be unescaped.
        if not body.endswith('"'):
            out.append(("ml-basic-trailnl", 'x = """\n%s\n"""\n' % body))

    # Multi-line literal: verbatim, so only values with no ''' and no stray
    # trailing ' can be written this way.
    if "'''" not in v and not v.endswith("'") and _literal_ok(v, multiline=True):
        out.append(("ml-literal", "x = '''%s'''\n" % v))
        if not v.endswith("\n"):
            out.append(("ml-literal-nl", "x = '''\n%s'''\n" % v))

    # Array element — the same escape rules, reached through a different code
    # path (the element splitter, which has its own quote tracking).
    out.append(("array", 'x = ["%s"]\n' % esc_basic(v)))

    return out


def line_ending_backslash_cases():
    """The multi-line line-ending backslash, which has no single-line analogue."""
    return [
        'x = """\\\n     foo \\\n     bar"""\n',
        'x = """a\\\n\n\n   b"""\n',
        'x = """a\\   \n   b"""\n',          # trailing spaces before the newline
        'x = """\\\n"""\n',                   # folds to empty
        'x = """a\\\n  \\\n  b"""\n',         # two folds in a row
    ]


def delimiter_run_cases():
    r"""Bodies that END in delimiter characters, and escaped quotes beside them.

    These are generated by hand rather than by escaping a value, because the
    value-driven forms above escape EVERY quote — so they never produce an
    unescaped delimiter char adjacent to the closer, which is precisely the
    shape the "closer is the last three of the run" rule exists for. Mutation
    testing found the hole: reverting that rule left all 1,463 value-driven
    vectors green.

    The `a\"""b` shapes separate two rules that can otherwise mask each other.
    Without the multi-line scan's backslash rule, the escaped quote plus the
    two raw ones read as a closing run and the body stops at `a\`; the last-3
    rule cannot rescue that, so the two are checked independently.
    """
    return [
        'x = """a""""\n',
        'x = """a"""""\n',
        'x = """he said "hi""""\n',
        'x = """a"b""""\n',
        'x = """a\\"b""""\n',
        'x = """""a"""\n',
        'x = """a\\"""b"""\n',
        'x = """a\\""b"""\n',
        'x = """a\\""""\n',
        "x = '''a''''\n",
        "x = '''a'''''\n",
        "x = '''it's''''\n",
        "x = '''''a'''\n",
    ]


def structural_cases():
    """(document, table, key) triples for the `P` kind — 1.5.4.

    Every one is a shape that landed the pair in the WRONG PLACE, or nowhere,
    before 1.5.4:

      * a quoted key containing a space was dropped entirely; one without a
        space kept its quotes, so every lookup missed;
      * `a . b = 1` was dropped for the same reason;
      * `a.b.c = 1` stored one flat key instead of naming the table `a.b`,
        disagreeing with `[a.b]` + `c = 1` for the same data;
      * `[ a ]` named the table " a ", spaces included.

    The oracle resolves the expected value by walking tomllib's nested dicts
    along the table path, so the expectation is Python's answer to "what is at
    a.b.c", not a transcription of what bayan does.
    """
    return [
        # quoted keys
        ('"key one" = 1\n',                     "",       "key one"),
        ('"key" = 2\n',                         "",       "key"),
        ("'lit key' = 3\n",                     "",       "lit key"),
        ('"esc\\tkey" = 4\n',                    "",       "esc\tkey"),
        # dotted keys name a table
        ("a.b.c = 1\n",                         "a.b",    "c"),
        ("a . b = 2\n",                         "a",      "b"),
        ("x.y = 3\nz = 4\n",                     "x",      "y"),
        ("x.y = 3\nz = 4\n",                     "",       "z"),
        ('a."b c".d = 5\n',                     "a.b c",  "d"),
        ("[t]\na.b = 6\n",                      "t.a",    "b"),
        ("[t]\na.b = 6\nx = 7\n",                "t",      "x"),
        # header names are trimmed and unquoted
        ("[ a ]\nx = 1\n",                      "a",      "x"),
        ('[ "b c" ]\ny = 2\n',                  "b c",    "y"),
        ("[ 'd' ]\nz = 3\n",                    "d",      "z"),
        ("[a.b]\nc = 4\n",                      "a.b",    "c"),
        ("[ a . b ]\nc = 5\n",                  "a.b",    "c"),
        # a header and a dotted key naming the same table agree
        ("[q]\nr.s = 1\n",                      "q.r",    "s"),
        # the root table is reachable even when the file opens with a header
        ("[a]\nx = 1\n",                        "a",      "x"),
    ]
    # NOT here: duplicate keys. tomllib REJECTS `secure = true` followed by
    # `secure = false` outright, so there is no oracle answer to record —
    # last-wins is bayan POLICY, chosen because it is what every implementation
    # that does not error does. It is pinned by hand in tests/bayan.tcyr
    # instead, where the reasoning can sit next to the assertion.


def crlf_cases():
    """CRLF after the opening delimiter must be trimmed as a unit."""
    return [
        'x = """\r\nline1"""\n',
        'x = """\r\nline1\r\n"""\n',
        "x = '''\r\nline1'''\n",
    ]


def _split_table(name):
    """Split a dotted table name into segments.

    A quoted segment may itself contain a dot; none of the fixtures here does,
    and the generator asserts that rather than pretending to handle it.
    """
    assert '"' not in name and "'" not in name, name
    return name.split(".")


# ---------------------------------------------------------------------------

def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/toml"
    os.makedirs(outdir, exist_ok=True)
    rng = random.Random(0x70776C)          # fixed seed: CI diffs the output

    docs = []
    for v in interesting_values() + random_values(rng, 240):
        for label, doc in forms(v):
            docs.append(("A" if label == "array" else "S", doc))
    for doc in line_ending_backslash_cases() + delimiter_run_cases() + crlf_cases():
        docs.append(("S", doc))

    lines = []
    seen = set()
    for kind, doc in docs:
        if doc in seen:
            continue
        seen.add(doc)
        # The oracle decides the answer, and it also decides whether the
        # document is legal at all. A form this generator built wrong must
        # abort the run rather than become a vector asserting nonsense.
        try:
            got = tomllib.loads(doc)["x"]
        except Exception as e:                       # pragma: no cover
            raise SystemExit(
                "generator emitted a document tomllib rejects:\n%r\n%s" % (doc, e)
            )
        if kind == "A":
            got = got[0]
        # A NUL would terminate the value early on the reading side, which
        # compares with memcmp over an explicit length but stores the document
        # as a cstring. Excluded at the source rather than papered over.
        if "\x00" in got or "\x00" in doc:
            continue
        lines.append(
            "%s %s %s" % (kind, doc.encode().hex(), got.encode().hex())
        )

    # `P` vectors: structure rather than value. The expected value is resolved
    # by walking tomllib's nested dicts along the table path.
    for doc, table, key in structural_cases():
        try:
            got = tomllib.loads(doc)
        except Exception as e:                       # pragma: no cover
            raise SystemExit("structural case tomllib rejects:\n%r\n%s" % (doc, e))
        node = got
        if table:
            for seg in _split_table(table):
                node = node[seg]
        val = node[key]
        if isinstance(val, bool):
            val = "true" if val else "false"
        else:
            val = str(val)
        lines.append("P %s %s %s %s" % (
            doc.encode().hex(), table.encode().hex(),
            key.encode().hex(), val.encode().hex()))

    path = os.path.join(outdir, "strings.vec")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s (%d vectors)" % (path, len(lines)))


if __name__ == "__main__":
    main()
