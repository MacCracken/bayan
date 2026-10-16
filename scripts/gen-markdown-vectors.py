#!/usr/bin/env python3
"""Generate the Markdown vectors from the upstream test suites (1.9.0).

The expected HTML comes from the suites' own authors, NOT from bayan: the
CommonMark 0.31.2 spec's examples, the GFM 0.29 spec's extension examples,
cmark-gfm's extension tests, and the regression suites of cmark and cmark-gfm.
The upstream files sit verbatim in tests/fixtures/markdown/upstream/, each
pinned here by SHA-256; a changed file aborts generation. Their licences are in
that directory's README.md.

bayan is checked against every example except the ones this file excludes, and
each exclusion carries its reason, checked against the example itself:

  raw HTML    bayan renders raw HTML as text (src/markdown.cyr's header, ADR
              0011). An example excluded for it must have a tag in its source
              that its expected HTML passes through.
  footnotes   cmark-gfm's footnote extension, which bayan does not have. The
              source must use `[^`.
  0.29 core   the GFM spec's CommonMark sections are CommonMark 0.29; bayan is
              checked against 0.31.2's own examples instead.

One transform, and only on cmark-gfm's extension tests: its renderer writes a
task item's checkbox `<input type="checkbox" disabled="" />`; the GFM spec, and
bayan, write `<input disabled="" type="checkbox">`. The same element.

Format, one vector per line, fields hex-encoded (`-` when empty):

    V <flags> <example> <markdown> <html>    parse with flags, render, compare
    C <flags> <example> <markdown>           parse with flags: no crash, a tree

tests/vectors.tcyr runs them. CI regenerates the files and requires no change.

Regenerate with:  python3 scripts/gen-markdown-vectors.py tests/fixtures/markdown
"""
import hashlib
import json
import os
import re
import sys

UP = {
    "spec-0.31.2.json": "d431b29d97b6f73e69d547109cf5081578fac931e72afe95639ebe766c1b2a20",
    "gfm-spec-0.29.txt": "7d8e5814befec287ac116786d81ff14e0adc9b13295b4494649e995408fd871c",
    "cmark-regression.txt": "c4e69ed0a38c786d01bb4bb1b605ed382d4bee037305b7ae9e3e21f10d20e527",
    "cmark-gfm-extensions.txt": "a2a45e98be9fca95f564f927265a0f63beea6cae5369d1cf4bde44caa51b2a3a",
    "cmark-gfm-regression.txt": "0920d7e8134d5e4ec3693f3f52d904b42de45e23a66c29f54fe714dc54213fd9",
}

GFM = 15    # MD_EXT_GFM: tables, task lists, strikethrough, autolinks

RAW, FOOT, CORE = "raw HTML", "footnotes", "0.29 core"

# CommonMark 0.31.2: the two HTML sections, and the examples elsewhere whose
# expected HTML passes a tag through. A section exclusion for raw HTML takes only
# the examples that pass one through: the rest test that a malformed tag stays
# text, as bayan writes every tag, and they are vectors.
CM_SECTIONS = {"HTML blocks": RAW, "Raw HTML": RAW}
CM_EXAMPLES = {21: RAW, 31: RAW, 201: RAW, 308: RAW, 309: RAW, 344: RAW, 475: RAW, 476: RAW,
               477: RAW, 491: RAW, 494: RAW, 524: RAW, 536: RAW, 642: RAW, 643: RAW}
# GFM 0.29: only its extension examples; the tag filter is raw HTML.
GFM_EXAMPLES = {652: RAW}
# cmark-gfm's extension tests, by section.
CMX_SECTIONS = {"Embedded HTML": RAW, "HTML tag filter": RAW, "Footnotes": FOOT,
                "When a footnote is used multiple times, we insert multiple backrefs.": FOOT,
                "Footnote reference labels are href escaped": FOOT}
CMREG_EXAMPLES = {3: RAW, 6: RAW, 8: RAW, 12: RAW, 15: RAW, 18: RAW, 19: RAW, 20: RAW, 23: RAW, 28: RAW}
CMXREG_EXAMPLES = {3: RAW, 6: RAW, 9: RAW, 14: RAW, 17: RAW,
                   13: FOOT, 20: FOOT, 21: FOOT, 22: FOOT, 23: FOOT, 24: FOOT}

FENCE = "`" * 32


def spec_txt(path):
    """The examples of a spec.txt-format file, as spec.json rows (tabs written as U+2192)."""
    lines = open(path, encoding="utf-8").read().split("\n")
    out, section, i = [], "", 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(FENCE + " example"):
            tag = ln[len(FENCE) + len(" example"):].strip()
            i += 1
            md = []
            while lines[i] != ".":
                md.append(lines[i])
                i += 1
            i += 1
            html = []
            while lines[i] != FENCE:
                html.append(lines[i])
                i += 1

            def body(xs):
                return ("\n".join(xs) + "\n" if xs else "").replace("→", "\t")
            out.append({"example": len(out) + 1, "section": section, "extension": tag,
                        "markdown": body(md), "html": body(html)})
        elif re.match(r"^#{1,6} ", ln):
            section = re.sub(r"^#+ ", "", ln).strip()
        i += 1
    return out


def passes_raw(e):
    """1 when the expected HTML passes through a tag of the source."""
    tags = set(re.findall(r"<[A-Za-z!?/][^\s<>]*", e["markdown"]))
    return any(t in e["html"] for t in tags)


def check_reason(src, e, reason):
    md = e["markdown"]
    if reason == RAW:
        assert passes_raw(e), (src, e["example"], "excluded as raw HTML, passes none through")
    elif reason == FOOT:
        assert "[^" in md, (src, e["example"], "excluded as footnotes, has no [^")
    else:
        assert reason == CORE, reason


def hx(s):
    b = s.encode("utf-8")
    return b.hex() if b else "-"


def write(out_dir, name, rows):
    with open(os.path.join(out_dir, name), "w") as fh:
        fh.write("\n".join(rows) + "\n")


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/markdown"
    os.makedirs(out_dir, exist_ok=True)
    # The upstream files are read from the repository, wherever the vectors are written (CI writes
    # them to a temporary directory and compares).
    up = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "fixtures", "markdown", "upstream")
    for name, want in UP.items():
        got = hashlib.sha256(open(os.path.join(up, name), "rb").read()).hexdigest()
        assert got == want, (name, "is not the pinned upstream file", got)
    summary = []

    def run(src, examples, flags, by_section, by_example, transform=None, vname=None):
        rows, skipped, used_s, used_e, kept = [], {}, set(), set(), 0
        for e in examples:
            reason = by_example.get(e["example"]) or by_section.get(e["section"])
            used_e.add(e["example"])
            used_s.add(e["section"])
            if reason == RAW and e["example"] not in by_example and not passes_raw(e):
                reason = None
                kept = kept + 1
            if reason is None and src == "gfm" and not e["extension"]:
                reason = CORE
            if reason is not None:
                check_reason(src, e, reason)
                skipped[reason] = skipped.get(reason, 0) + 1
                continue
            html = e["html"]
            if transform:
                html = transform(html)
            if html == "<IGNORE>\n":
                rows.append("C %d %d %s" % (flags, e["example"], hx(e["markdown"])))
            else:
                rows.append("V %d %d %s %s" % (flags, e["example"], hx(e["markdown"]), hx(html)))
        assert set(by_example) <= used_e, (src, "an excluded example does not exist", set(by_example) - used_e)
        assert set(by_section) <= used_s, (src, "an excluded section does not exist", set(by_section) - used_s)
        write(out_dir, vname, rows)
        summary.append("%s: %d vectors (%d of them from an excluded section, passing no tag), excluded %s"
                       % (vname, len(rows), kept, ", ".join("%d %s" % (n, r) for r, n in sorted(skipped.items())) or "none"))

    cm = json.load(open(os.path.join(up, "spec-0.31.2.json"), encoding="utf-8"))
    run("cm", cm, 0, CM_SECTIONS, CM_EXAMPLES, vname="commonmark-0.31.2.vec")
    run("gfm", spec_txt(os.path.join(up, "gfm-spec-0.29.txt")), GFM, {}, GFM_EXAMPLES, vname="gfm-0.29.vec")

    def checkbox(h):
        return (h.replace('<input type="checkbox" checked="" disabled="" />', '<input checked="" disabled="" type="checkbox">')
                 .replace('<input type="checkbox" disabled="" />', '<input disabled="" type="checkbox">'))
    run("cmx", spec_txt(os.path.join(up, "cmark-gfm-extensions.txt")), GFM, CMX_SECTIONS, {}, checkbox,
        vname="cmark-gfm-extensions.vec")
    run("cmreg", spec_txt(os.path.join(up, "cmark-regression.txt")), 0, {}, CMREG_EXAMPLES, vname="cmark-regression.vec")
    run("cmxreg", spec_txt(os.path.join(up, "cmark-gfm-regression.txt")), GFM, {}, CMXREG_EXAMPLES,
        vname="cmark-gfm-regression.vec")
    for line in summary:
        print(line)


if __name__ == "__main__":
    main()
