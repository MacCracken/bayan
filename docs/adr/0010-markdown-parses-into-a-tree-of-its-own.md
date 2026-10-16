# 0010 — Markdown parses into a tree of its own

**Status**: Accepted
**Date**: 2026-10-15 (bayan 1.9.0)

## Context

The roadmap's 1.9.0 slot asks for `bayan_markdown_parse(src)` returning a tree of headings,
paragraphs, lists, code, links, images, emphasis, block quotes and breaks, with GFM's tables, task
lists, strikethrough and autolinks behind a flag, and `bayan_markdown_to_html`. mneme hand-rolls a
Markdown subset until it exists, and the PDF layout API the roadmap wants after it walks the same
tree.

bayan already has two trees and has decided twice which to reuse.
[ADR 0008](0008-yaml-parses-into-the-json-value-tree.md) put YAML into the json value tree because
the two formats share a data model; [ADR 0002](0002-pdf-objects-do-not-reuse-the-json-value-tree.md)
gave PDF a graph of its own because PDF has types the json cell cannot hold. Markdown is the second
case. A document is an ordered tree of typed nodes, each with fields of its own kind: a heading's
level, a list's start number, delimiter and tightness, a link's destination and title, a code
block's info string and fence, a table cell's alignment, a task item's state.

The parse decides the tree's shape as much as the format does. CommonMark's inline algorithm (the
spec's appendix, which cmark and commonmark.js both implement) makes text nodes for delimiter runs
and brackets first, then moves the runs of siblings between an opener and a closer into a new
emphasis or link node, and trims the delimiters' text in place. A setext underline turns a
paragraph into a heading after the fact; a table takes over the paragraph above its delimiter row;
a paragraph that was only link reference definitions leaves the tree. Each is a constant-time
pointer change in a linked tree.

## Decision

**Markdown gets its own node: a 128-byte cell with kind, parent, first and last child, previous and
next sibling, a text slot, and a few numeric and string fields whose meaning depends on the kind,
as cmark's node does.**

- Kinds are `MD_K_*` (11 blocks, 10 inlines), extension flags `MD_EXT_*`, table alignments
  `MD_ALIGN_*`.
- The public surface is accessors: `bayan_markdown_kind`, the five links, `child_count` and
  `child(i)`, and one accessor per field (`level`, `url`, `title`, `info`, `fenced`,
  `list_ordered`, `list_start`, `list_tight`, `task`, `align`, `row_header`, `text`). Each returns
  0 for a node of another kind, and for 0 (`task` returns -1), never another kind's field.
- The parse state is per call, as json's and yaml's are, and nesting is capped at 128 levels from
  the first release: a deeper document is refused with "nesting too deep".
- Every allocation goes through an allocator (`bayan_markdown_parse_a`, `bayan_markdown_to_html_a`;
  `default_alloc()` otherwise), and a refused one makes the call return 0.

## Consequences

- **Positive** — the spec's algorithms run as written: moving a run of inlines into an emphasis or
  link node, or a paragraph out of the tree, is pointer surgery, never a copy.
- **Positive** — one walk serves every renderer. `bayan_markdown_to_html` is one, and the PDF
  layout API the roadmap plans will be another, over the same accessors.
- **Negative** — a fourth tree in bayan, beside json's value cells, PDF's objects and TOML's pairs,
  with its own accessors to learn. A consumer that wants the document as JSON converts it itself.
- **Negative** — 128 bytes a node, and the bump allocator keeps every block it hands out: a
  document costs memory in proportion to its node count, released only with the allocator.
- **Neutral** — the kinds and flags are `var`s, like json's `JSON_K_*`, so they join the roadmap's
  `const` migration (1.10.0).

## Alternatives considered

- **The json value tree** (an object per node: `type`, `children`, fields by key). Every node would
  cost an object, its key strings and an array for its children; every field read would be a lookup
  by name; and the inline algorithm's moves would copy array slices. ADR 0008's reason for reusing
  the tree, one loader for two formats with one data model, does not apply: nothing else in bayan
  produces documents.
- **An event stream, no tree** (enter/leave callbacks as the document is read). It suits a renderer
  that writes straight through, but CommonMark cannot be read that way: whether `*` is emphasis, or
  `[` a link, is known only when a later delimiter or definition arrives, and a definition may come
  after its first use. The layout API needs the tree in any case.
- **cmark's API names** (`cmark_node_first_child` and so on). bayan's modules are named `bayan_*`,
  and a cmark-shaped surface would invite the expectation of cmark's behaviour where bayan differs
  on purpose ([ADR 0011](0011-markdown-raw-html-is-text.md)).
