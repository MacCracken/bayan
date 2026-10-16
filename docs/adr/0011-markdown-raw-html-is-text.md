# 0011 — Markdown's raw HTML is text, and its dangerous URLs are dropped

**Status**: Accepted
**Date**: 2026-10-15 (bayan 1.9.0)

## Context

CommonMark passes HTML through. It defines seven kinds of HTML block, each with its own start and
end condition, and inline open and closing tags, comments, processing instructions, declarations
and CDATA, and its HTML renderer copies all of them to the output unchanged. A Markdown document is
then as able to carry script into a page as an HTML one, and a renderer that follows the spec is
safe only behind a sanitiser.

bayan's consumers render documents for a reader and for a PDF. PDF has no HTML; a reader view of
untrusted notes is exactly where passing script through matters. The reference implementations do
not follow their own spec here by default: cmark's default ("safe") renderer replaces raw HTML with
`<!-- raw HTML omitted -->` and writes an empty `href` for a `javascript:`, `vbscript:`, `file:` or
`data:` URL, and markdown-it's default (`html: false`) does not recognise HTML at all, so it is
text.

The roadmap asks for a CommonMark fixture subset "with the cut-off between what is rejected and
what is accepted documented". Raw HTML is most of that cut-off.

## Decision

**bayan does not recognise raw HTML. HTML blocks and inline tags are text, and the renderer escapes
them like any other text: `<div>` is written `&lt;div&gt;`. And `bayan_markdown_to_html` writes an
empty `href` or `src` for a `javascript:`, `vbscript:`, `file:` or `data:` URL (but `data:image/`
`png`, `gif`, `jpeg` or `webp`), in any letter case, checked after entities and escapes are
decoded. That is cmark's rule.**

- The tree keeps every URL as written (`bayan_markdown_url`): the rule is the HTML renderer's, for
  a caller that renders the tree itself to apply or not.
- No flag turns raw HTML on.

## Consequences

- **Positive** — bayan's HTML carries no markup from its input. Every `<` in the output opens a tag
  the renderer wrote, and `tests/markdown.fcyr` checks exactly that on every document it makes: the
  tags are from the renderer's set and nest.
- **Positive** — none of the HTML-block and tag grammar to carry. It is a large share of the spec,
  and it would recognise markup only for the renderer to escape it.
- **Negative** — part of CommonMark is out of scope: 72 of the spec's 652 examples (57 in its two
  HTML sections; 7 others there test that a malformed tag stays text, which bayan does, and run),
  10 of cmark's 32 regression tests and 5 of cmark-gfm's 26. `scripts/gen-markdown-vectors.py`
  names each, and refuses an exclusion whose example does not pass a tag through. GFM's tag filter
  has nothing to filter.
- **Negative** — a document that uses HTML on purpose (`<details>`, `<kbd>`, an `<img>` with a
  width) shows its tags as text, and an HTML block's lines are Markdown: `foo` then `<div>` on the
  next line is one paragraph here, where CommonMark ends the paragraph.
- **Neutral** — a trusted-content flag that passes raw HTML through would mean writing the HTML
  grammar after all. Nothing asks for it yet.

## Alternatives considered

- **Pass it through, as the spec renders it.** Complete, and unsafe by default for every consumer
  that renders documents it did not write: each would need a sanitiser bayan does not have.
- **cmark's safe mode** (recognise raw HTML, write `<!-- raw HTML omitted -->`). Its block structure
  is the spec's, but the content disappears without a trace in the output, and it needs the whole
  HTML grammar.
- **Recognise raw HTML as the spec does, then write it escaped.** The block structure would be the
  spec's (an HTML block ends a paragraph, its lines are not Markdown), at the cost of the whole
  grammar again, for output that differs from the text view only in which lines are parsed as
  Markdown.
