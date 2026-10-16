#!/usr/bin/env python3
"""Generate YAML quoted-scalar vectors from an independent oracle: PyYAML (1.8.0).

The expected values come from `yaml.safe_load`, NOT from bayan. Until 1.8.0
src/yaml.cyr kept a quoted scalar's body verbatim, "the toml convention" that
toml itself dropped at 1.5.3: "C:\\tmp" came back with both backslashes,
"a\\nb" with no newline, and every scan that tracked quotes took the first
quote character as the close, so `"x\\" # y"` lost ` # y"` to the comment
stripper. ADR 0009 is the argument for decoding in the parser.

Format, one vector per line: a kind tag and hex-encoded fields.

    S <doc> <value>    the string at key `k` of `k: <scalar>`
    K <doc> <key>      the one key of `<quoted key>: 1`
    A <doc> <value>    element 0 of `k: [<scalar>, x]`
    X <doc>            a document PyYAML refuses; bayan must refuse it too

Every vector is checked with the oracle before it is written: a document
PyYAML reads differently from the recorded value, or reads at all for an `X`,
aborts generation.

One divergence is deliberate and is not a vector: PyYAML accepts a surrogate
escape (\\ud800) into a Python str, which has no UTF-8 form; bayan refuses it.
tests/bayan.tcyr pins that.

PyYAML is not in Python's stdlib. CI installs the distribution's python3-yaml
when it is missing, as the aarch64 job installs qemu-user.

Regenerate with:  python3 scripts/gen-yaml-vectors.py tests/fixtures/yaml
"""
import os
import random
import sys

import yaml

PLAIN = ["a", "b", "z", " ", "  ", "#", " #", ":", ": ", ",", "[", "]", "{", "'", "\u00e9", "\U0001F600",
         "\t", "-", "!", "&", "*", "%", "@", "`", "x y", "0"]
D_ESC = ["\\n", "\\t", "\\\\", '\\"', "\\/", "\\0", "\\a", "\\b", "\\v", "\\f", "\\r", "\\e", "\\ ",
         "\\N", "\\_", "\\L", "\\P", "\\x41", "\\xe9", "\\x00", "\\u00e9", "\\u2028", "\\uFFFD",
         "\\U0001F600", "\\U0010FFFF", "\\\t"]
BAD = ["\\q", "\\x4", "\\xZZ", "\\u12", "\\u12G4", "\\U0011FFFF", "\\U110000", "\\c", "\\%"]


def load(doc):
    try:
        return True, yaml.safe_load(doc)
    except Exception:
        return False, None


def utf8_ok(v):
    try:
        v.encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def hx(s):
    b = s.encode("utf-8")
    return b.hex() if b else "-"


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    rnd = random.Random(1800)
    lines, seen = [], set()

    def emit(rec):
        if rec not in seen:
            seen.add(rec)
            lines.append(rec)

    def double_body():
        # Tokens joined; a raw `"` never appears unescaped, so the scalar is one.
        return "".join(rnd.choice(PLAIN + D_ESC) for _ in range(rnd.randint(0, 7)))

    def single_body():
        # A `'` in the text is written doubled.
        text = "".join(rnd.choice(PLAIN + ["\\", '"', "\\n", "'"]) for _ in range(rnd.randint(0, 7)))
        return text.replace("'", "''")

    for i in range(4000):
        q = rnd.choice(['"', "'"])
        sc = q + (double_body() if q == '"' else single_body()) + q
        tail = rnd.choice(["", "", " # trailing comment", "   "])
        kind = rnd.choice("SSSKA")
        if kind == "S":
            doc = "k: " + sc + tail
        elif kind == "K":
            doc = sc + ": 1" + tail
        else:
            doc = "k: [" + sc + ", x]" + tail
        ok, v = load(doc)
        if not ok or not isinstance(v, dict) or len(v) != 1:
            continue
        if kind == "S":
            want = v.get("k")
        elif kind == "K":
            (want,) = v.keys()
            if v[want] != 1:
                continue
        else:
            seq = v.get("k")
            if not isinstance(seq, list) or len(seq) != 2 or seq[1] != "x":
                continue
            want = seq[0]
        if not isinstance(want, str) or not utf8_ok(want):
            continue
        assert load(doc) == (True, v)
        emit(f"{kind} {hx(doc)} {hx(want)}")

    # Documents PyYAML refuses: escapes YAML does not define, short or non-hex
    # hex escapes, code points past U+10FFFF.
    for bad in BAD:
        for pre in ["", "a", "\\n"]:
            for form in ("k: \"{}\"", "\"{}\": 1", "k: [\"{}\"]"):
                doc = form.format(pre + bad)
                ok, _ = load(doc)
                assert not ok, doc
                emit(f"X {hx(doc)}")

    p = os.path.join(out_dir, "strings.vec")
    with open(p, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    counts = {k: sum(1 for l in lines if l[0] == k) for k in "SKAX"}
    print(f"wrote {p} ({len(lines)} vectors: {counts['S']} value, {counts['K']} key, "
          f"{counts['A']} flow element, {counts['X']} refused)")


if __name__ == "__main__":
    main()
