# Upstream Markdown test suites

These files are copied verbatim from their projects; `scripts/gen-markdown-vectors.py`
pins each by SHA-256 and turns their examples into the `../*.vec` vectors that
`tests/vectors.tcyr` runs. Do not edit them: replace a file with a newer upstream
copy and update its pin and the provenance below.

| File | From | Licence |
|---|---|---|
| `spec-0.31.2.json` | <https://spec.commonmark.org/0.31.2/spec.json>, the examples of the CommonMark Spec 0.31.2, © John MacFarlane | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `gfm-spec-0.29.txt` | `test/spec.txt` of [github/cmark-gfm](https://github.com/github/cmark-gfm) at `27d942c8b0a62d192f616e5bf3578f4b6a89e180`: the GitHub Flavored Markdown Spec 0.29-gfm, © GitHub, Inc., based on the CommonMark Spec, © John MacFarlane | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `cmark-regression.txt` | `test/regression.txt` of [commonmark/cmark](https://github.com/commonmark/cmark) at `ee05faf6cd95f6c949e2c0d17c73041dea7214fe` | BSD 2-Clause, `cmark-COPYING` |
| `cmark-gfm-extensions.txt` | `test/extensions.txt` of github/cmark-gfm at `27d942c8b0a62d192f616e5bf3578f4b6a89e180` | BSD 2-Clause, `cmark-COPYING` |
| `cmark-gfm-regression.txt` | `test/regression.txt` of github/cmark-gfm at the same commit | BSD 2-Clause, `cmark-COPYING` |
| `cmark-COPYING` | `COPYING` of commonmark/cmark at the commit above; cmark-gfm's `COPYING` at its commit is byte-identical (SHA-256 `c22e885f…e6d9a9`) | — |

The two specs are licensed CC BY-SA 4.0, which Creative Commons has declared
compatible with GPLv3: the vectors made from them (`../commonmark-0.31.2.vec`,
`../gfm-0.29.vec`, hex-encoded copies of the examples) are adaptations, and are
distributed with bayan under GPL-3.0-only, attributed as above. The cmark and
cmark-gfm test files are under the BSD 2-Clause licence in `cmark-COPYING`, whose
notice travels with them and with the vectors made from them.

Which examples bayan is checked against, which it is not, and why, is the
generator's docstring.
