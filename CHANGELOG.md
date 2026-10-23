# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.11.1] — 2026-10-23

Patch release: the bayan findings of cyrius 6.7.18's security audit
(`docs/audit/2026-10-22-security-audit.md` in cyrius), every one fixed, and the audit's JSON
parser work. Pin unchanged at **6.7.16**; the floor stays 6.7.9.

> ### ⚠ What to re-check — invalid input that parsed now refuses (the user's decisions at the audit)
>
> - **A duplicate JSON object key refuses the document**, in all three parsers, comparing keys
>   decoded (`"\u0061dmin"` is `"admin"`). The tree and streaming parsers fail with
>   "duplicate key" at the second key. **`bayan_json_parse` returns 0** for one (its documented
>   failure value, until now only a refused allocation), with "duplicate key" in
>   `bayan_json_last_error()` / `_pos()`: check its result for 0 before `vec_len`. A tree built
>   by hand with `bayan_json_v_obj_set` may still repeat a key, and the lookups still answer the
>   first. yaml already refused duplicates; it is unchanged but for the cost.
> - **A malformed JSON number is refused by name in the streaming parser as in the tree**:
>   `-`, `1.`, `1e`, `-e5`, `-.5` and an integer outside i64 (`18446744073709551616` reached
>   `on_int` as 0). **A leading zero (`01`, `-01`, `00`) is refused by both**, "a number may not
>   have a leading zero" (RFC 8259 section 6). yaml's numbers are unchanged (`01` stays a
>   string there).
> - **The base64 decoders refuse what is not canonical RFC 4648**: `=` anywhere but the padding
>   that ends the last group, padding of the wrong length (base64url: none, or exactly to a
>   multiple of 4), a one-character last group, non-zero bits below the last byte (`QR==`), and
>   the other alphabet's characters. The reason is in the new **`bayan_base64_last_error()`**.
> - **bayan needs stdlib `slice`.** json's parsers read through bounds-checked slices: a
>   hand-written include list adds `lib/slice.cyr` before bayan (the full bundle and the json,
>   yaml and toml-tree sublibs; their `.deps` and `# Requires` name it). A read past the input
>   is "slice bounds violation" and exit 134. JSON parsing costs about 1.5x what it did.
> - **bayan needs stdlib `hashseed`** for the same four (`.deps` and `# Requires` name it):
>   json's duplicate-key set hashes a peer's keys with the stdlib's per-process seed.
> - **PDF:** a stream that failed to decode stays failed in its document, so install the inflate
>   hook before asking for a stream's bytes; every inflate attempt counts against the 512 MiB
>   per-document budget, not only a success; and the page content handed out (and so scanned by
>   text extraction) counts against a new 512 MiB per-document budget, `_PDF_MAX_CONTENT`:
>   past it a page answers "" with "page content bytes exceed the per-document limit".

### Security

- **CYRIUS-2026-0045 — the PDF Flate bomb guard was bypassed.** `bayan_pdf_stream_data_a`
  memoised only a successful decode, and `_pdfz_inflate_a` charged `_pdfz_budget` only with a
  success's final length. A stream the inflate hook could not decode doubled its way through
  buffers the 512 MiB guard never saw, once for every page naming it: 48 pages of a 25 KB file
  reached 1.9 GB, and the ratio-capped hook bayan recommends, 1.96 GB from 66 KB. A failure now
  sets the stream's cache to the static empty Str, so it is decoded once; each attempt charges
  its buffer before allocating it (a buffer the budget cannot cover shrinks to the room left, and
  no room is the refusal, so `/DL` is trusted no further); a rejected attempt's buffer goes back
  through `free_via` on every refusal, a hook reporting more bytes than the buffer holds among
  them, and a refused `Str` header after an output that fitted is named ("FlateDecode: out of
  memory wrapping the output"; the stream used to read "" with no error). The audit's files hold
  at 42 MB and 7.9 MB. Rows: `tests/pdf_flate.tcyr` "a failing Flate stream is decoded once, and
  charged" and "an inflate attempt's buffer goes back on every refusal".

### Fixed

- **PDF text extraction work multiplied with page references to one content stream** (audit
  Finding 25). A decode is memoised, but each page naming the stream was scanned in full, up to
  the walk's 1,048,576 references: 11.6 s from 15.8 KB at 128. Every byte
  `bayan_pdf_page_content_a` hands out is charged to `_PDF_MAX_CONTENT` (PdfDoc +200;
  `_PDF_DOC_SIZE` 200 → 208), a `/Contents` array's streams one by one before each is copied.
  The same file: 2.9 s, and no longer growing with the references.
- **yaml was quadratic in a mapping's size** (Finding 15): each key's duplicate check walked
  every key before it, 14.4 s for 40,000 keys (480 KB). It uses json's new O(1) key set.
- **The flat TOML parser was quadratic in dotted-key tables** (Finding 17): each dotted key
  walked every table since the header, 4.0 s for 20,000 (300 KB). Past 8 tables under a header
  they are indexed by name; every smaller document allocates what it did. The index is the
  parse's scratch: zeroed before first use and freed when a header drops it and when the parse
  returns. Row: `tests/bayan.tcyr` "the dotted-key index frees only what it built", under an
  allocator that frees.
- **The streaming JSON parser wrapped out-of-range integers and accepted digitless numbers**
  (Finding 16). Both descents now share one scanner, `_jp_scan_number`, and the stream checks
  the i64 range as the tree does.
- **JSON accepted duplicate object keys and answered the first** (Finding 24), the opposite of
  most readers, so a validating bayan component and a last-wins reader disagreed about
  `{"role":"user","role":"admin"}`. A per-object key set (`_jk_*`: 32 keys in place, no
  allocation; past that a hash table) refuses one in O(1). `bayan_json_parse`'s header now says
  its lookups compare raw keys and must not decide an allowlist. The table's hash takes the
  stdlib's per-process seed and finalizer (`lib/hashseed.cyr`): unseeded, keys precomputed once
  from its published constants to share a slot made every JSON parser, and yaml's mappings,
  quadratic again (10,000 keys, 147 KB: 309 ms against 6 ms). Row: `tests/bayan.tcyr` "the key
  set's hash is seeded per process".
- **The base64 decoders accepted invalid and non-canonical input** (Finding 18): `QQ==QUFB`
  gave `41 00 00 41 41 41`, `====` one `00`, `QR==` what `QQ==` gives, base64url's `QUFBQ`
  `41 41 41`. One core now decodes both alphabets, refusing each by name, without the per-call
  256-byte table (unchecked, never freed); every allocation is checked.
- **`bayan_base64url_encode` stored through a refused output buffer**; it returns 0, as
  `bayan_base64_encode` has since 1.5.9.
- **The PDF writer's deflate loop freed none of its attempt buffers.** Each "too small" retry,
  a hook error, a hook reporting more bytes than the buffer holds and a refused `Str` header
  (which also recorded no reason) kept its buffer under an allocator that frees. Every buffer
  but the output's goes back, as inflate's do, and the header refusal is named ("deflate: out
  of memory wrapping the output"). Row: `tests/pdf_flate.tcyr` "a deflate attempt's buffer goes
  back unless it is the output".

### Hardening

- **json's three parsers read the document through bounds-checked slices** (cyrius 6.7.18 D1).
  Each reader wraps its `(buf, len)` in a fn-local `[u8]` slice and reads `bs[i]`, checked in
  every build. `tests/json_slice_trap.cyr` (a new CI step) makes a read past the input through
  each parser's readers and wants the trap.

### Tests

- `tests/json_parsers.fcyr` (new): the tree, streaming and flat parsers over 14 seeds after
  1..4 seeded mutations (truncation, byte edits, repeated and swapped spans, boundary numbers,
  a repeated first member, wraps 126..129 deep), 60,000 documents. The two descents must agree
  (acceptance, message, events), a tree's serialisation round-trip, the flat parser return an
  accepted object's members, and every answer be the same at a PROT_NONE page and inside a
  buffer whose bytes past the input would change it. Passes plain, `--poison`, `--poison=ab` and
  `--bounds`.
- `tests/json.fcyr` gains property (f), a duplicate key refuses the flat parse, and a REPEATED
  corpus; its generator now writes distinct keys.
- `tests/parse_scaling.cyr` (new, a CI step on x86_64 and aarch64): yaml mapping keys, the json
  tree, flat and stream parsers' object keys and flat toml dotted keys must cost linearly.
- `tests/bayan.tcyr` +95 (1,987 → 2,082), `tests/pdf_flate.tcyr` +40 (19 → 59). The rows that
  leaned on an accepted duplicate key now build their repeats by hand.

Public API: 1 function added (`bayan_base64_last_error`), none removed or deprecated.

## [1.11.0] — 2026-10-22

Minor release, the roadmap's 1.11.0 slot. Pin unchanged at **6.7.16**; the floor stays 6.7.9,
checked there.

- **`bayan_toml_v_parse`: TOML 1.0.0 into json's value tree**
  ([ADR 0013](docs/adr/0013-toml-parses-into-the-json-value-tree-strictly.md)). It is strict: it
  accepts and refuses what Python's `tomllib` does, and builds the tree `tomllib` builds. CI checks
  this on 3,494 vectors generated from `tomllib`. A scratch differential of 384,384 more documents
  agreed on every one (96,160 accepted, 288,224 refused).
- **The flat lookups name their key type**
  ([ADR 0014](docs/adr/0014-the-flat-lookups-name-their-key-type.md)). Each comes as `_by_cstr`
  and `_by_str`, and the bare names and five aliases are deprecated. They give the same answers.
- **The flat parser's two subset edges** (Known gap 1) have answers in the tree.

Public API: 27 functions and 4 constants added. 13 names deprecated, none removed.

> ### ⚠ What to re-check
>
> - **13 flat lookups warn at every call: rename each to its typed name.** The bare names are
>   `bayan_json_get`, `bayan_json_get_int`, `bayan_toml_get`, `bayan_toml_get_pair`,
>   `bayan_toml_count`, `bayan_toml_get_sections`, `bayan_toml_get_inline` and
>   `bayan_toml_get_array`. Their aliases are `json_get`, `json_get_int`, `toml_get`,
>   `toml_get_sections` and `toml_get_array`. Each warning names its two replacements:
>   - `_by_cstr` takes a C string or a literal;
>   - `_by_str` takes a `Str`.
>
>   A toml call passing a literal becomes `bayan_toml_get_by_cstr(pairs, "k")`. A json call
>   passing `str_from(..)` becomes `bayan_json_get_by_str(pairs, s)`. The deprecated names answer
>   exactly as before, with one difference: a null pairs or key now returns 0 (an empty vec for
>   sections) instead of faulting. A build that treats warnings as errors fails until every call is
>   renamed.
> - **The toml bare names now carry `key: cstring`,** so passing a `Str` to one warns twice:
>   deprecated, and "passing Str-typed". It was a silent "not found" before.
> - **Nothing else changes.** No existing function's answer moved, and no sublib's contents changed
>   except its version header and the deprecations. `bayan-toml` is still the flat parser alone;
>   the tree parser is the new `bayan-toml-tree`.

### Added — `bayan_toml_v_*`, TOML into the tree

- **The parser.** It has the forms yaml and json have:
  - `bayan_toml_v_parse(src)` and `bayan_toml_v_parse_a(a, src)` take a `Str`;
  - `bayan_toml_v_parse_buf(buf, len)` and `_buf_a` take a span;
  - `bayan_toml_v_parse_ctx(ps, buf, len)` and `_ctx_a` are the reentrant forms, on json's per-call
    state.

  Each returns the root table (a `JTAG_OBJ`), or 0 with the reason. Read the reason with
  `bayan_toml_v_last_error()` / `_last_error_pos()`, or from the state with
  `bayan_toml_v_state_error(ps)` / `_pos(ps)`. A table is read with `bayan_json_v_*`, and a key
  with `bayan_json_v_obj_get_by_cstr` / `_by_str`.
- **The mapping.**
  - Tables and inline tables are objects, keys in document order.
  - Arrays and arrays of tables are arrays.
  - Strings are decoded (all four forms; CR LF in a multi-line string reads as LF).
  - Integers are i64.
  - Floats are correctly rounded through the stdlib's `f64_parse_n`; `inf` and `nan` keep their
    sign.
  - A **date or time is a string cell holding its text as written.**
    `bayan_toml_v_datetime_kind(v)` says which kind: `TOML_DT_OFFSET`, `TOML_DT_LOCAL`,
    `TOML_DT_DATE`, `TOML_DT_TIME`. The parser keeps the kind in the cell's reserved word, so a
    cell json or yaml made reads 0.
- **What `tomllib` refuses is refused, with a message and a byte offset.** That covers a duplicate
  key, a table defined twice, and a dotted key into a table a header defined (or a header naming a
  table a dotted key opened). It also covers extending an inline table or static array, invalid
  escapes and UTF-8, control characters, an impossible date, a number TOML does not have, and
  statements that do not end their line. The model of which tables are defined, and when, is
  `tomllib`'s three flags. The parser keeps them in each container's reserved word during the
  parse and clears them before returning.
- **Where the tree cannot follow `tomllib`, bayan refuses:**
  - an integer outside i64 ("integer out of range"; `tomllib` returns a Python int);
  - nesting past json's cap of 128, counted as json counts ("nesting too deep");
  - bytes that are not UTF-8 ("invalid utf-8"; `tomllib.load` raises `UnicodeDecodeError`).
- **The flat parser's subset edges, answered.** `a."b.c".d = 1` is three nested tables, the middle
  one named `b.c`, apart from `a.b.c.d`. `[[a.b]]` repeated under `[a]` is one array of tables.
  `src/toml.cyr`'s header says the tree has the answers. In the flat API they stay documented.
- **Cost.** A hash index over every key the document defines makes each lookup O(1), so a table of
  n keys costs O(n). On a 3.1 KB Cargo-shaped manifest the tree parse takes about 100 µs and the
  flat parse 30 µs; the flat parse validates nothing and leaves arrays and inline tables as text.
- **Allocation.** Every allocation goes through the allocator given, and the strings are copies,
  so the tree outlives its source. A refused allocation returns 0 with "out of memory", never a
  partial tree.
- **`src/toml_tree.cyr`, in `[lib]` after `yaml.cyr`, and the sublib `bayan-toml-tree`** (dtoa,
  json, toml_tree; 11 stdlib leaves). It shares nothing with `toml.cyr`, so `bayan-toml` and
  `bayan-toml-tree` build side by side (checked, 0 warnings). `bayan-toml-tree` carries json, so,
  like `bayan-yaml`, it cannot sit beside `bayan-json`
  ([architecture note 002](docs/architecture/002-one-copy-of-each-module-per-program.md)).

### Changed — the flat lookups name their key type

- **16 typed lookups.** The json pairs are `bayan_json_get_by_cstr` / `_by_str` and
  `bayan_json_get_int_by_cstr` / `_by_str`. The toml pairs are `bayan_toml_get_by_*`,
  `_get_pair_by_*`, `_count_by_*`, `_get_sections_by_*`, `_get_inline_by_*` and `_get_array_by_*`.
  - `_by_cstr` carries `key: cstring`. On cyrius 6.7.16 a `Str` passed to it warns, whether it is a
    named local, a global or a call's result.
  - `_by_str` compares by the `Str`'s length, so a `Str` cut from a longer one (not NUL-terminated)
    is read correctly.
  - Each keeps its module's rule for a repeated key: json the first pair, toml the last.
  - Each returns 0 for a null pairs or key.
- **The bare names and aliases are deprecated forwarders**, each `#deprecated` with advice naming
  both replacements. The toml ones forward to `_by_cstr`, the json ones to `_by_str`. The aliases
  forward to the typed names, never the deprecated bare ones, whose warning would fire inside the
  bundle. Each toml lookup's three copies of its loop became one private helper taking the key type
  (`_toml_find_pair` and friends).
- **cyrius's `: cstring` diagnostic is no longer bayan's open gap** (Known gap 8). ADR 0004 measured
  it silent on a call's result, a global and a tail call (6.6.12). cyrius fixed that in 6.6.13 from
  bayan's 2026-10-01 filing, and 6.7.16 warns on each. `state.md` called it open until now.
- **CI** (`ci.yml`):
  - The overload-base guard covers every typed lookup: no fn may be named `*_by`.
  - New steps: the toml tree's cost (x86_64 and aarch64), and its vectors regenerating
    identically.
  - The consumer gate probes every new deprecation in every bundle that ships it: `bayan` for all
    13; `bayan-json`, `-yaml` and `-toml-tree` for json's; `bayan-toml` for toml's. Each needs
    exactly its warnings and advice. The json names never stated a key type and keep it unstated,
    so they expect no "passing Str-typed" warning. The gate also pins every new `_by_cstr`'s two
    diagnostics in every such bundle: 81 checks, all green.
- **`dist/` regenerated** (`cyrius distlib --all`): 12 bundles, `bayan-toml-tree` new.
  - `bayan.cyr`, `bayan-json`, `-yaml` and `-toml` carry the typed lookups and deprecations.
  - The other sublibs change only their version header.
  - No existing `.deps` sidecar changes, and a second regeneration changes nothing.

### Tests

- **`tests/fixtures/toml/tree.vec` (new), 3,494 vectors**, from `scripts/gen-toml-tree-vectors.py`
  (`tomllib`, fixed seeds, regenerated in CI). 2,114 parse and 1,380 are refused. Sources:
  - hand-written documents per rule: each table-model case, every escape, number and date form,
    each end of input, the depth cap on both sides;
  - 800 random documents over a small key alphabet, so tables collide and keys repeat;
  - 800 byte-level mutations of those;
  - every document of the string vectors.

  `run_toml_tree` in `tests/vectors.tcyr` writes bayan's tree in the canonical form with its own
  serializer: floats as bits, dates normalized as `tomllib` keeps them. Every error message the
  parser has is reached, most of them dozens of times, except "out of memory" and "null source",
  which the suite drives.
- **The differential, in scratch: 384,384 documents, 0 disagreements** (four seeds, 50,000
  generated and 50,000 mutated each).
- **`tests/toml.fcyr` (new): 120,343 parses, 18,597 of them accepted.** Inputs are token soup,
  random statements and their damage, every prefix of 15 edge documents, and nesting at 120–135
  levels by four routes. Each is parsed against a PROT_NONE page, so no read goes past the input.
  It checks that:
  - a second parse from another address builds an equal tree;
  - a tree is clean (flags cleared, no duplicate key, nothing past 128 levels);
  - one in eight is parsed again with a random allocation refused, and returns 0 with "out of
    memory";
  - nesting past the cap is refused.
- **`tests/toml_scaling.cyr` (new)** times eight families at two sizes, 8× apart: root keys,
  tables, array-of-tables elements, dotted keys, sub-table headers, array values, inline-table keys
  and string escapes. The ratios are 0.8–1.0, against a limit of 3.0.
- **`tests/bayan.tcyr`: 1,889 → 1,987 runtime asserts.**
  - The tree: a manifest walked with json's accessors, every value form and date kind, the
    reserved words cleared.
  - The two subset edges.
  - 13 refusals by message and byte offset.
  - The ctx path leaving the globals alone, the depth cap lowered to 3, the tree outliving its
    source.
  - Each of a 40-key document's 150+ allocations refused alone; the `_a` forms making every
    request through their allocator.
  - The 16 typed lookups: both key types, cut `Str`s, first and last wins, absent and null keys.
  - The alias rows of the 5 deprecated aliases moved to `tests/deprecated_lookup.cyr`.
- **`tests/deprecated_lookup.cyr`: 13 → 36 asserts.** Each of the 13 newly deprecated names answers
  what its typed name answers. `scripts/deprecated-lookup.sh` now holds advice per name, and
  requires exactly 31 warnings.
- **Mutation pass, 28 mutants in scratch copies: 26 fail a suite, and 2 are equivalent.** The
  mutants cover:
  - the key index (a constant hash: the scaling gate);
  - each table-model rule; year 0, the century leap rule, second 60, leading zeros, the i64 edge;
  - the extra closing quotes, the line-ending backslash, surrogates, DEL in a comment, the depth
    edge, a refused index growth, the multi-line newline trim, `\f`;
  - the trailing commas of inline tables and arrays, escapes in literal strings, a date's kind,
    the flags left uncleared;
  - and, in the flat lookups, first-wins, the key type, and the null guard.

  The two equivalents:
  - Dropping the PENDING bit's own set only lets a table walked by several dotted keys into the
    finalize list more than once. Every answer is the same; the bit stays, as a dedup.
  - Dropping the string scan's skip of the whitespace after a line-ending backslash changes nothing,
    because that run is legal body text and the decoder drops it on its own. So that loop was dead,
    and it is gone. The vectors, the suite, the fuzz harness and the whole differential (384,384
    documents, 0 wrong) were re-run after.
- **Benchmarks:** two rows in `tests/bayan.bcyr`, the tree and the flat parse of the same 3.1 KB
  manifest.
- **Gates** (state.md has the recipes):
  - every `ci.yml` job, each in a fresh tree, on the 6.7.16 release (signature verified): all green;
  - aarch64 under qemu: the suite, all four fuzz harnesses, both cost checks;
  - the floor, on the 6.7.9 release in a scratch copy: build, suite, raw include, `distlib --check`
    of the 6.7.16-generated bundles, consumer gate.

### Docs

- **[ADR 0013](docs/adr/0013-toml-parses-into-the-json-value-tree-strictly.md)**: the oracle, a
  date as a string that remembers its kind, the refusals where the tree cannot follow, the
  separate module and sublib, the index. Alternatives: a lenient tree parse, a `JTAG_DATETIME`
  tag, normalized date text, refusing dates, the tree in `bayan-toml`, pair-walking lookups.
- **[ADR 0014](docs/adr/0014-the-flat-lookups-name-their-key-type.md)**: ADR 0004 applied to the
  flat lookups, with the 6.7.16 re-measurement of both diagnostics.
- **[Architecture note 002](docs/architecture/002-one-copy-of-each-module-per-program.md)** gains
  `toml_tree` and the `bayan-toml-tree` pairings. json's cell layout comment says what the
  reserved word holds now. `src/toml.cyr`'s header points at the tree for its subset edges.
- **The README** lists `toml_tree`, and `markdown`, which it lacked since 1.9.0, and says which
  sublibs carry json. Its Status paragraph still says 1.5.4; state.md holds the version.
- **The roadmap** drops the 1.11.0 slot. **`state.md`** is refreshed: Version, Source, Tests, CI,
  Known gaps 1, 7 and 8, Next.

## [1.10.0] — 2026-10-22

Minor release, the roadmap's 1.10.0 slot, with the toolchain pin moving **6.7.12 → 6.7.16**.
**The public names are typed.** The 99 public constants are `const`. The 32 public predicates, and
their 12 `_compat` aliases, return `: bool` ([ADR 0012](docs/adr/0012-public-constants-are-const-and-predicates-return-bool.md)).

The roadmap listed 86 constants and 27 predicates by spelling. Typed by what they are, the set is
larger: 13 more constants and 5 more predicates, named below.

No value changed and no answer changed. A predicate returns what it returned before, and a bool
reads as 1 or 0 wherever an integer is used. The sources and `dist/` still build on cyrius ≥ 6.7.9,
checked there.

> ### ⚠ What to re-check
>
> - **A public constant is a `const`.** `&NAME` and `NAME = ...` stop compiling ("cannot take the
>   address of const", "cannot assign to const"). So does a program that declares one of these
>   names itself: as a `var` it is "already declared as a top-level const", and as a `const`, even
>   with the same value, it is "declared twice". None of the other 112 files in cyrius 6.7.16's
>   `lib/` declares or uses any of the 99 names.
> - **Two copies of the toml or the bigint module in one program are refused** (`const ... is
>   declared twice`). Until now they built, with duplicate-fn warnings and the last definition
>   winning. The routes to a second copy:
>   - a sublib beside the full bundle;
>   - two sublibs that share a module;
>   - a vendored 1.10.0 bundle beside cyrius's `lib/bayan.cyr` (the 1.9.0 fold), which
>     `lib/sigil.cyr`, `lib/ws.cyr`, `lib/ws_server.cyr` and `lib/yantra.cyr` include.
>
>   json, yaml, pdf and markdown were already refused this way, since 1.5.13 and 1.9.0. base64,
>   csv, u128 and cyml still build twice.
>   [Architecture note 002](docs/architecture/002-one-copy-of-each-module-per-program.md) has the
>   measured table. Include one bundle that carries every module you need.
> - **A predicate returns `: bool`, and no call site that worked before stops compiling.** Measured
>   on 6.7.16, each of these still compiles and reads 1 or 0:
>   - `== 1` and `== 0`
>   - adding the answer to an integer
>   - an `i64` local or parameter
>   - `store64`
>   - `return` from an `i64` function
>
>   The roadmap expected some integer use to break, and none does. What is new is that a
>   predicate's answer can now be returned from your own `: bool` function and passed to a `: bool`
>   parameter or local.
> - **Nothing else changes.** No function was added, removed or renamed, and no signature changed
>   but these return types.

### Changed — the public names are typed

- **99 public constants are `const`**, at their 1.9.0 values:
  - json: `JTAG_*` (7), `JV_SIZE`, `JSON_PAIR_SIZE`, `JSON_K_*` (5), `JS_EV_*` (12)
  - toml: `TOML_K_*` (8)
  - markdown: `MD_K_*` (21), `MD_EXT_*` (6), `MD_ALIGN_*` (4)
  - pdf: `PTAG_*` (10), `PDF_FONT_*` (15), `PDF_PAGE_*` (3), `PDF_MODE_*` (2), `PDF_WINANSI_*` (2),
    `PDF_MAGIC`
  - bigint: `U256_SIZE`

  The roadmap's list missed `PTAG_*` (which `bayan_pdf_obj_tag` returns), `U256_SIZE`,
  `JSON_PAIR_SIZE` and `JV_SIZE`. They are public in the same way.

  A `const` is a constant expression, which 6.7.16 refuses a `var` as ("a const context takes only
  constants"). So `switch (bayan_json_v_tag(v)) { case JTAG_INT: ... }`, a stack u256
  `var b[U256_SIZE];` and `#assert` now compile. The constants have no storage: the smoke binary
  is 659,472 → 654,856 bytes on 6.7.16.
- **32 public predicates return `: bool`.**
  - The 27 the roadmap named:
    - `bayan_json_v_is_null`, `_bool`, `_int`, `_float`, `_str`, `_arr`, `_obj`
    - `bayan_toml_pair_is_array`, `_inline`, `_string`, `bayan_toml_is_array`, `_inline`
    - `bayan_u128_is_zero`, `bayan_u256_is_zero`
    - `bayan_pdf_has_inflate`, `_deflate`, `bayan_pdf_font_is_monospace`
    - `bayan_pdf_obj_is_num`, `_name`, `_string`, `_array`, `_dict`, `_stream`, `_ref`, `_hex`
    - `bayan_pdf_is_encrypted`, `bayan_pdf_stream_is_image`
  - Five whose contract is the same yes or no under another spelling: `bayan_u128_eq`,
    `bayan_u256_eq`, `bayan_pdf_obj_eq` (its own comment calls it "the predicate"),
    `bayan_pdf_obj_name_eq` and `bayan_pdf_winansi_ok`.
  - The 12 `_compat` aliases of these are typed too, because ADR 0006 states anything said about
    one name of the pair about the other: `json_v_is_*` (7), `toml_is_array`, `u128_is_zero`,
    `u256_is_zero`, `u128_eq` and `u256_eq`.

  Their bodies return `true` and `false`. Four return a computed answer, and each value already
  was 0 or 1, so no answer moves:
  - `bayan_pdf_is_encrypted(0)` returns `_pdfp_last_enc != 0`.
  - `bayan_pdf_obj_name_eq` returns `memeq(..) != 0`.
  - `bayan_pdf_obj_eq` returns `_pdfo_eq_d(..) != 0`.
  - `bayan_pdf_stream_is_image` returns the private `_pdfz_filter_is_image`, now `: bool` too.
- **What stays `i64`, though its value is 0 or 1** (ADR 0012 has the rule):
  - `bayan_u256_cmp` is three-way.
  - `bayan_cyml_split` reports a status and writes its outputs.
  - `bayan_json_v_bool` reads a value.
  - markdown's `_fenced`, `_list_ordered`, `_list_tight` and `_row_header` are field accessors that
    share their family's contract, 0 for a node of another kind.
- The predicates' comments say true and false. pdf's tag block is no longer described as "plain
  vars". json's seven tag predicates are written over four lines each, as the other modules'
  predicates are: `: bool` with `true` and `false` took the one-line form past lint's 120 columns.
- **cyrius pin `6.7.12` → `6.7.16`.**
  - `lib/` was re-vendored by `cyrius lib sync --full --relock`, then `cyrius deps` and
    `deps --verify` (113 verified). 34 files changed. One of them is `lib/bayan.cyr`, cyrius's
    fold, which now carries bayan **1.9.0**, byte-identical to 1.9.0's `dist/bayan.cyr`.
  - `lib/` is byte-identical to the 6.7.16 **release**: installed through cyrius's `install.sh`
    into an isolated home, with the SHA-256 checksum and the Ed25519 signature verified. Its
    `cycc`, `cycc_aarch64`, `cycc_cx`, `cyrius`, `cyrfmt`, `cyrlint` and `cybs` are identical to
    the local install.
  - The 1.9.0 sources built and passed every x86_64, static and dist gate on 6.7.16 before any
    change, with `dist/` unchanged.
  - Of the stdlib changes in 6.7.13–6.7.16 to bayan's dependencies, bayan calls none:
    `result.cyr`'s `ok_via` and `err_via` are now typed `: Result`; `str.cyr`'s `Str_*`
    comparands are typed `: Str`; `io.cyr` adds `env_block`.
  - **The floor stays 6.7.9.** `const` dates from 6.7.2 and `bool` from 6.7.3. See Tests.
- **`dist/` regenerated** (`cyrius distlib --all`, all 11 bundles).
  - `bayan.cyr`, `bayan-json`, `-yaml`, `-toml`, `-markdown`, `-pdf`, `-u128` and `-bigint` carry
    the typed names.
  - `bayan-base64`, `-csv` and `-cyml` change only their version header.
  - No `.deps` sidecar changes, and a second regeneration changes nothing.
- **CI: a `static` step holds the rule for the next name.** It refuses a top-level upper-case `var`
  in `src/`, and an `_is_` / `_has_` / `_eq` function (or `bayan_pdf_winansi_ok`) that does not
  return `: bool`. On this tree it reports 99 consts and 44 bool functions. A planted public `var`,
  a planted `i64` canonical predicate and a planted `i64` alias each turned it red. The first draft
  matched any line starting with whitespace and `var`, so it flagged markdown's locals named `L`;
  it now matches column 0 only.

### Tests

- **`tests/bayan.tcyr`, three groups (1.10.0)**: 1,781 → 1,889 runtime asserts, plus 99
  compile-time ones.
  - **The constants.** There is one `#assert NAME == value` per constant, generated from the 99
    `var` declarations of 1.9.0's `src/`. An `#assert` is a const context, so each line fails the
    build if its name becomes a `var` again or its value moves.
  - **Constant contexts.** A `switch` over the seven `JTAG_*` sends each tag of a parsed array to
    its case. A `switch` over `MD_K_*` does the same for a document, its heading and its paragraph.
    A stack u256 is sized by `U256_SIZE`.
  - **The predicates.** Each of the 44 bool functions is passed to a `b: bool` parameter, which
    6.7.16 refuses an `i64` for, and asked once for true and once for false. These include the
    first rows for a **true** answer from `bayan_pdf_is_encrypted` and `bayan_pdf_stream_is_image`,
    whose return paths changed:
    - the writer's bytes with `/Encrypt` added to the trailer (which follows the cross-reference
      table, so no offset moves) are refused, and `is_encrypted(0)` is then true; a clean parse
      makes it false again;
    - a stream whose `/Filter` chain ends in `DCTDecode` or `JBIG2Decode` is an image, and one that
      ends in `FlateDecode` is not.
  - **Integer uses.** Five rows check that the answer added to an integer, held in an untyped
    `var`, stored with `store64`, and compared with `== 1` and `== 0` reads 1 or 0.
- **`tests/bayan_raw_include.tcyr`** (+1, and one `#assert`): against `dist/bayan.cyr` with nothing
  before it, a bundle predicate is accepted as a `bool` and `JTAG_INT` is a `const`. It is the
  consumer's view that distlib carries both.
- **Mutation pass, 12 mutants, each in a scratch copy of the tree; every one fails the build or the
  suite:**
  - an `i64` canonical predicate (`bayan_pdf_obj_eq`, `bayan_pdf_winansi_ok`) and an `i64` alias
    (`u128_eq`);
  - `JTAG_INT`, `U256_SIZE`, `MD_K_PARAGRAPH`, `MD_EXT_GFM` and `PDF_PAGE_LEGAL` back to `var`;
  - `PDF_PAGE_LEGAL` moved to 3;
  - `is_encrypted(0)` always false;
  - `stream_is_image` always false, and reading the first filter instead of the last.

  When the value rows were runtime `assert_eq`s, `MD_EXT_GFM` as a `var` passed the suite, and only
  the CI step caught it. That is why they are `#assert`s.
- **Every gate, on the 6.7.16 release.** Each of `ci.yml`'s six jobs ran in its own fresh tree on
  the release installed in an isolated home: all green. aarch64 ran under qemu: suite, fuzz, bench,
  both cost checks, and PDF bytes identical to x86_64's.
- **The floor, on the 6.7.9 release** (isolated home, its own `lib/`), in a scratch copy pinned to
  6.7.9:
  - the build and every test file are warning-free, and smoke exits 42;
  - `bayan_raw_include` builds `--no-deps`;
  - 6.7.9's `distlib --all --check` accepts the 6.7.16-generated bundles;
  - the consumer gate passes, and the aarch64 build is clean.
- `docs/examples/pdf_report.cyr` builds warning-free, and its output passes `pdfcheck.py`.

### Docs

- **[ADR 0012](docs/adr/0012-public-constants-are-const-and-predicates-return-bool.md).** It covers
  the rule (by contract, not spelling), what stays `i64` and why, and the alternatives: an `enum`
  per group, the roadmap's spelling only, one module per release.
- **[Architecture note 002](docs/architecture/002-one-copy-of-each-module-per-program.md).** A
  module that declares a `const` can be in a program once. It has the measured table, the three
  routes to a second copy, and why the modules that still build twice are the worse case, not the
  safer one.
- **The roadmap** drops the 1.10.0 slot. **`state.md`** is refreshed: Version, Toolchain, Source,
  Tests, CI, Known gap 4 (the 6.7.16 snapshot carries 1.9.0), Consumers and Next.

## [1.9.0] — 2026-10-15

Minor release, the roadmap's 1.9.0 slot. **`bayan_markdown_*`: CommonMark 0.31.2 to a node tree
and the tree to HTML**, with GitHub's tables, task lists, strikethrough and autolinks, and
`[[wiki links]]`, each behind a flag. It passes every example of the CommonMark spec but the 72
that pass raw HTML through, which bayan writes as text (ADR 0011), and the in-scope examples of the
GFM spec and of cmark's and cmark-gfm's own test files: 665 vectors, regenerated in CI from the
upstream files. A differential against commonmark.js 0.31.2, the spec's reference implementation,
agreed on all 94,584 documents it could compare. Public API: 27 functions and the `MD_*` names,
all new; nothing else changed. The pin stays 6.7.12, and the floor 6.7.9 (checked there).

> ### ⚠ What to re-check
>
> - **bayan now needs the stdlib's `unicode` modules.** Markdown's emphasis rules need the general
>   category of the characters around a delimiter, and its link labels match under full case
>   folding. A consumer with a hand-written include list adds `lib/unicode/categories.cyr` and
>   `lib/unicode/casefold.cyr` before `lib/bayan.cyr`. Without them, a program that never calls
>   markdown still builds, with three undefined-function warnings; one that calls it is refused.
>   The `# Requires` block of `dist/bayan.cyr` and `dist/bayan-markdown.cyr` and their `.deps`
>   sidecars carry the `unicode` leaf. distlib takes it as the whole family, so those two bundles
>   now include all seven files of `lib/unicode/` (about 350 KB of source, `normalize` and its
>   table among them, though markdown uses neither). A consumer that wants no Unicode tables uses a
>   sublib other than `bayan-markdown`.
> - **Nothing else changes.** No existing function, name or answer moved. The other nine sublibs
>   differ only in their version header.

### Added — `bayan_markdown_*`

- **The parser.** `bayan_markdown_parse(src)` reads a `Str` as CommonMark 0.31.2;
  `bayan_markdown_parse_ext(src, flags)` adds extensions; `bayan_markdown_parse_a(a, src, flags)`
  and `bayan_markdown_parse_buf_a(a, data, len, flags)` take an allocator, and a byte span.
  Each returns the document node, or 0 with the reason in `bayan_markdown_last_error()`.
- **The tree** (ADR 0010): a 128-byte node with kind, parent, first and last child and both
  siblings. Block kinds `MD_K_DOCUMENT`, `BLOCKQUOTE`, `LIST`, `ITEM`, `PARAGRAPH`, `HEADING`,
  `THEMATIC_BREAK`, `CODE_BLOCK`, `TABLE`, `TABLE_ROW`, `TABLE_CELL`; inline kinds `MD_K_TEXT`,
  `SOFTBREAK`, `LINEBREAK`, `CODE`, `EMPH`, `STRONG`, `STRIKETHROUGH`, `LINK`, `IMAGE`, `WIKILINK`.
  Accessors: `bayan_markdown_kind`, `_parent`, `_first_child`, `_last_child`, `_next`, `_prev`,
  `_child_count`, `_child(n, i)`, and one per field: `_text`, `_level`, `_url`, `_title`, `_info`,
  `_fenced`, `_list_ordered`, `_list_start`, `_list_tight`, `_task`, `_align`, `_row_header`. Each
  returns 0 for a node of another kind and for 0 (`_task` returns -1), never another kind's field.
- **The renderer.** `bayan_markdown_to_html(tree)` and `_to_html_a(a, tree)` write HTML as cmark
  does, byte for byte on every vector.
- **Extensions**, by flag: `MD_EXT_TABLES`, `MD_EXT_TASKLISTS`, `MD_EXT_STRIKETHROUGH`,
  `MD_EXT_AUTOLINKS` (`MD_EXT_GFM` is all four), and `MD_EXT_WIKILINKS`: `[[target]]` and
  `[[target|label]]`, a `WIKILINK` node whose url is the target, rendered
  `<a href="target" class="wikilink">label</a>`. Table alignment is `MD_ALIGN_NONE`, `LEFT`,
  `CENTER`, `RIGHT`. The GFM extensions follow the code of cmark-gfm, the reference implementation,
  for its row scanner, delimiter-row grammar, autolink matching and strikethrough pairing (flanking
  for `~` uses CommonMark 0.31.2's punctuation, as `*` and `_` do). Task items follow the GFM spec
  instead, which defines them on the item's first paragraph, so `> - [ ] x` and `- - [ ] x` are
  tasks here. cmark-gfm's `tasklist.c` scans the line from its first byte, which misses both.
- **Entities**: all 2,125 HTML5 named references that end in `;`, in the new generated
  `src/markdown_entities.cyr` (from Python's `html.entities.html5`, the WHATWG list CommonMark names;
  `scripts/gen-md-entities.py`). The lookup is a binary search.
- **`[lib.markdown]`, the `bayan-markdown` sublib**: `markdown_entities.cyr` then `markdown.cyr`, in
  `[lib]` too, before `_compat.cyr`. Neither depends on another bayan module.

### Design — what each choice answers

- **Raw HTML is text** (ADR 0011). HTML blocks and inline tags are not recognised; `<div>` is
  written `&lt;div&gt;`. A renderer that passes HTML through, as the spec does, turns every document
  it did not write into a way to put script into a page. **A dangerous URL is dropped** from the
  HTML: a link or image to `javascript:`, `vbscript:`, `file:` or `data:` (but `data:image/png`,
  `gif`, `jpeg`, `webp`) gets an empty `href` or `src`, in any case, checked after decoding, as
  cmark's default does. The tree keeps the URL.
- **Nesting is capped at 128 levels**, blocks and inlines together, and a deeper document is refused
  with "nesting too deep", as json and yaml cap theirs. The block cap acts while containers open, so
  200,000 `>` are refused at once. Inline nesting is checked before any pass that recurses into it.
- **Per-call state, and every allocation through the allocator given**: a refused one makes the
  parse or the render return 0, never a partial tree or HTML.
- **The pathological inputs are bounded.** Running cmark's suite (`test/pathological_tests.py`)
  on the first draft found three slow paths, each fixed:
  - backtick runs of every length 1..2499 ran past its 5 s limit: a memo now keeps the last run of
    each length up to 1,000 (a longer run opens no code span, cmark's bound);
  - emphasis kept its openers' lower bound as a pointer to a delimiter that could be removed, and
    cmark's issue #389 took 1.6 s: the bound is a position, as cmark keeps it, and it takes 0.16 s;
  - a named entity was looked up by scanning the 2,125-entry table, so 200,000 references took
    3.6 s: a binary search, 0.5 s.
  Reading the draft against the suite's list had already fixed three more before it ran:
  - link openers were deactivated by walking the bracket stack after each link, which `![[]()`
    repeated makes quadratic, since images are never deactivated and so never stop the walk. An
    epoch replaces it: an opener is inactive once a link was made after it was pushed. cmark's
    `no_link_openers` flag was not copied: in its code any new `[` clears the flag, so after
    `[a [b](c) [d] e]` the outer opener would be live again and its link would hold another;
  - definitions were found by a linear scan, now a binary search over a stable sort (the first
    definition of a label wins);
  - adjacent text was merged a pair at a time, quadratic in a run of separately allocated nodes
    (a paragraph of entity references is one); a run is now merged in one copy.
  A table's short rows are filled out with empty cells only up to cmark-gfm's bound of 524,288.

### Tests

- **`tests/vectors.tcyr`: 665 markdown vectors, 0 wrong.** All from the upstream suites, in
  `tests/fixtures/markdown/upstream/` verbatim with their licences (CC BY-SA 4.0 for the two specs,
  BSD 2-Clause for cmark's and cmark-gfm's tests; its `README.md`), each pinned by SHA-256 in the
  new `scripts/gen-markdown-vectors.py`:
  - CommonMark 0.31.2: 580 of 652. The 72 left out pass raw HTML through: 57 of the 64 in the HTML
    sections (the other 7 check that a malformed tag stays text, which bayan does, and run) and 15
    elsewhere.
  - GFM 0.29: its 23 extension examples but the tag filter (raw HTML). Its CommonMark sections are
    0.29's, checked at 0.31.2 instead.
  - cmark-gfm's extension tests: 25 of 30 (2 raw HTML, 3 footnotes, which bayan does not have). One
    is a crash test with no expected output, run as one. Its task items are written
    `<input type="checkbox" disabled="" />`, the GFM spec's (and bayan's) `<input disabled=""
    type="checkbox">` with its attributes in another order; that is the generator's one transform.
  - cmark's regression tests: 22 of 32; cmark-gfm's: 15 of 26 (the rest raw HTML or footnotes).
  The generator refuses an exclusion whose example does not bear out its reason (a source tag in the
  expected HTML, or a `[^`), and CI regenerates the files and requires no change. The 597
  CommonMark rows with no `[[` are parsed again with `MD_EXT_WIKILINKS`, which must change nothing.
  These suites found, in the first draft: a table row that opens another block must end the table;
  autolinks must be matched on merged text; cmark-gfm's `mailto:` and `xmpp:` links, links in
  quotes, hosts without a dot and its trailing-character rules; a leading byte order mark; an info
  string already starting `language-` getting it twice; and an empty `<p></p>` where a paragraph was
  only definitions.
- **A differential against commonmark.js 0.31.2** (the spec's reference implementation; it matches
  all 652 spec examples), in scratch: 100,000 documents generated from tokens that start every
  block and inline construct, across tabs, CRLF and non-ASCII. 5,416 were skipped, those
  commonmark.js reads as raw HTML or that pass bayan's cap, and the other 94,584 agree byte for byte.
  It found two defects in bayan:
  - an indented code block's dropped trailing blank lines hid a list's looseness
    (`-     code`, a blank line, `- b` was tight);
  - a paragraph that was only definitions left the tree before the list was judged (`- a`, a blank
    line, `  [r]: /u` was tight; a definition is a block, and the spec makes such a list loose). It
    stays in the tree, marked, until block parsing ends.
  The fuzzer normalises four ways commonmark.js parts from cmark and the spec, where bayan
  follows those two: it trims with JavaScript's `trim()`, which also strips NBSP and U+3000 at block
  edges and in an info string; it takes only spaces after a definition's colon or destination,
  where the spec allows tabs; it leaves `'` in an `href` unescaped; and it leaves an empty `<p></p>`
  when a setext underline follows a paragraph of only definitions, a case cmark's regression suite
  pins the other way.
- **`tests/bayan.tcyr` 1,656 → 1,781** (+125): the tree and every accessor, on the right kind, the
  wrong one and 0; pinned HTML for references, escaping, percent-encoding, the `language-` class,
  the byte order mark, NUL, CR and CR LF, hard breaks, near-miss entity names, five definitions of
  one label, nested links, the two looseness defects; raw HTML as text and each dangerous URL; each
  extension flag alone and together, task-item edges, a table ended by a block, a lone pipe, the
  header that is not retried; wiki links; both sides of the cap in blocks and in emphasis; and a
  refusal sweep: each of the parse's 222 allocations and the render's 5, refused alone, returns 0
  with "out of memory", and the `_a` forms make the same requests through the allocator they get.
- **New `tests/markdown.fcyr`**: 25,028 parses a run, of generated documents (each also edited at
  random), every prefix of 16 edge documents, nesting from 120 to 135 levels, and the pathological
  inputs at full size, plus the filled-cell bound at 513 body rows. Every document is parsed from
  the end of a page whose next page is PROT_NONE. The HTML must be well formed: since bayan writes
  every `<` of its input as `&lt;`, each `<` in the output opens one of the renderer's tags, and they
  must nest. A second parse from another address must write the same bytes. One document in eight is
  parsed again with one allocation refused at random, and must return 0. 4 s on x86_64, 44 s on
  aarch64 under qemu.
- **New `tests/markdown_scaling.cyr`**, run by its own CI step on x86_64 and aarch64, as
  `tests/mulmod_speed.cyr` is: six of the pathological families timed at two sizes (the fastest of
  five runs each), failing when the time ratio over the input ratio passes 3. All six measure 0.5 to
  1.1 on both targets.
- **Mutation-checked: 29 mutants of `src/markdown.cyr`, 28 caught.** The first pass left four
  uncaught: near-miss entity names, the first definition of a label winning (with two duplicates the
  search found the first by luck), and the emphasis bound and the backtick memo. Every answer stays
  right on a quadratic path, so only cost shows those two, which is why the scaling check exists:
  it puts them at 5.8 to 7.9 against the limit of 3. A third complexity mutant, a linear definition
  lookup, fails it too. The fuzz harness missed a one-byte over-read in the table cell scanner until
  two edge documents ending a row with a backslash were added. The survivor is equivalent: the
  label scanner's stop at 999 bytes repeats a check made when the `]` is found.
- **`scripts/consumer-check.sh` builds a consumer from a family leaf**: `unicode` names a directory,
  not a file, so its files go in, in the order distlib's `# Requires` block lists them. Until now
  the check had no family leaf to meet, and it failed on `lib/unicode.cyr`.
- **`tests/bayan_raw_include.tcyr`** parses and renders through `dist/bayan.cyr` alone (+1).
  **`tests/bayan.bcyr`** gains three rows: a 5.4 KB note with GFM parses in 556–657 µs and renders
  in 124–141 µs on x86_64, 4.6 ms and 1.0 ms on aarch64 under qemu.
- **The floor stays 6.7.9.** On the signature-verified 6.7.9 release, in an isolated home and a
  scratch copy with its `lib/`: the build and every test, fuzz and scaling program are
  warning-free and pass, the smoke entry exits 42, and 6.7.9's `distlib --all --check` accepts the
  bundles 6.7.12 generated. 6.7.9's `lib/unicode` has every function markdown calls.
- Gates, all green on the 6.7.12 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz (4 harnesses), bench, coverage 533/533, both cost gates. aarch64 under qemu: build,
  smoke, test, the deprecated lookups, fuzz, bench, both cost gates, the PDF writer byte-identical
  across targets. Also: format, lint (0/0 across `src/`), `vet`, the arch-arm check, the
  vendored-fold guard, every vector and the entity table regenerated with no change,
  `distlib --all --check`, regeneration with no change, `scripts/consumer-check.sh` (11 bundles)
  and the raw-include build. Then the CI mirror: every `ci.yml` job, each in its own fresh copy of the
  tree, on the 6.7.12 release, all six green, the three new steps included.
- **`dist/` regenerated** (`cyrius distlib --all`). `bayan.cyr` gains the two modules (17,664 →
  21,076 lines) and `bayan.deps` the `unicode` leaf; `bayan-markdown.cyr` (3,423 lines) and its
  `.deps` (6 leaves) are new; the other nine change only their version header.

### Docs

- ADR [0010](docs/adr/0010-markdown-parses-into-a-tree-of-its-own.md): markdown parses into a tree
  of its own, not the json value tree. ADR [0011](docs/adr/0011-markdown-raw-html-is-text.md): raw
  HTML is text, and dangerous URLs are dropped.
- [`docs/development/roadmap.md`](docs/development/roadmap.md): the 1.9.0 section is gone; 1.10.0's
  `const` migration now lists the `MD_*` names. `state.md` refreshed.

## [1.8.0] — 2026-10-15

Minor release, the roadmap's 1.8.0 slot. **yaml decodes its quoted scalars in the parser**, the
choice ADR 0009 made for TOML at 1.5.3: double quotes take YAML 1.2's escapes, single quotes take
`''`, and every scan that tracks quotes agrees on where a quoted region ends. Checked against
PyYAML. **cyml reads CRLF lines:** a CR LF ends a marker or `---` line, so a file saved with
Windows line endings has its entries. Public API: nothing added or removed. The pin stays 6.7.12,
and the floor 6.7.9 (checked there).

> ### ⚠ What to re-check
>
> - **yaml.** A quoted value, key or flow element comes back decoded: `"a\nb"` is `a`, newline,
>   `b`, and `"C:\\tmp"` has one backslash. **Remove any code that decoded bayan's output itself, or
>   it will decode twice.** Documents that were refused now parse: a `\"` inside double quotes, and
>   `''` inside single quotes. Documents that parsed are now refused: an escape YAML does not define
>   (`\q`), a short or non-hex `\x` / `\u` / `\U`, a code point past U+10FFFF or a surrogate, and a
>   key that opens a quote but is not one quoted scalar (`"a"b": 1`). Duplicate keys are compared
>   decoded, so `"\x61": 1` and `a: 2` in one mapping is now a duplicate, and refused.
> - **cyml.** A document with CRLF line endings parses into its entries and bodies. To 1.7.1 it gave
>   no entries and one block of header text. A lone CR mid-line is still text.

### Changed — yaml quoted scalars are decoded

- **Double-quoted scalars take YAML 1.2's escapes:** `\0 \a \b \t \n \v \f \r \e`,
  backslash-space, `\"`, `\/`, `\\`, `\N` (U+0085), `\_` (U+00A0), `\L` (U+2028), `\P` (U+2029), a
  backslash before a TAB, and `\xXX`, `\uXXXX` and `\UXXXXXXXX` as code points written in UTF-8.
  Bodies were verbatim until now, "the toml convention" in the module's words, which TOML itself
  dropped at 1.5.3 (ADR 0009). That made `"C:\\tmp"` two backslashes and `"a\nb"` a backslash and an
  `n`. Decoding happens in `_yp_unquote`, in the parser: the json tree YAML parses into records no
  quote style (ADR 0008), so nothing later could tell which rule applies.
- **Single-quoted scalars take `''` for a quote.** A backslash there is a backslash, as before.
- **Values, keys and flow elements all decode.** A quoted key kept its escapes (`"a\"b"` was
  `a\"b`), and a single-quoted key its doubled quotes (`'it''s'` was `it''s`).
- **Every quote scan agrees where a quoted region ends** (`_yp_qend`: in double quotes `\` escapes
  the next byte, and in single quotes `''` is a quote). The comment stripper, the key's colon
  finder, scalars and flow elements each took the first quote character as the close. So
  `k: "x\" # y"` came back as `x\`, its ` # y"` stripped as a comment, and `"say \"hi\""`,
  `'it''s'` and `["a\"b"]` were refused as malformed.
- **Refused loudly, with the offset of the escape:** an escape YAML does not define (`\q`, which
  was kept), a `\x` / `\u` / `\U` with too few or non-hex digits, a code point past U+10FFFF, and a
  surrogate (U+D800–U+DFFF). PyYAML refuses all of those but the surrogate, which it reads into a
  Python string. A surrogate is not a character and has no UTF-8 form, so bayan has nothing faithful
  to return. **A key that opens a quote must be one quoted scalar**: `"a"b": 1` was the key `a"b`,
  and is refused now, as the same shape is refused for a value.
- **Duplicate keys are compared after decoding**, so a mapping with `"\x61"` and `a` is refused for
  its duplicate.
- A quoted scalar with nothing to decode still shares the source buffer. One that decodes is a new
  allocation (at most 1.5 times the body: `\L` and `\P` are two bytes that become three), and a
  refused allocation is a parse error, "out of memory in quoted scalar".

### Changed — cyml: CR LF ends a marker or `---` line (Known gap 17)

- A CR ended no line until now, so `[[entries]]\r\n` and `---\r\n` were text. A `.cyml` saved with
  CRLF line endings parsed to no entries and one block of header text, and nothing reported it. Now
  a marker or delimiter line ends at `\n`, at `\r\n`, at the end of the input or region, or at a
  `\r` just before that end. A CR anywhere else is text, so `[[entries]]\rfoo` is not a marker.
  TOML allows CRLF, so the headers themselves were always fine.
- The new private `_cyml_eol` says where a line ends. `_cyml_marker_at`, `_cyml_delim_at` and
  `_cyml_body_at` use it, and an entry's header now starts past its marker's LF or CR LF. Marker
  position 0 means either a marker at byte 0 or a newline at byte 0 before one. The new
  `_cyml_marker_text` tells the two apart by the byte there, which the old fixed offsets never
  needed to do.

### Added

- **`scripts/gen-yaml-vectors.py` and `tests/fixtures/yaml/strings.vec`**: 3,429 vectors from
  PyYAML. 1,991 are values, 676 keys and 681 flow elements, each a quoted scalar built from plain
  text, `#`, `: ` and the full escape set, some with a trailing comment. 81 are documents PyYAML
  refuses, which bayan must refuse too. Each is checked with the oracle before it is written. The
  surrogate is left out on purpose (see above). CI's `oracles` job regenerates the vectors and
  requires no change. PyYAML is not in Python's stdlib, so the step installs the distribution's
  `python3-yaml` when the import fails, as the aarch64 job installs `qemu-user`, and fails if it
  still cannot import it.

### Tests

- **`tests/vectors.tcyr`: the YAML vectors, 0 wrong.** On 1.7.1's module 1,896 of the 3,429 were
  wrong.
- **`tests/bayan.tcyr` 1,611 → 1,656.** yaml: +25, one row per decoded form, for the comment and
  colon scans, keys and flow elements, the duplicate compared decoded, each refusal including the
  surrogate the oracle cannot carry, and the zero-copy case. cyml: +20, a whole-CRLF document,
  adjacent CRLF markers, a lone CR as text, a `---\r` at the end, and split. The 1.6.0 and 1.6.1
  pins for a CRLF marker and a CRLF `---` move to their new answers, each label naming the old one.
  The delimiter scan's reference states the CR rule.
- **yaml mutants: twelve,** each failing at least one suite: each side of `_yp_qend`, the comment
  scan and the colon scan without the rule, verbatim bodies, an unknown escape kept, a surrogate
  kept, `\u` read as two digits, raw keys, raw flow elements, `''` kept, and no range check. The
  oracle misses the surrogate mutant, and the pinned rows catch it. The pinned rows missed the
  colon mutant until a row was added for it; the oracle caught it with 4 wrong.
- **cyml against the line reference, extended to CR:** the 1.7.0 scratch model with the CR rule,
  over 30,000 random documents built from LF and CRLF markers and delimiters, lone CRs and `---\r`,
  each at every prefix. All 2,265,694 prefixes agree on x86_64 and on aarch64 under qemu. 1.7.1's
  module differs on 22,193 of the documents. Five mutants: treating CR as text, refusing a CR before
  the end, and misreading position 0 each fail. Starting the body at `q + 4`, or the header at
  `s + 12`, after a CRLF line changes no output, because that lands on the LF and the trim removes
  it. The source says so, as the divmod block does for its redundant tests.
- **The floor stays 6.7.9.** In a scratch copy pinned to 6.7.9 with its `lib/`: the build and all 6
  test files are warning-free (the YAML and CSV vectors 0 wrong there too), the smoke entry exits
  42, and 6.7.9's `distlib --all --check` accepts the bundles 6.7.12 generated.
- Gates, all green on the 6.7.12 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz, bench, coverage 506/506, the cost gate. aarch64 under qemu: build, smoke, test,
  deprecated lookups, fuzz, bench, the cost gate, the PDF writer byte-identical across targets.
  Also: format, lint (0/0 across `src/`), `vet`, the arch-arm check, the vendored-fold guard,
  `distlib --all --check`, regeneration with no change, `scripts/consumer-check.sh` and the
  raw-include build. Then the CI mirror: every `ci.yml` job, each in its own fresh copy of the tree,
  on the 6.7.12 release, all six green, the new YAML regeneration step included.
- **`dist/` regenerated** (`cyrius distlib --all`). `bayan.cyr`, `bayan-yaml` and `bayan-cyml`
  carry the changes; the other seven change only their version header. The `.deps` sidecars are
  unchanged.

### Docs

- ADRs [0008](docs/adr/0008-yaml-parses-into-the-json-value-tree.md) and
  [0009](docs/adr/0009-toml-strings-are-decoded-in-the-parser.md) record that 1.8.0 applied 0009's
  argument to yaml. [`docs/development/roadmap.md`](docs/development/roadmap.md): the 1.8.0 section
  is gone; 1.9.0 (`bayan_markdown_*`) is next. `state.md` refreshed: Known gap 17 is closed.

## [1.7.1] — 2026-10-15

Patch release, the roadmap's 1.7.1 slot. **Each csv function returns 0 when an allocation is
refused** (Known gap 16, found while 1.7.0 rewrote the parser). Until now each answered a refusal
in its own wrong way, and none of them with 0. Public API: nothing added or removed, and no function
returns anything different for any input it is not refused memory on. ⚠ A caller that passes
`bayan_csv_parse_line`'s result straight to `vec_len` should check it for 0 first, as it would
`bayan_toml_parse`'s. The pin stays 6.7.12, and the floor 6.7.9 (checked there).

### Fixed

- **`bayan_csv_parse_line` returns 0, never a short row.** A refused field copy or scratch buffer
  returned the fields read so far, a row a caller cannot tell from a real one. A refused vec
  header was pushed to (a fault), and a refused growth past 16 fields ended the process, as the
  default `vec_push` does.
- **`bayan_csv_escape` returns 0 instead of storing through address 0.** Its output buffer, needed
  only for a field that must be quoted, was used unchecked. A field that needs no quotes is still
  returned as it is, with no allocation.
- **`bayan_csv_write_line` returns 0** for a refused escape (it handed the 0 to `strlen`) and a
  refused vec or vec growth (a fault or an exit). The record buffer and 1.7.0's lone-empty-field
  buffer were the only allocations it checked.
- Every allocation in the module goes through `default_alloc()`: the same global bump allocation
  as the bare `alloc` it replaces, routed through the slot a test can swap. Pushes use
  `vec_push_a`, which reports a refused growth instead of ending the process. The module header
  states the contract.

### Tests

- **`tests/bayan.tcyr` +10 (1,601 → 1,611): "csv: a refused allocation returns 0, never a short
  row or a fault (1.7.1)".** The lever used for TOML at 1.5.13 and cyml at 1.6.1: the default
  allocator's alloc slot is swapped for one that refuses only the k-th request, for every k of one
  call. A line of 18 fields, six of them quoted, grows the vec past its 16 slots. Its parse makes 22
  requests (the vec's two, the scratch, 18 field copies, one growth), and writing the matching row
  makes 10 (the vec's two, six escapes, one growth, the record). An escape that quotes makes one, an
  escape that does not makes none, and a row of one empty field makes one. Every refused call
  returns 0. The counts are pinned, so an allocation that left the default allocator would be seen.
- **Thirteen mutants each fail it:** each of the new checks removed alone, the two pushes back on
  `vec_push`, and each allocation back on bare `alloc`. Four segfault, two end the process with
  `vec: alloc failed`, and seven fail a named row.
- The CSV vectors (4,835 from Python's `csv`) are unchanged and 0 wrong.
- **The floor stays 6.7.9.** In a scratch copy pinned to 6.7.9 with its `lib/`: the build and all 6
  test files are warning-free (the sweep included), the smoke entry exits 42, and 6.7.9's
  `distlib --all --check` accepts the bundles 6.7.12 generated.
- Gates, all green on the 6.7.12 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz, bench, coverage 506/506, the cost gate. aarch64 under qemu: build, smoke, test,
  deprecated lookups, fuzz, bench, the cost gate, the PDF writer byte-identical across targets.
  Also: format, lint (0/0 across `src/`), `vet`, the arch-arm check, the vendored-fold guard,
  `distlib --all --check`, regeneration with no change, `scripts/consumer-check.sh` and the
  raw-include build. Then the CI mirror: every `ci.yml` job, each in its own fresh copy of the tree,
  on the 6.7.12 release, all six green.
- **`dist/` regenerated** (`cyrius distlib --all`). `bayan.cyr` and `bayan-csv` carry the checks
  (+13 lines); the other eight change only their version header. The `.deps` sidecars are
  unchanged.

### Docs

- [`docs/development/roadmap.md`](docs/development/roadmap.md): the 1.7.1 section is gone; 1.8.0 is
  next. `state.md` refreshed: Known gap 16 is closed.

## [1.7.0] — 2026-10-15

Minor release, the roadmap's 1.7.0 slot: **four outputs that were silently wrong**, each fixed
against something other than bayan. csv now reads and writes what Python's `csv` module does.
`bayan_json_build` writes valid JSON with the values it parsed. cyml's markers and `---`
delimiters are whole lines wherever they fall. The pin stays 6.7.12, and the floor 6.7.9 (checked
there).

> ### ⚠ What to re-check, by module
>
> - **csv.** `bayan_csv_parse_line` returns one more field for a line ending in a comma, no longer
>   keeps the line's own CR, LF or CRLF in its last field, and keeps the text after a closing quote
>   in that field (`"a"b,c` is `ab`, `c`, not three fields). `bayan_csv_write_line` ends records in
>   CRLF, not LF, and writes a row of one empty field as `""`. `bayan_csv_escape` quotes a field
>   holding a CR. Drop any code that compensated for the old answers.
> - **json.** `bayan_json_build` writes a parsed number, `true`, `false`, `null`, object or array
>   unquoted, as it was read, and escapes a hand-built pair's key and value. A pair is **24 bytes**
>   (`JSON_PAIR_SIZE`), up from 16: code that allocated a pair itself, or assumed its size, must
>   change. Pairs read through the accessors are unaffected.
> - **cyml.** A document parses as before unless it has one of these shapes, each of which now
>   parses differently: two adjacent `[[entries]]` lines (now two entries, the first empty); a
>   `---` line directly after a marker or directly before the next one, or right after a blank
>   first line (now a delimiter); a marker or a `---` as the last line with no newline after it
>   (now a marker or a delimiter). Check documents with those shapes.

### Changed — csv reads and writes RFC 4180 as Python's `csv` does (Known gap 10)

- **A trailing empty field is a field.** `a,` parsed to one field and `,,` to two (the RFC: two and
  three), so a row ending in an empty field lost a column on every round trip. Documented since
  1.5.3.
- **Records end in CRLF** (RFC 4180 s2.1), from `bayan_csv_write_line`; they ended in a lone LF. And
  **`bayan_csv_parse_line` no longer keeps a line's terminator as data**: `a,b\r\n`, `a,b\n` and
  `a,b\r` all give `b`. It returned `b\n` for the writer's own output, so bayan's round trip was
  broken on the last field.
- **A field holding CR is quoted** by `bayan_csv_escape`. It was written bare, and came back from
  any reader as a line break.
- **The text after a closing quote stays in its field** (found here, not on the roadmap):
  `"a"b,c` parsed to `a`, `b`, `c`, where Python's reader gives `ab`, `c`, so every later column
  shifted by one. The parser is now RFC 4180's grammar as Python runs it: four states, where a
  quote just after a closing quote is an escaped one, and anything else but a comma or the
  terminator continues the field.
- **A row of one empty field is written `""`**, as Python writes it. Written bare it was an empty
  line, which reads back as a record of no fields.
- **One record per call**, stated in the module header. A CR or LF outside quotes ends the record
  only as the line's terminator: its last byte, or CRLF as its last two. Anywhere else it is kept
  as data, where Python would start a second record. Inside quotes CR and LF are data, so a quoted
  record spanning lines parses whole when it is passed whole.

### Changed — `bayan_json_build` writes valid JSON with the same values (Known gap 14)

- **Each pair is written by its kind.** The build quoted every value and escaped nothing: a number
  came back as a string, a nested value as a quoted span (`{"o": "{"a":1}"}`, not JSON), and a `"`
  or `\` in a hand-built value broke the document. Now a pair from `bayan_json_parse` is written as
  it was read: a string's raw body between quotes, and a number, `true`, `false`, `null`, object or
  array as its raw bytes. So `bayan_json_build(bayan_json_parse(doc))` has doc's members and
  values. A hand-built pair is text: its key and value are escaped (`_jb_append_string`, the tree
  serializer's), and the value is written as a string, as it always was. A raw byte below 0x20 in a
  parsed string, which JSON forbids but the flat parser takes, is written as `\u00XX`. Other bytes
  a non-JSON document can carry through the lenient parser (an unvalidated bare value such as
  `abc`, an escape JSON does not define) come out as they went in.
- **The flat pair records its kind and is 24 bytes** (`{ key, value, kind }`; `JSON_PAIR_SIZE` 16
  → 24). `bayan_json_parse_a` records the form it read, and `bayan_json_pair_new(_a)` keeps its
  signature and makes a `JSON_K_TEXT` pair. This is how TOML's pairs have worked since 1.5.4, for
  the same reason: only the parser knows what form a value took.

### Changed — cyml markers and delimiters are whole lines wherever they fall (Known gap 15)

- **Two adjacent `[[entries]]` lines are two entries, the first one empty.** From 1.5.1 to 1.6.2
  they were one entry whose header began with the second marker: the scan resumed past the first
  marker's newline, and a marker can only follow one. It resumes on that newline now (11 past
  offset 0, else 12), and both passes take the same step. An empty entry's header start is held at
  its end, so its header is empty and it has no body. This is TOML's reading of two `[[t]]` lines,
  and bayan's TOML parser has kept an empty table since 1.5.4. 1.6.0 pinned the old answer so that
  changing it would be a decision; the roadmap asked for one.
- **A `---` line is a delimiter after a blank first line** (`\n---\nbody`: an empty header and the
  body), and **straight after its entry's marker** (`[[entries]]\n---\nA`: the body `A`). To 1.6.2
  byte 0 was tested for `---\n` only, and an entry's search began past the marker's newline, so both
  were header text. 1.5.1 fixed the first shape in the marker scan.
- **The same rule at the region's far end** (found here; the roadmap named the near end). A `---`
  line just before the next marker, whose newline it shares, is that entry's delimiter, with an
  empty body; it was header text, and the entry had no body. A `---` that is the last line, with no
  newline after it, is a delimiter too. And **a marker that is the last line** (`x\n[[entries]]`)
  is a marker, opening an empty entry; it was text. A file's last line need not end in a newline.
- `_cyml_next_delim` now returns the start of the `---` line rather than the newline before it, and
  the new private `_cyml_body_at` says where the body begins: past the line's newline, or at the
  region's end. `_cyml_marker_at` and `_cyml_delim_at` accept the end of the input or region where
  they needed `\n`. The rule is stated once, in the module header.
- **Not changed:** a CR does not end a line, so `[[entries]]\r\n` and `---\r\n` are still text
  (Known gap 17, roadmap 1.8.0).

### Added

- `JSON_K_TEXT`, `JSON_K_STRING`, `JSON_K_BARE`, `JSON_K_OBJECT`, `JSON_K_ARRAY`;
  `bayan_json_pair_kind(p)`; `bayan_json_pair_new_kind(key, value, kind)` and its `_a` form. Any
  kind but `JSON_K_TEXT` says that the key and value are raw JSON source bytes, which the build
  writes unchanged. The constants are `var`s like `JTAG_*`, and join roadmap 1.10.0's `const` list.
  No `_compat` aliases: the alias set is closed (ADR 0006).
- **`scripts/gen-csv-vectors.py` and `tests/fixtures/csv/csv.vec`**: 4,835 vectors from Python's
  `csv` module (3,993 parse, 619 write, 223 escape), each verified against the module before it is
  written. Lines Python would split at a mid-line break are left out (see "one record per call").
  CI's `oracles` job regenerates them and requires no change, as for the TOML and numeric vectors.

### Tests

- **`tests/vectors.tcyr`: the CSV vectors, 0 wrong.** On 1.6.2's module 3,747 of the 4,835
  disagreed with Python.
- **`tests/bayan.tcyr` 1,553 → 1,601.** csv: +22, one row per fixed answer, plus the mid-line
  breaks the oracle cannot see. Two 1.5.1 rows that pinned the LF terminator now pin CRLF. json:
  +13, each kind's output, the raw control byte, hand-built escaping, `pair_new_kind` and the pair
  size. cyml: +13, as the 1.6.0 and 1.6.1 groups' pins for adjacent markers, a marker at the end,
  and the four delimiter edges move to their 1.7.0 answers, each label naming the old one. The two scan
  references now state the 1.7.0 rule (the marker reference loses its own `pos + 13` bound; the
  delimiter reference is rewritten for whole lines and the line-start position).
- **csv mutants:** nine, each failing at least one suite. The oracle misses one, any CR or LF
  ending the record, because it has no mid-line breaks; the pinned rows catch it. The pinned rows
  miss one, a quote opening a field mid-field; the oracle catches it with 673 wrong.
- **JSON round trip against Python's `json`:** 22,000 random documents: 20,000 objects with
  escapes, non-ASCII text, nesting, numbers, booleans and null, at three separator styles, and
  2,000 with raw control bytes in strings. `bayan_json_build(bayan_json_parse(doc))` loads in Python
  and equals `json.loads(doc)` (non-strict for the control bytes) for every one. 1.6.2's output was
  not JSON for 12,624 and had different values for 5,368 more. Six mutants fail the pinned rows;
  the three that touch parsed documents fail the round trip too.
- **cyml against a line-by-line reference:** a scratch Python model written from the rule (markers
  and `---` lines found as lines, then trimmed), not from `src/cyml.cyr`, against the parser and
  `bayan_cyml_split` at every prefix of 30,000 random token documents: 1,960,742 prefixes, each
  compared through a hash of every field. 0 differences on x86_64 and on aarch64 under qemu.
  1.6.2's module differs on 26,108 of the documents, the corpus being dense in the edge shapes.
  Eight mutants (each side of the marker rule, the header clamp, each side of the delimiter rule,
  the body start, a count pass stepping past the newline) give 3,632–22,985 differences each and
  fail the pinned rows too.
- **The floor stays 6.7.9.** In a scratch copy pinned to 6.7.9 with its `lib/`: the build and all 6
  test files are warning-free (the CSV vectors 0 wrong there too), the smoke entry exits 42, and
  6.7.9's `distlib --all --check` accepts the bundles 6.7.12 generated.
- Gates, all green on the 6.7.12 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz, bench, coverage 506/506 (the three new json functions included), the cost gate.
  aarch64 under qemu: build, smoke, test, deprecated lookups, fuzz, bench, the cost gate, the PDF
  writer byte-identical across targets. Also: format, lint (0/0 across `src/`), `vet`, the arch-arm
  check, the vendored-fold guard, `distlib --all --check`, regeneration with no change,
  `scripts/consumer-check.sh` and the raw-include build. Then the CI mirror: every `ci.yml` job,
  each in its own fresh copy of the tree, on the 6.7.12 release, all six green, including the new
  CSV regeneration step.

### Docs

- [`docs/development/roadmap.md`](docs/development/roadmap.md): the 1.7.0 section is gone. Added:
  **1.7.1**, csv's allocation refusals (Known gap 16, found here); a **1.8.0** item for cyml CRLF
  lines (Known gap 17); `JSON_K_*` in 1.10.0's `const` list. `state.md` refreshed: Known gaps 10, 14
  and 15 are closed, 16 and 17 open.

## [1.6.2] — 2026-10-15

Patch release, the roadmap's 1.6.2 slot. On aarch64, **`bayan_u128_divmod` by a divisor below
2^64 runs in 7.3–7.9× a plain 64-bit division under qemu, down from 644–707×** (about 21 µs to
230 ns per call). Through 1.6.1 it took 128 shift-subtract rounds there, while x86 took two `div`.
`bayan_u128_div`, `_mod`, `_diveq` and `_modeq` go through it. Answers are unchanged: 298 new
oracle rows aimed at the new routine's correction steps, and a 1,000,000-division differential
against 1.6.1 on aarch64, with 0 differences. Public API: nothing added or removed. x86_64 and cx
compile what they did, and a divisor of 2^64 or more is still divided bit by bit on every target.
The pin stays 6.7.12, and the floor 6.7.9 (checked there).

### Changed

- **aarch64 `bayan_u128_divmod`: a divisor below 2^64 takes two-digit Algorithm D over `udiv`**
  (Known gap 11). aarch64 has no 128-by-64 divide, so 1.0.2 sent it to the portable shift-subtract
  loop, three to five helper calls a round, 128 rounds. 1.5.10 gave mulmod its own asm and left
  this, because no mulmod path reached it any more. The new block in `bayan_u128_divmod` takes
  `q.hi = a.hi / d` and `u1 = a.hi % d` with `udiv`/`msub`, then divides `u1 * 2^64 + a.lo` by `d`
  with Knuth's Algorithm D in two 32-bit digits (Hacker's Delight's `divlu`). That is the routine
  1.5.10's mulmod block runs for its remainder, keeping the quotient as well. Four `udiv`, no loop
  over bits, no calls. The proof is in the comment above it. `u1 < d` bounds the quotient to 64
  bits. Each digit's estimate is at most 2^32 + 1 and corrects at most twice. Neither `q-hat * vn0`
  nor `rhat << 32` can overflow, because `rhat` is checked against 2^32 with `b.lo` before every
  retest; a `b.ls` there would decrement a correct digit at `rhat == 2^32`. The mod-2^64 partial
  remainders are exact. Unlike mulmod's, the numerator is any value below `d * 2^64`, so both
  correction loops are live: either digit can need its second correction. The two `b.hs` tests are
  redundant (with a two-digit divisor the product test alone is exact) and stay, as they do in
  mulmod, for fidelity to the textbook routine.
- **The block reads its parameters with `param_load`** and the limbs through the pointers, so it
  does not depend on the fn's local layout as the x86 block does. It loads every input before its
  first store, so `qdst` or `rdst` may be `a` or `b` (`bayan_u128_diveq` passes `dst` as both).
  Scratch is x0–x15, as in mulmod's block. The 58 encoded words (the four `param_load`s are the
  compiler's) were assembled by llvm-mc 23.1.1 and by GNU as 2.47, which agree on every word, and
  read back with objdump, which places every branch on the label named beside it. Except for the
  moves in and out, the two correction loops are mulmod's words.
- **`scripts/check-arch-arms.py` gains `FN:asm`**, a check of the asm blocks alone: one survives on
  x86_64 and on aarch64, none with neither macro. `bayan_u128_divmod`'s hardware arms are fast
  paths in front of a loop that every target compiles, so it has no `result` for an arm to set,
  which is what the plain mode requires. CI's static step now checks `bayan_u64_mulmod
  bayan_u128_divmod:asm`. Three planted mis-gatings each turn it red: the aarch64 macro misspelt,
  the aarch64 arm gated `#ifndef CYRIUS_ARCH_X86` (cx would compile aarch64 bytes), and the x86
  macro misspelt.
- **`dist/` regenerated** (`cyrius distlib --all`, all 10 bundles). `bayan.cyr` and `bayan-u128`
  carry the block (+126 lines). The other eight change only their version header. The `.deps`
  sidecars are unchanged, and a second regeneration changes nothing.

### Tests

- **`tests/fixtures/numeric/u128.vec` +298 `DV` rows** (5,913 → 6,211 lines), expected values from
  Python's `//` and `%`. `scripts/gen-numeric-vectors.py` splits its `divlu` model into
  `_divlu_core(u1, u0, m)` so that the division can be aimed with the model mulmod's rows use, and
  appends three groups, each after everything before it, so every earlier line is byte-identical.
  - 86 rows aimed (`div_aimed`): 8 or more for each digit's one correction, two corrections, an
    estimate of 2^32 or more, and a loop exit because `rhat` reached 2^32, with a normalising shift
    of 0 and of more than 0. Across all 298 rows, two corrections occur on digit 1 in 29 and on
    digit 2 in 18.
  - 32 rows constructed (`div_rhat_exact`) to leave a digit's loop at `rhat == 2^32` exactly, the
    exit where `b.lo` and `b.ls` differ: 8 per digit and shift.
  - 180 boundary rows (`div_edges`): divisors 1, 2, 3, 2^32 ± 1, 2^32, 2^33 − 1, 2^63 ± 1, 2^63,
    2^64 − 2, 2^64 − 1, `0x80000000FFFFFFFF`, `0xFFFFFFFF00000001` and 10^9 + 7, against dividends at
    the quotient's limits.
  `tests/vectors.tcyr` runs each row through divmod, div and mod: **13,843 u128 checks** (from
  12,651), 0 wrong on x86_64 and on aarch64 under qemu.
- **The mnemonic program, interpreted:** a scratch interpreter of the 58 instructions with 64-bit
  aarch64 semantics (a `nop` standing in for the two `param_load`s before the stores), run on the assembled text, agrees with Python on 100,514 divisions (the 514
  64-bit-divisor rows and 100,000 random ones). Six mnemonic mutants (each back-edge's `b.lo` as
  `b.ls`, the csel, a decrement, the digit shift, a `b.hs` retargeted) give 16–270 wrong rows each.
- **Byte mutants, under qemu-aarch64:** 14 single-word mutants of the real block, against the
  vectors. 12 fail, with 64–1,892 wrong checks each: both back-edges as `b.ls`, both back-edges
  dropped, both decrements dropped, the csel, the digit shift, the `q.hi` and `r.hi` stores, the
  first `udiv`, and the final shift. The two `b.hs` drops survive, as the comment proves they must.
- **Differential, 1.6.1 against 1.6.2 on aarch64: 0 differences.** The 1.6.1 module renamed, beside
  the new one, over 1,000,000 random divisions: divisors of 1–64 bits, dividends of mixed widths,
  just below `d * 2^64`, `2^128 − 1`, and exact multiples. Then 20,000 calls with the quotient
  written into `a` and the remainder into `b`, checked against the non-aliased answer. Two byte
  mutants give 12,819 and 162,135 differences.
- **`tests/mulmod_speed.cyr` gains three divmod rows** (a 128-bit dividend over 31-, 62- and 64-bit
  divisors, each call's high word fed by the last answer), against the same floor and 50× limit. On
  1.6.1, aarch64 measures 644–707× and the program exits 3; on 1.6.2 it measures 7.3–7.9×, and
  x86_64 6.5–6.6× (call overhead included). CI's two cost steps are renamed to say so.
- **The floor stays 6.7.9.** In a scratch copy pinned to 6.7.9 with its `lib/`: the build and all 6
  test files are warning-free, the smoke entry exits 42, `tests/vectors.tcyr` built by 6.7.9's
  aarch64 compiler gives 13,843 u128 checks with 0 wrong under qemu (so the block and its
  `param_load`s work on that backend too), and 6.7.9's `distlib --all --check` accepts the bundles
  6.7.12 generated.
- Gates, all green on the 6.7.12 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz, bench, coverage 503/503, the cost gate. aarch64 under qemu: build, smoke, test,
  deprecated lookups, fuzz, bench, the cost gate, the PDF writer byte-identical across targets.
  Also: format, lint (0/0 across `src/`), `vet`, the arch-arm check, the vendored-fold guard,
  `distlib --all --check`, regeneration with no change, `scripts/consumer-check.sh` and the
  raw-include build. Then the CI mirror: every `ci.yml` job, each in its own fresh copy of the tree,
  on the 6.7.12 release (installed through `install.sh`, checksum and signature verified), all six
  green.

### Docs

- [`docs/development/roadmap.md`](docs/development/roadmap.md): the 1.6.2 section is gone; 1.7.0 is
  next. [`docs/benchmarks.md`](docs/benchmarks.md) gains the divmod table. `state.md` refreshed:
  Known gap 11 is closed for 64-bit divisors.

## [1.6.1] — 2026-10-15

Patch release, the roadmap's 1.6.1 slot. The toolchain pin moves **6.7.11 → 6.7.12**. cyml's three
`---` searches get 1.6.0's treatment and hop from line to line: a single-entry document with a
200-line header parses in **0.40×** 1.6.0's time, and `bayan_cyml_split` runs in 0.25×.
`bayan_cyml_parse` returns 0 when an allocation is refused, where it faulted, and its file loader
returns an `Err`. Smaller items: the flag loops become `loop`, a wrong comment in `u128` is fixed, CI
refuses any route to the vendored `lib/bayan.cyr`, and the five unwritten ADRs are written. Public
API: nothing added or removed. A parse that is not refused memory returns what 1.6.0 returned for
every input, and the differential under Tests is the proof. The two delimiter answers that a fix
would change are pinned for 1.7.0. The sources and `dist/` still build on cyrius ≥ 6.7.9 (checked on
6.7.9; see the pin entry).

### Changed

- **The `---` searches hop from newline to newline instead of testing every byte.** The single-entry
  search, each entry's search and `bayan_cyml_split` called `_cyml_is_delim(data, len, pos)` at every
  byte offset. That is the shape 1.6.0 removed from the marker scan, left in place then because an
  entry's header is short. The new private `_cyml_next_delim(data, len, i)` returns the first
  delimiter at or after `i`. It walks to each newline in a tight loop and compares `---\n` only there
  (`_cyml_delim_at`), testing the flush form at byte 0 first. An entry's search passes the entry's
  end as `len`, as before. Measured with both modules in one binary, fastest of 9 interleaved rounds
  of 200 parses, on a host at load average ~15, so the ratios are the result, not the times:

  | Document | Bytes | 1.6.0 | 1.6.1 | 1.6.1 / 1.6.0 |
  |---|---:|---:|---:|---:|
  | parse, 95-entry font | 8,816 | 50.5 µs | 46.1 µs | 0.91 |
  | parse, 300-entry font | 27,676 | 159.3 µs | 143.5 µs | 0.90 |
  | parse, one entry, 200-line header | 6,922 | 54.4 µs | 22.1 µs | 0.40 |
  | parse, 50 entries × 20-line headers | 24,768 | 243.4 µs | 131.2 µs | 0.54 |
  | `bayan_cyml_split`, 200-line header | 6,922 | 44.1 µs | 10.9 µs | 0.25 |

  A font entry's header is one line, so the font rows move least, as 1.6.0 predicted.
- **Removed (private): `_cyml_is_delim`.** `_cyml_next_delim` answers what it answered at every
  offset (pinned below). Nothing else in bayan called it.
- **Two answers the searches keep, now pinned so that changing them is a decision.** Both are the
  same edge in two places: a delimiter at the start of the searched region. (1) `"\n---\n"` at byte 0
  is not a delimiter. Byte 0 is tested for the flush form `---\n` only, so a document that opens with
  a blank line and then `---` has no delimiter, and its whole text is header. 1.5.1 fixed this shape
  in the marker scan. (2) An entry's search starts past its marker's newline, so a `---` flush against
  the marker (`[[entries]]\n---\nA\n`) is header text (`---\nA`), and the entry has no body. Both
  date from 1.0.0. Fixing either changes what a document parses to, which a patch does not do, so
  they join the roadmap's 1.7.0 slot.
- **Flag loops → `loop { … break; }`, all nine** (the roadmap counted the five whose flag is named
  `go`): `_toml_scan_key_a`, `bayan_toml_inline_parse_a`, the four read loops of `_toml_slurp`,
  `bayan_toml_parse_file_r`, `_json_slurp` and `bayan_json_parse_file_r`, cyml's
  `_cyml_read_file_trimmed` and `bayan_cyml_parse_file_r`, and the quoted-field scan in
  `bayan_csv_parse_line`. In each, the flag was set as the body's last action, so `break` exits at the
  same point. No behaviour change: the suite, fuzz and the differential are unchanged.
- **`src/u128.cyr`: the comment above `_u128_lshr64` said cyrius `>>` sign-extends** (Known gap 13).
  It is a logical shift. Re-measured on 6.7.12: `-16 >> 2` is `0x3ffffffffffffffc` on x86_64, on
  aarch64 under qemu and on cx (a local `cycc_cx`; the release ships none). The mask stays, and the
  comment now says why: one AND keeps the shift unsigned whatever a backend's `>>` does.
- **cyrius pin `6.7.11` → `6.7.12`.** `lib/` re-vendored by `cyrius lib sync --full --relock`: 113
  files, byte-identical to the 6.7.12 snapshot (installed from the tag, `97abbfec`; its
  `SOURCE_COMMIT` records that the tree matches the tag), and `cyrius.lock` covers all 113
  (`deps --verify`). 31 files changed. One is `lib/bayan.cyr`, cyrius's fold of bayan 1.6.0,
  byte-identical to 1.6.0's `dist/bayan.cyr`. On 6.7.12, `cyrius deps` alone refuses to re-lock
  while `lib/` holds files that its resolve did not vendor (22 of them here) and names
  `lib sync --full` as the fix, so on a bump the order is now `lib sync --full --relock`, then
  `deps` and `deps --verify`. The 1.6.0 sources built and passed every gate on 6.7.12 before any
  change, on x86_64 and on aarch64 under qemu, and `distlib --all --check` passed with `dist/`
  unchanged. **The floor stays 6.7.9**: checked in a scratch copy pinned to 6.7.9 with its `lib/`
  (see Tests).
- **`dist/` regenerated** (`cyrius distlib --all`, all 10 bundles). `bayan.cyr` and `bayan-cyml`
  carry the delimiter scan and the refusal checks. Every bundle that holds one of the loops changes
  only there (`bayan-csv`, `-json`, `-yaml`, `-toml`), and `bayan-u128` carries the comment. The other
  three change only their version header. The `.deps` sidecars are unchanged, and a second
  regeneration changes nothing.

### Fixed

- **`bayan_cyml_parse` returns 0 when an allocation is refused** (the last item of Known gap 9). The
  doc, the single-entry array, each entry and the multi-entry array were stored through unchecked,
  so under allocator exhaustion the parse wrote to address 0. The module header had said so since
  1.5.3. The entry-offset array was checked, but it answered with the doc built so far, no header
  and no entries, which a caller cannot tell from an empty document. Each is checked now, and a
  refusal returns 0. The three arrays called bare `alloc`, while the doc and entries went through
  `default_alloc()`. All of them now go through `default_alloc()`, the same global bump allocation
  as before, so one lever reaches every allocation point.
- **`bayan_cyml_parse_file_r` returns `Err(CymlIoErr)` on every refused allocation**, never
  `Ok(0)`, the convention toml's loader has followed since 1.5.11: every accessor answers 0 for a 0
  doc, so `Ok(0)` would read as an empty document. Only the read chunk was checked before. A refused
  builder or chunk `Str` faulted, a refused grow ended the process (the default `str_builder_add`
  does), and a refused result or parse faulted. The loop now appends with `str_builder_add_a`, which
  reports a refused grow, and the chunk comes from `default_alloc()`.

### Added

- **CI: `Nothing reaches the vendored fold lib/bayan.cyr`** (`static` job;
  `scripts/vendored-fold-guard.sh`, Known gap 4). Every `lib sync --full` vendors cyrius's fold of an
  older bayan back into `lib/`, and it defines every symbol `src/` does. The guard fails on three
  routes to it: an include of `lib/bayan.cyr` or a `lib/bayan-<name>.cyr` sublib from `src/`,
  `tests/` or `scripts/` (comment lines are not includes, since `src/` headers name the bundle for
  consumers); `bayan` in `cyrius.cyml`'s `[deps].stdlib`, or a `[deps.bayan]` table, either of which
  makes `cyrius build` prepend it to every build with no include line; and a `bayan` leaf in a
  `dist/*.deps` sidecar, which `consumer-check.sh` would include from `lib/`. Each route was planted
  in a scratch copy of the tree (an include from each of the three directories, the two manifest
  forms, a sidecar leaf) and each turned the guard red. A comment naming the file and the unchanged
  tree stayed green.

### Tests

- **`tests/bayan.tcyr` +29: "cyml: the --- searches hop line to line and find what the per-byte
  test found (1.6.1)".** It carries a copy of 1.6.0's `_cyml_is_delim`. From every offset of every
  prefix of 10 documents, `_cyml_next_delim` must return the first offset where the copy says yes, or
  `len`. That covers an entry's end bound too, because an entry's search is a prefix. The 1-entry
  font is checked at every prefix and the 95-entry one at full length: 26,461 offsets in all. Parse
  and split results are pinned, including both kept answers above. These are 1.6.0's values: the
  group passes unchanged against the 1.6.0 module with only the two new helpers appended. Six
  mutants each fail it: testing `\n---\n` at byte 0, dropping the flush test, comparing at the
  newline instead of after it, starting the walk one byte late, bounding an entry's search by the
  document instead of the entry, and an off-by-one `at + 4 >= len`. Comparing at the newline fails
  eight rows, then faults in a later row that reads the missing span.
- **Differential, 1.6.0 against 1.6.1: 0 differences.** The 1.6.0 module, renamed, against the new
  one in one binary, over two corpora of 40,000 random token documents (0–39 tokens: delimiters with
  and without their newline, CRLF and space-padded near misses, `--`, `----`, markers in each form,
  lone `[` `]` `\r` `\n`, text). The second corpus is weighted towards markers. Each document is
  parsed and split at every prefix length: 7,811,233 parses, 2,970,654 of them multi-entry, compared
  field by field (doc header, every entry's header and body pointers and lengths) along with the five
  outputs of `bayan_cyml_split`. 0 differences on x86_64, and 0 on aarch64 under qemu. The six
  mutants above give 17,888–2,913,008 differences each.
- **`tests/bayan.tcyr` +10: "cyml: bayan_cyml_parse returns 0, and the loader an Err, on every
  refusal (1.6.1)".** toml's lever from 1.5.13: the default allocator's alloc slot is swapped for one
  that refuses only the k-th request, for every k of one parse. Three documents are swept: no
  delimiter (1 request), one entry (3) and three entries (6). Every refused parse returns 0. Then
  every request of a whole `bayan_cyml_parse_file_r` load (12: the chunk, the builder, a chunk
  `Str`, a grow, the result and its `Str`, and the parse's 6) is refused alone, and each load is an
  `Err`. The request counts are pinned, so an allocation that left the default allocator would be
  seen. Thirteen mutants each fail it: each of the eleven new checks removed alone (the offset
  array's put back to `return doc`), and the offset array or the chunk put back on bare `alloc`.
  Six of them fault, one ends the process with `str_builder: alloc failed`, and six fail a named row.
- **`tests/bayan.bcyr` gains `cyml_parse (one entry, 200-line header, 6.9KB)`**: 19.8 µs in one
  `cyrius bench` run (140.1 µs under qemu-aarch64). The 95-entry font row barely reaches the `---`
  search, because a font entry's header is one line, so this row puts the search under the bench.
- **The floor stays 6.7.9.** In a scratch copy pinned to 6.7.9 with 6.7.9's `lib/`, the build and
  all 6 test files are warning-free, the smoke entry exits 42, 6.7.9's `distlib --all --check`
  accepts the bundles 6.7.12 generated, and the guard passes. The new `loop` statements and
  `str_builder_add_a` compile there.
- Gates, all green on the 6.7.12 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz, bench, coverage 503/503 (it counts public functions; the private helpers moved),
  mulmod speed, the PDF oracle and font metrics. aarch64 under qemu: build, smoke, test,
  deprecated lookups, fuzz, bench, mulmod speed, the PDF writer byte-identical across targets. Also:
  format, lint (0/0 across `src/`), `vet`, `distlib --all --check`, regeneration with no change,
  `scripts/consumer-check.sh`, the raw-include build, and the new guard.
- **The CI mirror, on the release toolchain: all six jobs green.** The 6.7.12 release was installed
  through cyrius's `install.sh` into an isolated home (checksum and Ed25519 signature verified), and
  its `lib/` is byte-identical to bayan's (113 files). Then every `run:` step of `ci.yml` ran job by
  job, each job in its own fresh copy of the tree: `toolchain`, `static`, `x86_64`, `aarch64` (qemu),
  `oracles` and `dist`. So the committed `dist/` is exactly what the release's `distlib` generates,
  not only the local install's. The release tarball also ships `bin/cycc_cx`, which no release had
  before (Known gap 12; noted, not acted on).

### Docs

- **Five ADRs, written after the fact** for decisions that had no record beyond this file:
  [0005](docs/adr/0005-the-data-format-modules-are-carved-out-of-the-stdlib.md) the carve,
  [0006](docs/adr/0006-legacy-names-are-forwarding-aliases-in-one-last-module.md) the `_compat`
  aliases, [0007](docs/adr/0007-per-format-sublibs-beside-the-full-bundle.md) the per-format sublibs,
  [0008](docs/adr/0008-yaml-parses-into-the-json-value-tree.md) yaml parsing into json's tree, and
  [0009](docs/adr/0009-toml-strings-are-decoded-in-the-parser.md) 1.5.3's choice to decode TOML
  strings in the parser (Known gap 5). Each names the release that decided, and marks any alternative
  its record does not mention. 0009's argument is the case for yaml's escapes (1.8.0): the json tree
  does not record quote style either.
- [`docs/development/roadmap.md`](docs/development/roadmap.md): the 1.6.1 section is gone, and 1.7.0
  gains the two kept delimiter answers. [`docs/benchmarks.md`](docs/benchmarks.md) gains the
  delimiter table. `state.md` refreshed: Known gaps 4, 5, 9 and 13 are closed or narrowed.

## [1.6.0] — 2026-10-15

Opens the 1.6 line. **`bayan_cyml_parse` takes 0.39× 1.5.14's time.** Since 1.5.1 it had tested
every byte for an `[[entries]]` marker, twice. bannermanor found it (`font_load_file` ~45% slower
since bayan 1.5.2). The toolchain pin moves **6.7.9 → 6.7.11**, and the roadmap now lists only open
work, sequenced as 1.x.x release slots. Public API: nothing added or removed, and no public function
returns anything different for any input. The differential under Tests is the proof. The sources
and `dist/` still build on cyrius ≥ 6.7.9 (checked on 6.7.9; see the pin entry).

### Changed

- **`bayan_cyml_parse` hops from marker to marker instead of testing every byte**
  ([issue 2026-10-15](docs/development/issues/archived/2026-10-15-cyml-parse-scans-every-byte-twice.md),
  found by bannermanor). 1.5.1 replaced the 256-slot array, which silently truncated larger
  documents, with two passes: count the markers, allocate exactly, fill. Each pass called
  `_cyml_is_entries(data, len, i)` at every byte offset. Nearly every call answered "not a
  newline", so the parse was a function call per input byte, twice, about double 1.4.0's one pass.
  A marker can only begin a line. The new private `_cyml_next_entries(data, len, i)` returns the
  first marker position at or after `i`: it walks to each newline in a tight loop and runs the
  12-byte compare only there, checking a marker flush at byte 0 first (1.5.1's leading-newline fix).
  Both passes use it. The skip after a match (12 at offset 0, 13 elsewhere) and everything after the
  scan are unchanged. Measured with both parsers in one binary, fastest of 9 interleaved rounds:
  75.1 → 29.7 µs (a 69-entry font, 6.4 KB), 103.6 → 41.2 µs (95 entries, 8.8 KB), 328.7 →
  129.9 µs (300 entries, 27.7 KB). That is 0.39× at every size, faster than 1.0.1's one pass (0.48–0.56×
  of 1.5.14 in the issue's measurements; see [`docs/benchmarks.md`](docs/benchmarks.md)). The two passes stay. The issue measured one
  pass into a doubling array as faster again, but `alloc` is a bump allocator, so every outgrown
  array would stay behind, which 1.5.1's exact count avoids.
- **Removed (private): `_cyml_is_entries`**, the per-byte test. `_cyml_next_entries` answers what
  it answered at every offset (pinned below) and carries its 1.5.1 offset-0 note. Nothing else in
  bayan called it.
- **cyrius pin `6.7.9` → `6.7.11`.** `lib/` re-vendored by `cyrius deps`, then `cyrius lib sync
  --full --relock`: 113 files, byte-identical to the 6.7.11 snapshot (installed from the tag,
  `99c681d2`), and `cyrius.lock` covers all 113 (`deps --verify`). 18 files changed. One is
  `lib/bayan.cyr`, cyrius's fold of bayan 1.5.14, byte-identical to 1.5.14's `dist/bayan.cyr`. The
  1.5.14 sources built and tested warning-free on 6.7.11 before any change, and
  `distlib --all --check` passed with `dist/` unchanged. **The floor stays 6.7.9**, because 1.6.0
  uses nothing newer. Checked in a scratch copy pinned to 6.7.9 with 6.7.9's `lib/`: the build and
  all 6 test files are warning-free, and 6.7.9's `distlib --all --check` accepts the bundles 6.7.11
  generated.
- **`dist/` regenerated** (`cyrius distlib --all`, all 10 bundles). `bayan.cyr` and `bayan-cyml`
  carry the scan (+1,400 bytes each; the base bundle goes 17,098 → 17,117 lines). `bayan-pdf` and the
  base bundle carry one re-worded comment (below). The other seven bundles change only their version
  header. The `.deps` sidecars are unchanged, and a second regeneration changes nothing.
- **`src/pdf.cyr`: the encryption refusal's comment** points at the roadmap's "Out of scope"
  section, which lost its "(for v1.0)". cyrlint wants the cross-reference on the same line as the
  phrase it tracks, so the two lines are re-wrapped. Lint: 0 warnings, 0 untracked deferrals.

### Tests

- **`tests/bayan.tcyr` +25 (1,489 → 1,514): "cyml: the marker scan hops line to line and finds
  what the per-byte test found (1.6.0)".** It carries a copy of 1.5.14's `_cyml_is_entries`. From
  every offset of every document, `_cyml_next_entries` must return the first offset where the copy
  says yes, or `len`. The documents are the issue repro's 12 plus a 13th, checked at every prefix
  length; the 95- and 300-entry fonts are checked at full length only. That is 54,803 offsets. The
  documents' parse results are pinned too. These are 1.5.14's values: the group passes unchanged
  against the 1.5.14 parser with only the new helper appended. Four mutants each fail the group:
  dropping the byte-0 marker test, comparing the marker at the newline instead of after it,
  starting the walk one byte late, and a count pass that skips 12 where the fill pass skips 13. The
  last survived the repro's 12 documents, whose adjacent markers sit at byte 0, where the skip is 12
  anyway. The 13th document (adjacent markers after the first line) is what catches it.
- **Differential, 1.5.14 against 1.6.0: 0 differences.** The 1.5.14 `bayan_cyml_parse` and
  `_cyml_is_entries`, extracted and renamed, against the new parser in one binary. The input was
  40,000 random documents of 0–39 tokens (`[[entries]]` with and without its newline or with CRLF,
  a near-miss `[[entrie]]`, `---` delimiters, lone `[` `]` `\r` `\n`, spaces, text), each parsed at
  every prefix length: 4,601,648 parses, 1,799,047 of them multi-entry. Compared field by field
  (header and entry pointers and lengths). 0 differences on x86_64 and on aarch64 under qemu. The
  four mutants above give 38,635–292,213 differences each.
- **`tests/bayan.bcyr` gains `cyml_parse (95-entry font, 8.8KB)`**, as the issue asked. A CYML row
  at 1.5.1 would have shown the slowdown.
- Gates, all green on the 6.7.11 pin. x86_64: build, smoke, `cyrius test` (6/6), the deprecated
  lookups, fuzz, bench, coverage 503/503, mulmod speed. aarch64 under qemu: build, smoke, test,
  deprecated lookups, fuzz, bench. Also: format, lint (0/0 across `src/`), `vet`,
  `distlib --all --check`, regeneration with no change, and `scripts/consumer-check.sh`.

### Docs

- **[`docs/development/roadmap.md`](docs/development/roadmap.md) lists only open work, in release
  slots.** The finished sections are gone (the pin moves to 6.6.6, 6.7.5 and 6.7.9, the 6.6.13 and
  6.6.16 follow-ups, YAML, PDF, M0, and the scaffold's empty M1 / M2), and the CHANGELOG remains
  their record. What is open, gathered from the roadmap, `state.md`'s Known gaps and Next, and this
  release's issue: **1.6.1** the rest of the cyml scans, its allocation refusals, flag loops →
  `loop`, a wrong `u128` comment, a guard against including the vendored `lib/bayan.cyr`, and the
  unwritten ADRs. **1.6.2** aarch64 128/64 division. **1.7.0** silently wrong output (csv RFC 4180,
  `bayan_json_build`'s quoting, cyml's adjacent markers). **1.8.0** yaml escapes. **1.9.0**
  `bayan_markdown_*`. **1.10.0** `const` / `: bool` public names. **1.11.0** TOML into the tagged
  tree and one lookup key type. **1.12.0** the security audit and the frozen surface. Then the
  traits work, gated on cyrius shipping checked `dyn`, and the out-of-scope list.
- **[`docs/architecture/001`](docs/architecture/001-str-parameters-are-handles.md), the first
  architecture note.** Three PDF constructors keep their `: Str` parameter, which is safe only
  because cyrius passes a `Str` as a handle. This is the 6.6.6-pin analysis from 1.5.7, and the one
  part of the deleted roadmap sections that had no other home.
- [`docs/benchmarks.md`](docs/benchmarks.md) gains the CYML section. The issue is archived with a
  RESOLVED banner, and its repro moves to `issues/archived/repros/`. After the fix the repro compares
  the parser with itself, so it stays as the record of the documents and the measurement, and the
  `.tcyr` group is the guard. `CLAUDE.md` and the README describe the roadmap as open work by
  release slot. `state.md` refreshed.

## [1.5.14] — 2026-10-11

Patch release. The toolchain pin moves **6.7.5 → 6.7.9**, and `bayan_f64_parse` hands its numbers
to cyrius's new public `f64_parse_n` instead of carrying its own copy of the parser (B-4). Public
API: no addition, no removal, and no public function returns anything different for any input —
the differential under Tests is the proof. ⚠ **bayan now needs stdlib `math`: a consumer with a
hand-written include list must include `lib/math.cyr` before `lib/bayan.cyr`** (and vendor it; the
`.deps` sidecars that need it name it). Building bayan, or a `dist/` bundle, needs cyrius ≥ 6.7.9.

### Changed

- **`bayan_f64_parse(s, n)` delegates to the stdlib's `f64_parse_n(s, n)`** (lib/math.cyr, public
  from cyrius 6.7.9; cyrius issue 2026-10-08-f64-parse-no-public-length-bounded-form). Its core is
  the port of bayan's own correctly rounded parser that cyrius 6.6.13 took, so the ecosystem now
  carries one copy of a numerically delicate routine instead of two to keep in step. The one point
  the two fronts disagree on stays on bayan's side: `f64_parse_n` takes only a whole `nan` / `inf`
  inside the span and reads any other n/N/i/I start as 0, while bayan's readers have always read
  ANY n/N start (after spaces / tabs and a sign) as quiet NaN — `null` included — and any i/I start
  as ±Inf. bayan keeps that front and passes every other input through. `bayan_f64_from_json` and
  json's `_jp_atof` are unchanged; they call `bayan_f64_parse`.
- **Removed (private): the parser-only code in `src/dtoa.cyr`** — `_d_diyfp_round`, `_d_approx`,
  `_d_decexp_index`, `_d_dec_trim`, `_d_dec_step`, `_d_dec_rsh`, `_d_dec_lsh`, `_d_dec_shift`,
  `_d_dec_round`, `_d_dec_set`, `_d_exact`, `_D_WINDOW`, `_D_UNDECIDED`, `_D_DEC_CAP`,
  `_D_DEC_MAXSH` and the exact-power table `_D_POW10_EXACT` (with its 23 stores in
  `_d_init_tables`). `bayan_f64_to_json` (Grisu2) keeps `_D_POW10_SIG`, the once-claimed
  `_d_init_tables` and every helper it calls. 933 → 463 lines; `dist/bayan.cyr` 735,730 → 716,985
  bytes (−18,745; 17,567 → 17,098 lines), and the same −18,745 in `bayan-json` and `bayan-yaml`.
  No bayan file, test or script referenced a removed name except `tests/dtoa.fcyr` (below).
- **bayan needs stdlib `math`.** It is in `cyrius.cyml [deps].stdlib`; the 6.7.9 distlib adds it to
  the `.deps` sidecars of the base bundle, `bayan-json` and `bayan-yaml` (10 → 11 leaves) and to
  their `# Requires` blocks; the hand-written include lists of `src/main.cyr` and the tests that
  reach the json / yaml number path carry `lib/math.cyr`, and `scripts/consumer-check.sh`'s
  canonical order places it. `lib/math.cyr` includes nothing and defines no name bayan defines
  (its parser helpers carry a private `_f64p_` prefix for exactly that reason): every build here
  is warning-free, including the differential's binary, which holds both parsers and math.cyr.
- **cyrius pin `6.7.5` → `6.7.9`.** `lib/` re-vendored by `cyrius deps`, then `cyrius lib sync
  --full --relock`: 113 files, byte-identical to the 6.7.9 snapshot; `cyrius.lock` covers all 113.
  The 1.5.13 sources built and tested warning-free on 6.7.9 before any change, with `dist/`
  unchanged.
- **Parse cost rose**, measured by the bench's per-tier rows (minimum of 9 interleaved runs):
  tier 1 132 → 172 ns (+30%), tier 2 227 → 321 ns (+41%), tier 3 +6–9%. The stdlib core keeps its
  cached powers as hex text and decodes one per lookup (~50 ns, against a ~3 ns load from bayan's
  table), and the input's front is scanned three times (bayan's, the strict entry's, the core's).
  See [`docs/benchmarks.md`](docs/benchmarks.md).
- **`dist/` regenerated** (`cyrius distlib --all`, all 10 bundles): `bayan.cyr`, `bayan-json` and
  `bayan-yaml` carry the change; the other seven change only their version header.
- ADR-0003 records that the parser it describes now lives in the stdlib.

### Tests

- **Differential, 1.5.13 against 1.5.14 — 0 mismatches.** The 1.5.13 `bayan_f64_parse` (from the
  tag, renamed `_d_` → `_o_`) and the new one, in one binary, return the same 64-bit pattern for
  every one of **1,145,999 strings**, each run four ways: the span followed by more digits
  (n = length); NUL-terminated (n = 2³¹−1, and `bayan_f64_from_json`); the span ending at a
  PROT_NONE page (a read of `s[n]` faults); and the span cut at a random point, at 0, negative, or
  past its end — 5.7 million comparisons. The strings: **27,296** from bayan's own tests (both
  `f64*.vec` files, every string literal and number token in `tests/`, the fixtures' numbers, the
  explicit-length calls); **18,707** from cyrius's `tests/tcyr/math/f64_parse_rounding.tcyr`
  (its corpus, its explicit-length rows with their n, the 10,000 two-decimal literals with a digit
  after the span) and the other cyrius f64 tests' literals; **1,099,996** generated — 297,297
  random decimals (spaces / tabs, signs, 0–30 integer and fraction digits, leading zeros, 1–7-digit
  and garbage exponents, trailing bytes), 297,297 near-halfway (exact binary midpoints written in
  full, ± a far digit, cut to 16–60 digits and nudged, across the normal, subnormal and overflow
  seams), 198,198 shortest-repr and `%.17g` / `%.Ne`, 59,459 subnormal, 49,549 overflow, 79,279
  garbage, 39,639 n/N/i/I starts, 39,639 long mantissas (to 830 digits), 39,639 integers around
  2⁵³. Also on aarch64 under qemu: 0 mismatches. The 87 cached and 23 exact powers compare equal to
  the stdlib's literals, and a comment-stripped diff of the 1.5.13 tiers against `lib/math.cyr`'s
  core, names mapped, differs only in how `UNDECIDED` is spelled (the same bits), the exact powers'
  table load against an if-chain, and the lazy table init. Three mutants of the new front each turn
  the differential red (`N` not NaN; `n + 1`; a span capped at 600 bytes). The harness is not
  committed: it carries the whole 1.5.13 parser.
- `tests/bayan.tcyr`: **1,489** assertions (from 1,476), 0 failed. The 13 new rows pin bayan's
  lenient front against the strict stdlib entry (`null`, a bare `n` / `i`, signed and spaced
  `NaN` / `In` / `+Infinity`), spans that end before the letter, and the span bound (`2.57,` at
  n = 3; a tie inside the span, and above it read whole). Coverage 503/503.
- `tests/dtoa.fcyr`'s third property (the tiered parser against the exact tier alone, 200,000
  decimals) calls `lib/math.cyr`'s `_f64p_exact`, the stdlib's copy of the former `_d_exact`.
  `tests/dtoa_init.tcyr`'s comment says what its rows race now: only the format reads a bayan table.

## [1.5.13] — 2026-10-08

Patch release for the cyrius **6.7.5** stdlib wave (W2). The toolchain pin moves **6.6.18 → 6.7.5**,
and the three TOML refusal defects the 1.5.11 review found are fixed. Public API: no addition, no
removal; the TOML functions below now report a refused allocation (0) where they returned an empty
string, ended the process, or faulted. ⚠ The sources now use `const` (6.7.2+): building bayan, or a
`dist/` bundle, needs cyrius ≥ 6.7.2.

### Fixed

- **`bayan_toml_escape_a` / `bayan_toml_escape` answered a refused buffer with an empty string**
  (B-1) — `str_from("")`, from the DEFAULT allocator. A caller escaping a value for a TOML file it
  writes wrote `key = ""` and saw no failure. They return 0, as the unescape side has since 1.5.11.
- **`bayan_toml_inline_parse_a` used its allocations unchecked** (B-2). A refused result vec,
  key-parts vec, joined key, pair or push was used as if granted — a refused vec was loaded through
  at address 0 (SIGSEGV). `_toml_join_parts_a` took its builder from `a` but appended and built
  through the default allocator's builder fns, which end the process on a refusal; it now stays on
  `a` and returns 0. The empty end-of-input value in `_toml_parse_value_a` also comes from `a` (it
  was a default-allocator Str made on every call). Every refusal returns 0.
- **`bayan_toml_parse` broke its own "0 on a refusal" contract** (B-3) everywhere but the decode
  arms. Its sections and pairs vecs, sections, pairs, pushes and joined table names went through
  the default wrappers: a refused push or join exited the process with status 1, and a refused
  vec or section was used at address 0. It threads `default_alloc()` through the `_a` forms and
  returns 0 on every refusal. `bayan_toml_parse_file` passes the 0 on and `bayan_toml_parse_file_r`
  reports it as `Err(TomlIoErr)`, as for a refused decode.

### Changed

- **cyrius pin `6.6.18` → `6.7.5`.** `lib/` re-vendored by `cyrius deps`, then `cyrius lib sync
  --full --relock`: 113 files, byte-identical to the 6.7.5 snapshot (written from the 6.7.5 tag),
  and `cyrius.lock` covers all 113. The bump needed no source change and surfaced no warning.
- **`_D_DEC_CAP`, `_JP_STATE_SIZE` and `_PDF_STATE_SIZE` are `const`, and size every stack buffer
  they describe** — dtoa's exact-decimal digits and shift scratch, the three json and two yaml
  parser states, and all nine PdfState locals in pdf.cyr (16 sites). The capacity the bound checks
  read and the bytes reserved were hand-copied literals; they are one fact now. The names are
  private; no behaviour change.
- The default-allocator wrappers `_toml_scan_key` and `_toml_join_parts` had no caller left and
  are removed (private).
- **`dist/` regenerated** (`cyrius distlib --all`, all 10 bundles): `bayan.cyr`, `bayan-json`,
  `-yaml`, `-toml` and `-pdf` carry the source changes, the rest change only their version header.
  No `.deps` sidecar changes.

### Tests

- **Every allocation point refused alone** for the two parsers: `bayan_toml_inline_parse_a` on a
  17-pair fixture (a push past 16 slots, a dotted key, an escaped value, a quoted key) through an
  allocator that refuses its k-th request, and `bayan_toml_parse` on a 24-section document with a
  17-pair table through the default allocator's swapped alloc slot. Each run returns 0; the
  inline sweep also proves every request goes through the allocator it is handed. Without the fix
  both groups die of SIGSEGV.
- `bayan_toml_escape_a` with its buffer, then its Str, refused, and `bayan_toml_escape` under
  `ALLOC_MAX = 128` — 0 each (they were an empty string).
- `tests/bayan.tcyr`: **1,476** assertions (from 1,460), 0 failed. Coverage 503/503.

## [1.5.12] — 2026-10-06

Patch release for the cyrius **6.6.18** sibling regeneration wave. The toolchain pin moves
**6.6.12 → 6.6.18**. No source change: public API, behaviour and output are unchanged.

### Changed

- **cyrius pin `6.6.12` → `6.6.18`** (`cyrius.cyml [package].cyrius`). `lib/` re-vendored by
  `cyrius deps`, then `cyrius lib sync --full --relock` (the pin moved, so the old rows were the
  previous pin's): 113 files, 0 differ against the installed 6.6.18 snapshot (`diff -rq`), and
  `cyrius.lock` covers all 113 (`cyrius deps --verify`). New leaves: `poison.cyr` (6.6.18's
  allocator poison mode, which `alloc.cyr` now includes) and `tls_hostid.cyr`.
- **`dist/` regenerated by the 6.6.18 distlib.** Each `.deps` sidecar is now exactly the stdlib
  leaves the compile-verify fixpoint proves the bundle needs. The base sidecar `dist/bayan.deps`
  goes from 13 leaves to 10:
  - before: syscalls, string, alloc, io, vec, str, fmt, tagged, result, fnptr, assert, bench, atomic
  - after: syscalls, alloc, string, vec, str, io, result, atomic, fmt, fnptr
  - dropped: **tagged**, **assert**, **bench** — bayan's own `[deps] stdlib` names them for its
    tests and bench, and the old generator copied them into the consumer's contract.

  Of the sublibs, `bayan-base64`, `bayan-bigint` and `bayan-csv` drop `str`; the others keep
  their leaves in a new (single-pass) order, and `bayan-u128` is unchanged.
- **Every bundle carries a compile-verified `# Requires` include block**, so
  `include "dist/bayan.cyr"` (or a sublib, or the folded `lib/bayan.cyr`) compiles with nothing
  included before it. Through 1.5.11 distlib stripped every include and the consumer had to
  supply the sidecar's leaves itself, in order.

### Tests

- **`tests/bayan_raw_include.tcyr`** (new, 2 asserts): includes only `dist/bayan.cyr`, then
  `lib/assert.cyr`, and checks `bayan_base64_encode`. Against the 1.5.11 bundle it does not
  compile (`unknown type 'Str'`); against this one it builds with no warning and
  passes. `cyrius test` auto-prepends the manifest's stdlib, which would hide a missing block, so
  CI's `dist` job also builds it with `--no-deps`.
- **The deprecated json lookups moved out of the warning-free suite** (the follow-up recorded at
  cyrius 6.6.16). From 6.6.16 `#deprecated` warns through `&fn` too, and `tests/bayan.tcyr`
  reached `bayan_json_v_obj_get` and `json_v_obj_get` that way precisely because it was silent,
  so `no-warnings.sh cyrius test` went red on the bump (4 warnings). Their 12 rows moved to the
  program `tests/deprecated_lookup.cyr` (13 asserts, direct calls), which
  `scripts/deprecated-lookup.sh` builds expecting EXACTLY one warning per call with the exact
  advice and nothing else (a missing attribute or a stray warning fails it), then runs — on
  x86_64 and under qemu on aarch64. `cyrius.cyml [coverage] programs` puts it in the coverage
  corpus, so `cyrius coverage --min 100` still sees both names: 503/503.
- `tests/bayan.tcyr`: **1,460** assertions (from 1,472; the 12 moved rows), 0 failed.

## [1.5.11] — 2026-10-01

Patch release, cut for cyrius **6.6.13**. ⛔ **Tag it before cyrius 6.6.13 is tagged** — cyrius 6.6.13
folds `dist/bayan.cyr` as `lib/bayan.cyr`. Three fixes, each with tests. The toolchain pin stays at
**6.6.12**. Public API: no addition, no removal; the TOML functions listed below now report a
refused allocation (0, or `Err` from the Result variant) where they returned a substituted answer.

### Fixed

- **`bayan_pdf_use_font` passed a Str's data pointer as a `key: cstring`.** It set each page's
  `/Resources /Font` key with `bayan_pdf_obj_dict_set_a(a, fdict, str_data(name), ..)`. The bytes
  were right — the Str borrows the NUL-terminated buffer `_pdfc_resname_a` built — but cyrius
  6.6.13 warns on `str_data(..)` passed to a `: cstring` parameter (its issue
  2026-10-01-str-cstring-diagnostic-misses-call-results), so every build that includes bayan,
  `tls.cyr` or `tls_native.cyr` would carry that warning. The PdfFont now keeps the buffer itself
  (`+32`; the struct is 40 bytes, from 32) and the key is set from it, on both paths: the first use
  of a face and a later page's use of a registered one, where only the PdfFont has the buffer. The
  writer's output is unchanged byte for byte. Three rows of `tests/bayan.tcyr` that compared with
  `streq(str_data(x), "lit")` use the length-bounded `str_eq_cstr(x, "lit")` now, for the same
  diagnostic.
- **A refused allocation while decoding a TOML string was reported as an empty string.**
  `_toml_unescape_span_a` answered a refused output buffer with `str_from("")` — an EMPTY Str from
  the DEFAULT allocator — so every arm that decodes a basic string (single-line and multi-line
  values, quoted keys, inline-table members) reported the refusal as a parsed empty value. Its
  sibling on the multi-line arm, `_toml_crlf_copy_a`, fell back to a default-allocator view of the
  RAW bytes, CRs and all. Both return 0 now, and every caller stops on it, per the rule 1.5.9 and
  1.5.10 applied to base64, TOML arrays and the flat JSON parser:
  - `bayan_toml_parse` and its alias `toml_parse` return 0 when a key or value is refused.
    `bayan_toml_parse_file` (and `toml_parse_file`) pass the 0 on. `bayan_toml_parse_file_r` (and
    `toml_parse_file_r`) report it as `Err(TomlIoErr)` — the answer they already gave a refused
    read chunk — never `Ok(0)`, which a caller matching `Ok` would hand to `vec_len`.
  - `bayan_toml_inline_parse_a` and its default-allocator wrapper `bayan_toml_inline_parse` return 0
    when a key or value is refused (so does `bayan_toml_get_inline` through them).
  - `bayan_toml_unescape_a` and its wrapper `bayan_toml_unescape` return 0 on a refusal.
  - A refused key segment, or a refused push of one, was dropped or empty; the key scan now reports
    it and the parse stops — in a key/value line and in a `[table]` or `[[array]]` header.
  - `bayan_toml_array_parse_a` already returned 0; its flush no longer needs the `str_len == 0`
    test that existed only to recognise the empty fallback.
- **The f64 tables' first use was not thread-safe on aarch64.** `_d_init_tables` (`src/dtoa.cyr`)
  was a check-then-set with the flag stored last and no barrier, so a second thread could see the
  flag set and read significands that were still zero: a wrong `bayan_f64_parse` or
  `bayan_f64_to_json` answer, with no error. The build is now a 0 → 1 → 2 claim (`atomic_cas`) and
  publish (fence, then store), with an acquire fence on aarch64's fast path — the shape sigil 3.13.6
  gave its own initialisers (cyrius issue 2026-09-30-tls-first-use-thread-race). `atomic` joins
  `[deps] stdlib`; `alloc.cyr` already includes it, so no consumer gains a module.

### Changed

- `dist/` regenerated (`cyrius distlib --all`, under the 6.6.12 pin in an isolated `CYRIUS_HOME`).
  `bayan.cyr`, `bayan-json.cyr`, `bayan-yaml.cyr`, `bayan-toml.cyr` and `bayan-pdf.cyr` carry the
  fixes; the rest change only their version header. The `.deps` sidecars of the bundles that carry
  `dtoa.cyr` gain `atomic`.

### Tests

- `tests/bayan.tcyr`: **1,472** assertions (from 1,437), 0 failed.
  - pdf (+7): the font resource key on both paths — the returned name's bytes, NUL-terminated at
    its length, one buffer with the returned Str.
  - toml (+28): `unescape_a` on a refusing allocator; `inline_parse_a` with ONLY the unescape's
    request refused, for a value and for a quoted key; `bayan_toml_parse` under `ALLOC_MAX = 128`
    for a basic string, a multi-line basic string, a CRLF multi-line string (the copy), a quoted
    key, a quoted `[table]` name, a quoted `[[array]]` name and a 17-segment header whose 17th
    push is refused, each parsing whole without the limit, plus a control; and
    `bayan_toml_parse_file_r` with only the value's decode buffer refused (the default allocator's
    alloc slot swapped and restored — `ALLOC_MAX` cannot reach the decode past the 64 KiB read
    chunk), which is `Err`, beside an unrestricted read of the same file. 11 of these rows fail on
    1.5.10's `src/toml.cyr`.
- `tests/dtoa_init.tcyr` (new, **12** assertions): the claim/publish protocol, and 8 threads held
  at a start word and released together into their FIRST parse and format, each answer equal to
  the answer recomputed after publication. Green 20× on x86_64, 10× under qemu-aarch64 and 300× on
  a Raspberry Pi (aarch64). The race is a probability — 300 Pi runs of the 1.5.10 code did not show
  it either — so the file pins that the protocol completes and agrees with itself; it is its own
  file because it must be the process's first use of the tables.

## [1.5.10] — 2026-10-01

Patch release. Resolves the three open issues, moves the toolchain pin to cyrius **6.6.12**, and
moves the GitHub Actions to their current majors. Public API: two additions
(`bayan_json_v_obj_get_by_cstr`, `bayan_json_parse_a`) and two deprecations
(`bayan_json_v_obj_get`, `json_v_obj_get`); nothing removed.

> ⚠ **`bayan_json_parse` changes what it returns for VALID input.** An object or array value now
> comes back whole, as its raw source span; its members are no longer top-level pairs, and the
> members after it are no longer lost. TAB or CR after a bare value no longer stays in it
> (`0.79\r` is now `0.79`). A member nested deeper than 128 levels (counting the top-level object)
> now stops the parse, as `bayan_json_v_parse` refuses that document. Malformed input now stops
> the parse at the first defect instead of pairing a key with another key's bytes.

### Fixed

- **`bayan_json_parse` handed keys the wrong values**
  ([2026-09-30](docs/development/issues/archived/2026-09-30-json-parse-flat-misassociates-values.md),
  repro 14 of 16 rows wrong on 1.5.9, 0 now). The flat scan had five defects:
  - TAB and CR did not end a bare value: a CRLF document's last value came back as `0.79\r`, which
    a number parse refused. All four JSON whitespace bytes now end one and are skipped around `:`.
  - A nested object or array was read as a bare value, cut at its first `,` `}` space or LF, and
    the scan resumed INSIDE it: for `{"meta":{"x":1,"admin":"true"},"admin":"false"}`,
    `bayan_json_get(pairs, "admin")` answered `true`, from inside meta. A nested value is now ONE
    value, its raw source span; parse the span again to reach inside it. The span scan is
    string-aware and **matches closer kinds** — the filing's proposal counted depth only, which let
    `{"meta":{"x":[}],...}` surface meta's `admin` again. Kinds sit on a 128-bit stack on the
    frame; the scan never recurses.
  - A key whose own `:` was missing took the next pair's value: the scan skipped to the next `:`
    anywhere in the document. `,` was skipped in every state, so `"a":,"b":2` gave a the value `b`.
  - A value followed by `:` was paired, although the `:` made it the next KEY: `{"a":"b":2}` gave
    a = `b` (found by review; the filing's fix closed only the `,` spelling of this).
  - A bare value ran on through `"`, so `{"a":1"b":2}` gave a = `1"b":2`. A bare value now stands
    only when whitespace, `,` or `}` ends it; one cut by `"` `:` `[` `]` or `{` is refused rather
    than returned as the part before the cut, which can parse (`{"GBP":0.7:9}` would give 0.7).

  Malformed input now stops the parse; the vec holds the pairs read before the first defect it
  stops on, never one after it. The defects, and what is still tolerated (bytes outside the first
  object; missing, doubled or trailing commas; unvalidated bare values), are listed in the
  function's header. An unterminated string or nested value, or a bare value the input ends on
  (`"n":12` may be the start of 123), is no longer returned truncated.
- **`bayan_json_parse` checked no allocation.** It carried on past a refused Str and could return a
  shorter vec as success, and a refused growth of the vec ended the process. It now returns 0 when
  any allocation is refused — never a partial vec, the rule 1.5.9 applied to base64 and TOML.
  `bayan_json_get(0, key)` answers 0. `bayan_json_parse(0)` died of SIGSEGV; it is now an empty
  vec, so the documented re-parse `bayan_json_parse(bayan_json_get(pairs, key))` is safe on an
  absent key. `bayan_json_parse_file` and `bayan_json_parse_file_r` pass the 0 on (as 0 and as
  `Ok(0)`) when an allocation inside the parse is refused.
- **`bayan_u64_mulmod` ran a 128-round shift-subtract on every aarch64 call**
  ([2026-09-30](docs/development/issues/archived/2026-09-30-u64-mulmod-aarch64-always-wide.md)).
  The aarch64 arm is now one asm block: `udiv`/`msub` reduction, `mul`/`umulh` product, and the
  remainder by two-digit Knuth Algorithm D (Hacker's Delight fig. 9-3 `divlu`), four `udiv`, no
  loop over bits, no calls. Measured under qemu-aarch64 on release 6.6.12: 19.4–20.2 µs → 63–74 ns
  per call (1–2× a plain `(a*b)%m` call, from ~600×); Miller–Rabin ×200 4.89 s → 17.6 ms. The 54
  instructions were re-assembled independently with llvm-mc 22.1.8 (byte-identical to the
  filing's), every branch checked on its label with objdump, and the frame offsets read from the
  cyrius 6.6.12 aarch64 backend and confirmed by disassembling the compiled function (ELF and
  arm64 Mach-O). The block comment proves the first digit is corrected at most once. The x86 and
  portable code sits under the aarch64 arm's `#else`, so aarch64 compiles only the asm block: its
  function is 332 bytes against 1.5.9's 444. The x86 function is byte-identical.
- **`bayan_u64_mulmod` returned 0 on cx** (found while fixing the above). The cx backend
  predefines no `CYRIUS_ARCH_*` macro, and the function had an x86 arm and an aarch64 arm and
  nothing else, so every call with a, b and m below 2^63 returned the 0 `result` starts at:
  measured with cyrius 6.6.12's `cycc_cx` and `cxvm` (a local install; the release ships no
  `cycc_cx`) over the shipped oracle fixture, 1.5.9 gets 67 of 335 mulmod and 209 of 302 powmod rows
  wrong (the powmod count includes the exponents ≥ 2^63 below, wrong on every target), and 1.5.10
  gets 0 of each. The portable path is now the `#else` of the x86 arm.
- **`bayan_u64_powmod` returned 1 for every exponent at or above 2^63** (found by the same work).
  Its loop was `while (exp > 0)`, a signed test, so the loop never ran. It now runs until the
  exponent is 0 and shifts it with `_u128_lshr64`: `powmod(3, 2^63 + 1, 1e9 + 7)` is 113884165, not
  1. An exponent of 0 still gives `1 % m`.
- **A null key crashed every JSON object lookup.** `_by_cstr` ran `strlen(0)` and `_by_str`
  `str_data(0)`: SIGSEGV, reachable from `bayan_json_v_obj_key`'s documented out-of-range 0. Both
  now return 0, and the deprecated names, which forward to `_by_cstr`, inherit it.

### Changed

- **Deprecated: `bayan_json_v_obj_get` and its alias `json_v_obj_get`**
  ([2026-08-04](docs/development/issues/archived/2026-08-04-agnosai-json-obj-get-takes-cstr-while-obj-set-takes-str.md);
  [ADR 0004](docs/adr/0004-json-lookup-states-its-key-type-by-name.md)). The bare name does not
  say what its key is, and re-measured on 6.6.12 the `: cstring` diagnostic 1.4.1 armed on it
  still misses the filed spelling: `bayan_json_v_obj_get(o, str_from("k"))` compiles with no
  warning and returns 0. Overload routing keys on the first argument only, so it cannot help. New
  **`bayan_json_v_obj_get_by_cstr(v, key: cstring)`** carries the old body; `_by_str` (1.4.1) is
  the Str half. Both deprecated names forward to `_by_cstr`, so every answer is unchanged; the call
  site now warns with which replacement to use. Renaming the bare name to take a Str was rejected
  again: it would silently break every caller passing a non-literal C string. The deprecation flags
  call sites; it does not widen the diagnostic, which stays a cyrius-side gap — filed as cyrius
  `docs/development/issues/2026-10-01-str-cstring-diagnostic-misses-call-results.md`.
- **New `bayan_json_parse_a(a, src)`**, the allocator-threaded form of `bayan_json_parse` (the
  house `_a` convention; it is what the per-allocation-point refusal tests drive).
- **Toolchain pin 6.6.11 → 6.6.12.** `lib/` re-vendored by `cyrius deps` then `cyrius lib sync
  --full`: 22 files changed, and `diff -rq` against the 6.6.12 **release tarball**'s `lib/` reports
  0 differences (111 files). The local install's `cyrius` wrapper differs from the release's, so
  every gate and the `dist/` regeneration ran on the release toolchain in an isolated `CYRIUS_HOME`.
  No source change was needed for 6.6.12 itself (all gates green on the 1.5.9 source first).
- **`cyrius.lock` is new.** Since 6.6.9 `cyrius deps` writes a stdlib-only project's first lock;
  bayan never had one. Relocked after the full sync (111 verified). Two CI steps keep it honest:
  `cyrius deps --verify` on the COMMITTED lock before resolving (exits 1 on a hash mismatch, an
  unlocked file and a missing lock — each measured), and a check that resolving changes nothing in
  `lib/` or the lock (`git status`, which sees untracked files; `git diff` does not).
- **GitHub Actions:** `actions/checkout` v4 → **v7**, `softprops/action-gh-release` v2 → **v3**.
  Both majors move the action runtime to Node 24; checkout v7 also refuses fork checkouts under
  `pull_request_target`, which bayan does not use.
- **CI is six parallel jobs instead of one 32-step job:** `toolchain` (pin, manifest, lock, `lib/`),
  `static` (format, lint, include audit, naming and arch-arm checks), `x86_64` (build, smoke, suite,
  fuzz, bench, coverage, mulmod cost), `aarch64`, `oracles` (PDF validator, font metrics, numeric
  and TOML vector regeneration) and `dist` (bundles, their regeneration, the consumer/deprecation
  gate). A lint slip is no longer reported only after the whole x86 suite, and `release.yml`
  needs all six. Each job installs the pin through one composite action
  (`.github/actions/setup-cyrius`, which also fails on pin drift; `release.yml` uses it too), and
  every build/test/fuzz/bench goes through `scripts/no-warnings.sh`, which fails on the exit status
  or on a `warning:` anywhere in the output — one copy of that rule instead of eight. Run locally
  with each job in its own fresh copy of the tree, all six pass, and none relies on another's
  `cyrius deps` or `build/`; planted defects turn red exactly the jobs that own them.
- **aarch64 is its own track, for the first time in CI.** The program is cross-built by the
  release's x86-hosted `cycc_aarch64` and run under `qemu-user`: build with zero warnings and the
  smoke entry (exit 42), the suite (`cyrius test --aarch64`), all three fuzz harnesses (built and
  run by hand — `cyrius fuzz` has no `--aarch64`; the f64 harness takes minutes under qemu, which is
  why this is not a step in the x86 job), the bench harness, the mulmod cost check, and the PDF
  fixture, whose output must be **byte-identical** to x86_64's (it is: 3,331 bytes) and pass the
  oracle on its own. A native `ubuntu-24.04-arm` runner is not an option: the aarch64-linux release
  tarball ships `cycc` but no `cyrius` CLI, `cyrfmt` or `cyrlint`.
- **The mulmod cost check** (`tests/mulmod_speed.cyr`, both tracks) fails above 50× a plain
  `(a*b)%m` call. It sees a fall back to a bit-serial loop (planted: ~690× on aarch64, red), not
  x86's ~13× hardware-divide wide path; the threshold's reasoning is in the file's header.
  `scripts/check-arch-arms.py` applies `bayan_u64_mulmod`'s conditionals as x86, aarch64 and a
  target with no arch macro, and fails when one has no arm that sets the result or when
  x86/aarch64 has no asm block (a misspelt macro); it is red on the 1.5.9 source, twice over. CI
  cannot compile cx (the release tarball has no `cycc_cx`), so this is the gate that sees the cx arm.
- **CI: every build, fuzz and bench fails on any `warning:`** (Fuzz, Bench, the PDF-fixture and
  mulmod-speed builds used to pass a build that only warned); the Format step covers `tests/*.cyr`;
  the dist regeneration check uses `git status`, which sees a newly created bundle `git diff`
  cannot; a step forbids defining `bayan_json_v_obj_get_by`, the base that would turn
  `_by_str`/`_by_cstr` into live overload slots; and the workflow's token is read-only
  (`permissions: contents: read`).
- **`scripts/consumer-check.sh` gates the deprecations.** Against every bundle that ships a
  deprecated name it compiles direct calls and requires exactly the expected warnings, with the
  exact advice text, and none from the bundle; it counts `#deprecated` attributes over code only
  (comments and strings stripped) wherever on a line cyrius 6.6.12 honours one — its own line,
  after another attribute, and at the end of the previous fn's line, all measured; it refuses any reference to a deprecated name in `src/` or `dist/` (a call parsed
  before the definition does not warn on 6.6.12); and it pins `_by_cstr`'s own `key: cstring`
  diagnostics.
- `dist/` regenerated with the release toolchain (reproducible; `--check` green). `bayan.cyr`,
  `bayan-json.cyr`, `bayan-yaml.cyr` and `bayan-u128.cyr` carry the fixes; `bayan-pdf.cyr` and
  `bayan-toml.cyr` carry a comment that now names `_by_cstr`; the other four change only their
  version header. No `.deps` sidecar changes.

### Tests

- `tests/bayan.tcyr`: **1,437** assertions (from 1,281), 0 failed, on x86_64 and on `--aarch64`
  under qemu. `vectors` 13 (u128 checks **12,651**, from 12,334), `pdf_flate` 19, `src/test.cyr` 3.
  Reference coverage **503/503**.
  - json flat parser (+120): the issue's 16 documents against exact pair lists; nested spans and
    kind matching; the depth cap at 127/128 levels, lowered, raised by one and raised to 100,000;
    unterminated strings and spans; every byte through five byte classes; what may follow a value;
    allocation refusals, including each of a 17-member parse's 54 allocation points refused ALONE
    through a one-shot allocator (a fail-after allocator would let a later check hide a missing
    earlier one).
  - json lookups (+29): `_by_cstr` and `_by_str` agree on prefix keys, the empty key and a repeated
    key (the FIRST wins); null keys return 0; the deprecated names are pinned through `&fn` +
    `fncall2`, a call shape that does not warn on 6.6.12, so the suite needs no warning allowance.
  - u64 (+7): an edge grid and random triples (reduced/raw now independent of modulus length) for
    mulmod; powmod with exponents at or above 2^63.
- `scripts/gen-numeric-vectors.py` adds 317 rows to `u128.vec`, expected values all Python's:
  79 mulmod rows aimed at the Algorithm-D correction steps and large quotient estimates; 56 mulmod
  rows CONSTRUCTED to leave each correction loop at `rhat == 2^32` exactly (both digits, s = 0 and
  s > 0) — a random triple lands there about once in 2^31, and no earlier row told `b.lo` from
  `b.ls` there; 32 powmod rows over 64-bit moduli; and 150 powmod rows with exponents ≥ 2^63.
- New `tests/json.fcyr` (in `cyrius fuzz`): 40,000 valid, 120,000 damaged and 40,000 random
  documents; every key is followed by its own `:`, every value lies inside the source, and the pair
  list equals an independent reader of the documented grammar (and, for valid documents, the
  generator's spans and the tree parser's members). Every document, and every prefix of eight edge
  documents, is also parsed flush against a PROT_NONE page, so a one-byte read past the end
  faults: six over-read mutants passed both suites without the page.
- Mutation-checked: 59 single-edit mutants of the flat parser (57 red; one equivalent, one —
  checking the depth bound after the kind store — guarded by a comment at the check); the asm block
  (each correction step, the csel, the `stur` offset, `umulh`, both `b.lo` exits; the survivors are
  the documented equivalent instructions); powmod's signed loop; and the deprecation gates (lost or
  respelt attributes, swapped advice, a deprecated call in src, a harness or the alias body, either
  null-key guard).

## [1.5.9] — 2026-09-30

Patch release, from cyrius 6.6.12 bite B13 (items SA2, SA10, SA12). ⛔ **Tag it before cyrius
6.6.12 is tagged** — cyrius 6.6.12 folds `dist/bayan.cyr` as `lib/bayan.cyr`. Moves the toolchain
pin to cyrius **6.6.11** and the coverage floor back to **100**. Public API unchanged.

### Fixed

- **`bayan_base64_encode` stored into its own refused alloc.** `src/base64.cyr` used the output
  buffer without checking it, so a length whose output the allocator refuses (past `ALLOC_MAX`)
  died of SIGSEGV instead of returning 0. It now returns 0, which its callers in cyrius
  (`lib/ws.cyr`, `lib/ws_server.cyr`) already test for.
- **`bayan_toml_array_parse_a` ignored every allocator refusal.** It used `vec_new_a`'s result
  unchecked (a refused vec was loaded through 0 on the first push: SIGSEGV), and
  `_toml_arr_flush_a` ignored a refused element Str and a refused push, so a refusal later in the
  parse silently dropped that element and the caller got a short vec as success. The flush now
  returns -1 on either (including an unescaped element whose first alloc was refused and fell back
  to an empty Str), and `array_parse_a` returns 0 on any refusal — never a partial vec. The
  default-allocator `bayan_toml_array_parse` inherits it.

### Changed

- Toolchain pin **6.6.9 → 6.6.11**. `lib/` re-vendored by `cyrius deps` then `cyrius lib sync
  --full` against the 6.6.11 release: `diff -rq` reports 0 differences (111 files). No source
  change was needed for 6.6.11's new refusals (qualified-enum check, unknown string escapes).
- **CI coverage floor 99 → 100.** cyrius 6.6.11's `cyrius coverage` excludes the entry point
  `main`, which no test can reference and which was the only miss (the two `main`s of
  `src/main.cyr` and `src/test.cyr`). Measured **501/501 (100%)** under the new pin; the floor and
  the pin move in the same commit because a ≤6.6.10 CLI still reads 501/503.
- `dist/` regenerated under the 6.6.11 pin (`--check` green, reproducible). `bayan.cyr`,
  `bayan-base64.cyr` and `bayan-toml.cyr` carry the fixes; the rest change only their version
  header. One sidecar changes: `bayan-pdf.deps` gains `result` (6.6.11's distlib inference,
  compile-verified).

### Tests

- base64: an oversize length returns 0 (SIGSEGV without the fix).
- toml: the `toml_array_parse_a` alias row now runs on the allocator that refuses everything (it
  was an allocation COUNT, because the function could not survive a refusal), plus the canonical on
  the same allocator; a fixture parsed once under a counting allocator, then re-parsed with a
  refusal at each of its 6 allocation points — every one returns 0 (4 of 6 came back as a short vec
  without the flush fix, 1 of 6 without the empty-unescape check); and an allocator that refuses
  ONLY the vec header (SIGSEGV without the `vec_new_a` check); and an 18-element fixture whose vec
  growth (the 17th push) is refused once — it returns 0 (17 of 18 elements came back as success
  without the push check; no smaller fixture ever grows the 16-slot vec, so none reached that arm).
- `tests/bayan.tcyr`: **1,281** assertions (from 1,271), 0 failed; `pdf_flate` 19 and `vectors`
  13 unchanged.

## [1.5.8] — 2026-09-28

Patch release, from cyrius 6.6.10 bite 14. Carries the archive/link changes below (previously
unreleased) and moves the toolchain pin to cyrius **6.6.9**.

### Fixed

- **A stale comment in `src/pdf.cyr`'s FlateDecode loop said `callptr` "is a hard compile error on
  one backend (G13)".** It was cx, and it stopped being true at cyrius v6.5.13, when cx gained
  `callind`. The comment now says why `fncall4` is used (the stdlib's indirect-call helper; kept for
  consistency, not necessity). Comment-only — cyrius folds `dist/bayan.cyr` as `lib/bayan.cyr`, so
  the ~15 repos that vendor it carried the stale claim too.
- **`scripts/consumer-check.sh` failed on the 6.6.9 pin before compiling a single bundle.** Its
  preflight asserts that a consumer including only `lib/syscalls.cyr` emits exactly
  `warning: undefined function 'alloc'`. Through 6.6.8 only that file's cx arm included
  `alloc.cyr`; 6.6.9 made the include unconditional, so the scaffold now builds with no warning and
  the assertion fired, as it should. `HARNESS_EXPECT` is now empty: nothing is subtracted, and every
  warning a bundle build prints counts against that bundle. All 10 bundles compile clean from their
  sidecars, and dropping `str` from a scratch copy of `bayan-toml.deps` still fails the gate. CI never
  showed this: the coverage step, earlier in the same job, was already red (see Tests).

### Changed

- Toolchain pin **6.6.6 → 6.6.9**, verified before the source change: 962 + 19 + 13 + 3 assertions
  green. `lib/` re-vendored by `cyrius deps` then `cyrius lib sync --full`:
  `diff -rq lib ~/.cyrius/versions/6.6.9/lib` reports 0 differences (111 files).
- `dist/` regenerated with `cyrius distlib --all` (reproducible: a second run is byte-identical;
  `--check` green). Seven profile sidecars change because 6.6.9's distlib infers leaves
  differently (compile-verified by distlib itself): `base64`, `bigint`, `csv` gain `str`; `cyml`
  drops `vec`, `pdf` drops `fmt` and `assert`, `toml` drops `string`, `u128` drops `alloc`. The
  base `dist/bayan.deps` is unchanged.

- **The five resolved issues are archived.** `2026-06-23` (thoth, json global
  cursor), both `2026-07-16` (agnosai, json depth cap and yaml tree),
  `2026-08-22` (mneme, toml unescape) and `2026-08-28` (toml structural gaps)
  moved from `docs/development/issues/` to `issues/archived/`. Each was
  already marked resolved; they had never been moved. `issues/` now holds
  only the one open issue (`2026-08-04`, agnosai `obj_get`/`obj_set` key type).
- **Every reference to them follows them**: comments in `src/json.cyr`,
  `src/pdf.cyr`, `src/toml.cyr`, `src/yaml.cyr`, `tests/bayan.tcyr` and
  `scripts/gen-toml-vectors.py`, plus the CHANGELOG, `state.md`, the roadmap
  and ADR-0003. Links between the five are sibling-relative and moved with them.
- **Four CHANGELOG paths to `2026-08-19` were already broken.** That issue was
  archived at 1.5.5 without its references being updated. Fixed now.
  All 80 relative links and `docs/` paths across the Markdown, `src/`, `tests/`
  and `scripts/` now resolve, checked by script.
- `dist/` regenerated for the comment changes. It is byte-for-byte the 1.5.7
  code with eight path strings changed, and still headed `1.5.7` until the next
  version bump.
- The empty `## [Unreleased]` heading that sat below the oldest entry, at the
  bottom of this file, is this one, moved to the top.

### Tests

- **`cyrius coverage --min 100` was red under the 6.6.9 pin: 70% (355/503).** cyrius 6.6.8 made
  the counter match REFERENCES (whole identifiers outside comments and strings) instead of
  substrings. Every back-compat alias in `src/_compat.cyr` is a substring of the `bayan_*` name it
  forwards to, so the old counter credited all 153 while the suite called ten. Three canonicals were
  unreferenced outright: `bayan_pdf_obj`, `bayan_cyml_entry_body` and `bayan_cyml_doc_header`.
- New group `back-compat aliases: every alias forwards to its bayan_* twin (1.5.8)` calls every one
  of the 153 aliases against its canonical twin on the same inputs: scalars compared directly, value
  trees by tag and serialisation, TOML/CYML documents section by section, out-parameters through
  separate buffers, and the JSON tag predicates and accessors over one value of every tag plus the
  null pointer. Each `_a` alias also runs on an allocator that refuses every request (for
  `toml_array_parse_a`, by allocation count instead), so an alias that dropped its allocator and fell
  back to the default one fails. Checked against 16 deliberate mis-forwardings in a scratch copy of
  `_compat.cyr` (wrong twin, swapped arguments, dropped allocator, shifted event id): each was caught.
- Direct tests for the three canonicals, expected values read from their implementations.
  `bayan_cyml_doc_header` and `bayan_cyml_entry_body` return addresses into the caller's buffer and
  are checked as addresses, plus the no-header, fresh-doc and null cases. `bayan_pdf_obj` resolves
  `/Root`'s number to the catalog cell itself; returns 0 for object 0, a negative number, one past
  `/Size` (recording a document error) and a null handle; and on a writer returns 0 for slot 0 and
  for one past the table instead of letting `vec_get` exit the process.
- `tests/bayan.tcyr`: **1,271** assertions (from 962), 0 failed; `pdf_flate` 19 and `vectors` 13
  unchanged. `cyrius coverage`: **501/503 (99%)**, from 355/503 (70%).
- **CI coverage floor 100 → 99.** The two unreferenced functions are the `main` entry points of
  `src/main.cyr` and `src/test.cyr`: the 6.6.8+ tool counts them and no test can reference them
  (`cyrius header` already excludes `main`; `cyrius coverage` does not yet). 1.5.2's 100 was a
  substring-counter figure, so this corrects what the floor measures rather than lowering it to go
  green. It goes back to 100 when the tool excludes `main`; the floor still only ratchets.

## [1.5.7] — 2026-09-23

**The f64 parser is correctly rounded: every input, not "the vast majority".**
prakash reported that about 2 in 10⁵ doubles came back as a neighbouring double
from `bayan_f64_to_json → bayan_f64_from_json`
([issue 2026-09-22](docs/development/issues/archived/2026-09-22-prakash-f64-parse-double-rounding-at-midpoint.md)).
Measured against Python's `float()`, the parser also got 46 of 300,000 Python
`repr` strings wrong, 276 of 300,000 random 1–25-digit decimals, 124 of 200,000
fixed-notation fractions, and 22,529 of 60,000 decimals at or near a rounding
midpoint. It turned up three defect classes the report did not cover. After the
fix: **0 wrong of 884,093**, and 0 with the fast tiers disabled.

Toolchain **6.6.2 → 6.6.6**; `lib/` re-vendored.

> ### ⚠ BEHAVIOUR CHANGE — some decoded floats change bits
>
> `bayan_f64_parse`, `bayan_f64_from_json`, and every JSON and YAML float
> decoded through them now return the correctly rounded double. Where the old
> answer was wrong, the new one differs by **1 ULP** (a near-tie), or goes
> **0 → 5e-324** (`[2⁻¹⁰⁷⁵, 2⁻¹⁰⁷⁴)`), or **DBL_MAX → +Inf** (the exact overflow tie).
> Any stored hash, diff baseline or golden value built from a misdecoded float
> changes.
>
> **prakash:** `tests/hardening.tcyr` pins `1.621274542797433e-9` →
> `0x3E1BDA70DB50D1A0`, the wrong +1 ULP value, precisely so that this release
> would turn it red. Delete it, and delete the `src/serialize.cyr` caveat that a
> float field is not guaranteed to round-trip bit-exactly. It now is.

### Fixed

- **Double rounding at the midpoint (the report).** After Clinger's exact path,
  the parser's DiyFp tier multiplies a 64-bit significand by a cached power of
  ten and then by the residual 10^r, then rounds the 64 approximate bits to 53.
  Two rounded products feed that rounding. It took `low == halfway` as a real
  tie, and a decimal is almost never a binary midpoint. **Fixing only that one
  pattern would not have been enough**, as the report warned. The error bound is
  < 5.01 units of the last bit (derived at `_D_WINDOW`); the measured maximum
  over 200,000 samples is 3.25. Over 389,822 decimals built to sit within a few
  units of a tie, the approximation lands on the wrong side at distance 0 from
  halfway 14,759 times, at distance 1 764 times, and at distance 2 172 times.
  Tier 2 now answers only when its dropped bits are **more than 16 units** from
  halfway, and returns `_D_UNDECIDED` otherwise.
- **An exact third tier decides everything tier 2 does not.** It is Go strconv's
  `decimal` (Nigel Tao's "simple decimal conversion"): the digits themselves in
  an 800-digit buffer, scaled by exact binary shifts, then rounded once. A
  `trunc` flag breaks the one tie the stored digits cannot. It lives on the
  caller's stack (1.6 KB), uses no globals and no tables, and runs for ~0.6% of
  shortest-repr inputs and ~1.8% of arbitrary decimals. Why this and not
  Eisel–Lemire: [ADR-0003](docs/adr/0003-f64-parse-exact-fallback-not-eisel-lemire.md).
- **The 20th+ significant digit was discarded, not accounted for.** The scanner
  keeps 19 digits in a u64 and dropped the rest, so an input just ABOVE a
  midpoint parsed as the midpoint and rounded to even:
  `9007199254740993.0000000000000001` gave 2⁵³ instead of 2⁵³+2. The scanner
  now records that a nonzero digit was dropped. Tier 2 answers only if W and
  W+1 round to the same double, and otherwise tier 3 reads every digit.
- **`[2⁻¹⁰⁷⁵, 2⁻¹⁰⁷⁴)` flushed to 0 instead of rounding up to the smallest
  subnormal.** `_d_diyfp_to_f64` returned 0 whenever the shift reached 64 bits,
  without rounding. That covers `3e-324`, `4.9e-324`, and
  `4.9406564584124654e-324`, which is how C's `printf("%.17g")` writes the
  smallest subnormal. All now give bit pattern 1. The same interval is now
  settled by tier 3.
- **The exact overflow tie decoded to DBL_MAX.** The midpoint between DBL_MAX
  and 2¹⁰²⁴ is a tie, and ties go to even, which is +Inf. The truncated
  significand read it as below the midpoint. So did the full-length ties at the
  subnormal/normal seam and among the subnormals.
- `src/dtoa.cyr`'s header no longer claims round-trip correctness it did not
  have. It now states what is true and where the proof lives.

### Tests

Every new check was run against the **old** parser first, to show it can fail:

- `tests/bayan.tcyr` — **962** assertions (from 919). The report's 27 vectors,
  each checked as the literal string AND through the emitter, plus one or more
  pins per new defect class and two through `bayan_json_v_parse_buf`. **37 of the
  43 are red on the old parser**; the other 6 are boundary controls that
  bracket a defect from the side the old parser got right.
- `tests/fixtures/numeric/f64parse.vec` — **7,736** Python-oracle vectors aimed
  at the hard inputs: every double's midpoint cut to 16–19 digits (rounded down
  and up), full-length exact ties ±1 unit past their last digit, inputs past the
  exact tier's 800-digit buffer, and the underflow, subnormal and overflow seams.
  **The old parser gets 355 wrong.** `f64.vec`'s 328 shortest-repr strings stayed
  green on the old parser throughout: at a 2×10⁻⁵ failure rate, a fixture that
  size had about a 0.7% chance of catching this. Aiming beats volume.
  Generated by `scripts/gen-numeric-vectors.py`, with its own `Random`, so
  `u128.vec` and `f64.vec` still regenerate byte-identically. CI now diffs this
  file on regeneration too. `tests/vectors.tcyr`: **13** asserts (from 10).
- `tests/dtoa.fcyr` (new fuzz harness) — 2×10⁶ `to_json → parse` round-trips
  (uniform finite doubles; |x| ≈ 1e-16..1e16) at the report's seed, plus
  200,000 random decimals checked tier-2-vs-exact, which verifies every tier-2
  answer against an independent algorithm with no Python needed. **The old
  parser fails 31 of the round-trips**, including the report's vector 6. ~8 s.
- **Mutations.** Fourteen, applied one at a time, each run against six scratch
  corpora (Python oracle, 884,093 inputs). All twelve that remove a piece of the
  fix turned a corpus red: window 0 (red on all six), the underflow flush, the
  W-only bound for truncated input, the tie parity, the tie branch, the input
  `trunc` flag, `trunc` through the left and right shifts, the integer-part
  decimal point (`nsig` vs `nd`), the exact tier's carry, and its overflow check
  (red with tier 3 forced on; tier 2 catches that input first otherwise). The two
  shift-`trunc` mutations stayed green until a corpus of EXACTLY-800-digit ±1
  inputs was built, since that is the only input shape that reaches them. The
  other two mutations narrow the window to 2 and to 3, and both stay green on
  every corpus. That matches the measurement (no wrong-side landing beyond
  distance 2), and it is why 16 rests on the derivation, not on a test.
- `tests/bayan.bcyr` — four f64 parse rows, one per tier. Minimum of 7
  interleaved runs, old → new: tier 1 258 → 285 ns, tier 2 414 → 479 ns (both
  within this host's noise), tier 3 **~0.5 → 2.5–4.0 µs** on exactly the inputs
  the old parser answered wrongly.

### Changed — toolchain 6.6.2 → 6.6.6

- `cyrius.cyml` pin **6.6.2 → 6.6.6**. `cyrius deps` refreshed the 9 declared
  leaves; `cyrius lib sync --full` then left `lib/` at **111 files, 0 differ**
  against the snapshot. The snapshot's `lib/` is byte-identical to the 6.6.6
  release tarball's. 40 files changed, plus one new one (`alloc_cx.cyr`). The
  aarch64 syscall peer's `SYS_UNLINKAT` 35 → 263 correction came with it, as
  the roadmap required.
- **`src/pdf.cyr:6126` was the one lint failure**, as the roadmap predicted:
  6.6.5's cyrlint folds case, so "Out of scope for 1.5.0" became an untracked
  deferral (`1.5.0` without a `v` is not a pointer). The comment now points at
  the roadmap's *Out of scope (for v1.0)* → PDF encryption, on the line itself.
- **`dist/bayan-toml.deps` and `dist/bayan-cyml.deps` no longer list `fmt`, and
  that is correct.** 6.6.6 made `lib/io.cyr` self-sufficient: it `include`s
  `fmt.cyr` itself. `consumer-check.sh` stays green from the declared leaves.
  It still goes red when a needed leaf (`io`) is deleted, so the gate is not vacuous.
- `dist/` regenerated with the **release** 6.6.6 toolchain in an isolated
  `CYRIUS_HOME`. The local toolchain produces byte-identical output.
- Re-verified after the bump, per the roadmap's 6.6.6 note: every `.tcyr` file
  individually, and `: Str` handles stored by `bayan_pdf_obj_string_new_a` /
  `_hex_new_a` surviving `to_bytes → obj_parse_buf` intact. Streams are
  covered at document level by the strict-oracle gate: `obj_parse_buf` stops
  at the `stream` keyword by documented design.

### Closed — `tests/pdf_flate.tcyr` is green

1.5.5 recorded it RED (16/19) on every cycc ≥ 6.5.57 and blamed a codegen
defect. The diagnosis was right: `Str = Str` copied the type's two slots over a
one-slot pointer local. The fix shipped in the **released** cyrius 6.6.0
(its CHANGELOG: "A SILENT MISCOMPILE THAT SHIPPED IN v6.5.57"). 1.5.5 had
measured against a pre-release 6.6.0 snapshot, which is exactly what state.md's
local-snapshot caveat warns about. 19/19 on 6.6.2 and on 6.6.6.

## [1.5.6] - 2026-09-12

### Changed

- **Toolchain `6.6.0` → `6.6.2`.** No source change: this repo was already on the
  value form, so the flip cost it nothing. Re-verified on every surface it ships —
  build, tests, and any bench/fuzz/distlib target, including every
  `[lib.<profile>]` bundle.

## [1.5.5] — 2026-09-06

**Migrated to the cyrius 6.6.0 `Result`/`Option`/`Either` VALUE FORM.** A payload
variant is now a REGISTER PAIR (tag in `rax`, payload in `rdx`) that allocates
nothing, so the `tag at +0 / payload at +8` heap box is gone. Toolchain pin
**6.5.36 → 6.6.0**; vendored `lib/` re-synced to the 6.6.0 snapshot.

No public signature changes. `bayan_json_parse_file_r`, `bayan_toml_parse_file_r`,
`bayan_cyml_parse_file_r` and `bayan_pdf_parse_file_r` still return a `Result` —
but a CONSUMER receiving one must now bind both halves, and the shape it used to
read the payload with is gone:

> ### ⚠ CONSUMER ACTION REQUIRED — how you RECEIVE a bayan `Result` changed
>
> ```
> # before (1.5.4 and earlier)                # now (1.5.5, cyrius 6.6.0)
> var r = bayan_toml_parse_file_r(p);         var r_tag, r = bayan_toml_parse_file_r(p);
> if (is_err_result(r) == 1) { ... }          if (is_err_result(r_tag) == 1) { ... }
> var secs = load64(r + 8);                   var secs = r;
> ```
>
> `payload(x)` and `tagged_new(tag, v)` are DELETED upstream with no one-argument
> replacement, and `result_unwrap` / `err_code_of` / `unwrap` / `result_print` take
> `(tag, value)` while `result_unwrap_or` / `unwrap_or` take `(tag, value, fallback)`.
> Passing the call straight into a predicate — `is_err_result(bayan_json_parse_file_r(p))`
> — still reads the tag and is unchanged.
>
> **The dangerous half is the hand-rolled box read.** `load64(r)` for the tag and
> `load64(r + 8)` for the payload do NOT fail to compile: under the value form the
> payload is a plain value, so `load64(r + 8)` dereferences (say) a file descriptor
> as a pointer. Grep for it; the compiler will not.

### Changed

- `bayan_json_parse_file_r` / `bayan_toml_parse_file_r` / `bayan_cyml_parse_file_r`
  bind `file_open_r` / `file_read_r` as a pair (`var fd_r_tag, fd_r = ...`) and read
  the fd and the byte count from the bound payload instead of `load64(fd_r + 8)` /
  `load64(rd_r + 8)`. The error semantics each of these was built for are unchanged:
  a missing file is still `Err(*IoErr)` and an empty file is still a legal empty
  document, which is the one distinction these `_r` variants exist to draw.
- `cyrius.cyml`: `[package].cyrius` **6.5.36 → 6.6.0**; `lib/` re-vendored from the
  6.6.0 snapshot (`cyrius lib sync --full`, 109 files, 0 differ).

### Tests

- `tests/bayan.tcyr` — the six sites that asserted the OLD boxed layout now assert
  the value form, with every assertion intent preserved: the `is_err_result` checks
  read the bound tag, and `vec_len(load64(r + 8))` / `load64(r + 8)` become
  `vec_len(r)` / `r`. One assertion was ADDED, not removed: the cyml empty-file case
  binds a payload it previously discarded, so it now also asserts the empty document
  really has zero entries. **919 assertions, 0 failed.**
- `tests/vectors.tcyr` — 10/10 (12,334 u128 · 328 f64 round-trip · 1,494 TOML string
  vectors against Python).

### Fixed — carried in by the 6.6.0 toolchain

- **The two under-declared sublib `.deps` sidecars are closed.** `bayan-toml`
  and `bayan-cyml` each needed `fmt` (`fmt_int_buf` *and* `fmt_int`) that their
  sidecar did not name, so a consumer following the sidecar got undefined
  functions. The 6.6.0 `distlib` generator closes the transitive set —
  `sidecar: re-added 1 leaf(s) the inference missed (compile-verified)` — and
  both now declare `fmt`. `scripts/consumer-check.sh` reports all **10 bundles
  ok** and its `EXPECTED_FAIL` list is now EMPTY, which is the whole design of
  that list: it fails when a known-bad bundle starts passing, so an exemption
  cannot outlive its bug. Issue archived
  ([2026-08-19](docs/development/issues/archived/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md)).

### Known-bad — NOT from this migration

- ⛔ **`tests/pdf_flate.tcyr` is RED (16/19) on any cycc ≥ 6.5.57**, including 6.6.0.
  Compressed writer output loses `/Type /Page`, `/MediaBox` and `/Resources` from the
  page dictionary, so the file it writes has 0 pages — confirmed independently by
  `scripts/pdfcheck.py`, which is the point of having a strict oracle.
  Bisected on a PRISTINE 1.5.4 tree with only the compiler changing:
  **6.5.56 → 19/19 pass, 6.5.57 → 16/19**. It is a codegen defect, not a bayan one:
  assigning one `Str` to another (`data = z;` at `src/pdf.cyr:8924`) now emits a
  16-byte aggregate copy, but `Str` is a heap-allocated 16-byte HANDLE — a local
  holds one word — so the second word lands on the neighbouring local and smashes
  it. Here it smashes the page dictionary pointer. Minimal repro: two `Str` locals
  with an `i64` guard between them, `s = z;`, and the guard changes value.
  Not worked around in `src/`: contorting source around a codegen bug is how a
  compiler bug becomes a permanent language rule.

## [1.5.4] — 2026-08-28

**The seven structural TOML gaps, closed.** 1.5.3 fixed what a value *decodes
to*; these are about where a pair *lands* — what a key is, whether a table can
be empty, what a duplicate means. They were filed rather than fixed at 1.5.3
([2026-08-28](docs/development/issues/archived/2026-08-28-toml-structural-subset-gaps.md)),
and deferring them was the wrong call: the report was a repair request, not a
survey. Also removes the project's last two fixed read caps, both in `cyml`.

Toolchain unchanged at **cyrius 6.5.36**.

> ### ⚠ BEHAVIOUR CHANGE — `bayan_toml_parse`'s RESULT SHAPE
>
> Four changes move data. All four make it correct; all four can move an index
> or a lookup that worked before.
>
> - **The root table is always `sections[0]`, even empty.** It used to be
>   emitted only if it had pairs, so a file opening with `[a]` made
>   `sections[0]` the section `a` — and a consumer reading `sections[0]` as
>   "the root pairs" silently got `a`'s. If you index sections, re-check.
> - **An empty table is emitted.** `[a]` with nothing under it used to vanish.
> - **A dotted key names a table.** `a.b.c = 1` lands in section `a.b` as key
>   `c`, not in the root as the flat key `a.b.c`. This is what `[a.b]` +
>   `c = 1` has always produced — the two spellings finally agree — but a
>   lookup of `"a.b.c"` in the root now misses.
> - **A duplicate key resolves to the LAST value**, not the first.
>
> **The pair struct is 24 bytes, not 16.** Reading through the accessors is
> unaffected and `bayan_toml_pair_new` keeps its signature; anything that
> allocated a pair by hand, or assumed the size, must be re-checked.

### Fixed — the seven gaps

Every expectation below is Python `tomllib`'s.

- **Quoted keys.** `"key one" = 1` was **dropped entirely**: the key scan
  stopped at the space inside the quotes, the next byte was not `=`, and that
  test has no `else`. `"key" = 2` survived but kept its quotes, so every lookup
  missed. A `"` key is now decoded like a basic string, a `'` key is verbatim.
- **Dotted keys.** `a . b = 1` was dropped for the same reason. `a.b.c = 1`
  stored one flat key, disagreeing with `[a.b]` + `c = 1` for the same data.
  Both now name a table, including quoted segments (`a."b c".d`) and nesting
  under a header (`a.b = 1` inside `[t]` names `t.a`).
- **Inline tables.** `k = { a = 1 }` had no accessor and was not listed as a
  subset limit anywhere a caller reads — so a consumer needing one had to
  hand-roll a splitter, the outcome bayan exists to prevent. Now
  `bayan_toml_inline_parse` / `_a`, `bayan_toml_get_inline` and
  `bayan_toml_is_inline`. As an **array element** the splitter cut on every
  comma inside the braces and returned four syntactic fragments where there
  were two elements; it tracks brace depth now.
- **Empty tables.** A header with no pairs vanished, shifting the index of
  every later `[[array-of-table]]` entry: three `[[s]]` blocks with an empty
  middle one returned **two** sections, so `s[1]` was the third record.
- **Duplicate keys.** Both pairs were stored and the lookup returned the
  **first**, which no other TOML implementation does. The direction is the
  point: `secure = true` then `secure = false` returned `true` for a file whose
  last word is `false`. `bayan_toml_count` is there for a caller that wants the
  spec's "a duplicate is an error" — this parser has no error channel to report
  one through, so the check has to be the caller's.
- **`bayan_toml_is_array` could be fooled by content.** It sniffs the value's
  first byte, by which point the quotes are gone, so `format = '[ $host ]($style)'`
  — an ordinary prompt template — classified as an array. The parser now
  **records the kind** it actually saw.
- **Header names are trimmed and unquoted.** `[ a ]` named the section `" a "`,
  spaces included, so `bayan_toml_get_sections("a")` returned an empty vec —
  silently, which is the worst way to be told.

### Fixed — cyml's last two fixed read caps

Both truncated silently and reported success, the shape 1.5.1 removed from
toml's loader after it lost 1,893 keys from a 300 KB file.

- `bayan_cyml_parse_file_r` stopped at 262,144 bytes and still returned
  `Ok(...)`, with the cut landing mid-line.
- `_cyml_read_file_trimmed` declared `var buf[4096]` and cut a `${file:PATH}`
  expansion at 4,095 bytes — in the one path whose whole job is to substitute a
  file's contents verbatim.

Both slurp into a growing `str_builder` now, and a mid-file read **error** is
no longer folded into clean EOF. An empty file is a legal empty document rather
than `Err(CymlIoErr)`, the same correction toml's loader got at 1.5.3.

There are no fixed read caps left in `src/`.

### Added

- `bayan_toml_pair_kind` and the `TOML_K_*` constants; `bayan_toml_pair_is_array`
  / `_is_inline` / `_is_string`; `bayan_toml_pair_new_kind` / `_a`. A pair built
  by hand reports `TOML_K_UNKNOWN` — a caller supplying only a key and a value
  has not said what form the value took, and a guess would be worse than an
  honest "unknown".
- `bayan_toml_get_pair` (the pair, so the kind is reachable) and
  `bayan_toml_count`.
- `bayan_toml_inline_parse` / `_a`, `bayan_toml_get_inline`,
  `bayan_toml_is_inline`.
- **18 structural oracle vectors** (`P` records) alongside the 1,476 string
  ones. `S` and `A` records can only see what a value decodes to; `P` carries a
  table name and a key and checks **where the pair landed**, which is what all
  of quoted keys, dotted keys and header trimming are about. Total: **1,494**,
  regenerated byte-identically in CI.

  Duplicate keys are deliberately NOT among them: `tomllib` rejects the
  document outright, so there is no oracle answer and last-wins is bayan
  policy. It is pinned by hand instead, where the reasoning sits next to the
  assertion.

### Changed — internals worth knowing about

- **The value dispatch is one function now** (`_toml_parse_value_a`), called by
  both the top-level parser and the inline-table accessor. This module's
  history is a list of two scanners that had to agree and stopped agreeing —
  `_toml_parse_str` / `_toml_str_end`, and the three array quote-trackers, each
  of which cost a release. Copying it into the inline parser would have been
  the third.
- The string parsers gained `_a` twins, so an inline table parsed into an arena
  allocates its decoded values there too.
- A bare value now ends at `,` and `}` as well as at a newline and a comment.
  Nothing bare can contain either — numbers, booleans and dates are made of
  digits, letters and `_ . + - :` — and the same function parses the values
  inside an inline table, where there is no newline to stop at.

### Verification

918 asserts (from 839), 1,494 oracle vectors (from 1,476), 466/466 reference
coverage. `dist/bayan.cyr` is **16,709** lines, up from 16,308 at 1.5.3;
`src/toml.cyr` is 1,632 lines with 33 public functions, up from 1,261 and 21. **Ten mutations, one per gap fix, each confirmed to turn the suite
red** — including two against the structural vectors specifically, to check
that the new `P` records bite rather than merely run.

### On how this release came to be scoped

1.5.3 filed these seven as "wants its own release" without asking. That was a
scoping decision presented as a technical one, and it was wrong twice: the
report was a repair request, and the call belonged to the maintainer. The four
decisions in this release that move data or change a struct — the dotted-key
model, the pair widening, last-wins, and emitting empty tables — were put to
the maintainer before any of them was written.

## [1.5.3] — 2026-08-28

**The TOML parser returned wrong values, and had since 1.0.0.** Reported by
mneme ([2026-08-22](docs/development/issues/archived/2026-08-22-mneme-toml-basic-strings-not-unescaped.md));
the repair grew because measuring the reported defect properly turned up nine
more of the same shape. Toolchain moves to **cyrius 6.5.36**.

> ### ⚠ BEHAVIOUR CHANGE — read this if you consume `bayan_toml_*`
>
> **String values are now decoded per the TOML spec.** They used to be the raw
> bytes between the quotes.
>
> - `"say \"hi\""` was `say \"hi\"`, is now `say "hi"`.
> - `'hello'` (literal string) was `'hello'` — **with its quotes** — and is now
>   `hello`.
> - `"""` bodies keep their trailing newline, which they used to lose.
>
> **If you compensated for any of this in your own code, remove the
> compensation now or you will double-decode.** mneme's `_cfg_toml_unesc` is
> the known case; its `tests/core_config.tcyr` has assertions written to fail
> loudly at this moment rather than corrupt data quietly. `bayan_toml_escape` /
> `bayan_toml_unescape` are now public so the writing half can go too.
>
> **One knock-on:** `bayan_toml_is_array` is a byte heuristic on the stored
> value, and stripping a literal string's quotes exposes what they were hiding.
> `format = '[ $host ]($style)'` classified as a string before and classifies as
> an ARRAY now — the same way `format = "[ $host ]"` always has. If you branch
> on `is_array`, check for this shape. Filed with the structural gaps; fixing it
> means recording the value's kind on the pair.
>
> This is shipped as a patch release because a wrong answer becoming a right
> answer is a bug fix, which is how 1.5.1 shipped `bayan_u256_mul` being wrong
> 46% of the time. The behaviour change is real regardless of the version
> number, hence this banner.

### Why fix 1 and not fix 2

The report offered three shapes and asked for none of them specifically. It had
to be fix 1 — decoding **at parse time** — because a `bayan_toml_unescape` a
caller applies to a returned value cannot work. By then the string kind is
gone: a basic string resolves escapes and a literal string must not, so the
same bytes decode two different ways depending on which quote produced them,
and a `Str` from `bayan_toml_get` no longer records which. Fix 2's helpers ship
too, for callers writing TOML by hand; fix 3's documentation is in the module
header. But only the parser has the information.

### Fixed — string values

Every expected value below is Python `tomllib`'s. Nine of ten string forms
disagreed with it before this release.

- **Basic-string escapes are decoded** — `\b \t \n \f \r \" \\ \uXXXX` and
  TOML's 8-hex `\UXXXXXXXX`, which JSON has no equivalent of. An **unknown**
  escape is preserved verbatim rather than deleted: this parser has no error
  channel, and keeping the bytes beats losing them.
- **Single-line literal strings `'...'` are parsed at all.** There was no such
  branch: a literal string fell through to the "unquoted value, read to end of
  line" arm and came back **wearing its quotes**. `'hello'` was seven bytes
  where the spec says five, and `'C:\tmp'` — the form literal strings exist FOR
  — was wrong twice over. Every literal string bayan has ever parsed carried
  two stray bytes.
- **The multi-line closing-delimiter scan** had two independent bugs, and
  either one alone masks the other:
  - it did not skip a backslash-escaped quote, so `"""he said \"hi\""""`
    stopped one byte early and **dropped a character** (the filed repro 2);
  - it took the FIRST three quotes of a run where TOML says the closer is the
    **last** three, so `"""a""""` lost the `"` and `'''a''''` lost the `'`.

  Mutation testing is what separated them: a test for the reported case passes
  with either fix in place.
- **A trailing newline before the closing delimiter is no longer trimmed.** The
  spec trims the newline *after* the opening delimiter and says nothing about
  the one before the closer, so `"""\nline1\n"""` is `line1\n`. bayan dropped
  that byte from every such value.
- **The line-ending backslash** in a `"""` body now folds the newline and the
  next line's indent, as the spec requires.
- **CRLF** after an opening delimiter is trimmed as a unit, and a raw CRLF
  inside a multi-line body normalises to LF. An **escaped** `\r` is not
  normalised — the author asked for that byte by name.
- **The escaped-quote rule reached all three array scanners.** The value
  capture, the element splitter and the content-end walk each tracked quotes
  without it, so `["a\"b"]` read the escaped quote as closing, the `]` then
  landed "inside a string", and the capture **ran to the end of the document**.

### Fixed — the value arms return the value and nothing else

Found by an adversarial review of the above, in the most ordinary lines a TOML
file contains.

- **An inline comment is no longer part of the value.** `port = 8080 # default`
  yielded the 14-byte string `8080 # default`; a consumer converting that to an
  integer got a different number.
- **CRLF and tabs are trimmed from unquoted values.** The trim removed spaces
  only, so every unquoted value in every file written on Windows carried a
  stray CR — invisible when printed, unequal to the obvious literal.
- **Two more scanners no longer swallow the rest of the document**, the shape
  1.5.1 called the worst one this can take. An unterminated quote inside an
  array value, and a table header with no closing `]`, each ran to EOF and took
  every key below them with it.
- **A backslash-escaped newline** ends a single-line basic string. 1.5.1 closed
  the bare-newline hole and the escaped one stayed open, because the scan
  stepped over "the escaped byte" without looking at it.
- **A line beginning with `=`** produces no pair, instead of a phantom one with
  a zero-length key.
- **`_toml_slurp` no longer folds a read ERROR into clean EOF** — silent
  truncation reported as success, the same shape 1.5.1 removed from the fixed
  256 KiB buffer, arriving by a different route.
- **An empty file is a legal empty document**, not `Err(TomlIoErr)`. It used to
  be indistinguishable from a file that does not exist, which is the one
  distinction that Result variant exists to draw.

### Added

- **`bayan_toml_unescape` / `bayan_toml_escape`** (+ `_a` allocator twins).
  Values from `bayan_toml_get` are already decoded; these are for a consumer
  writing TOML by hand, so mneme's `_cfg_toml_esc` / `_cfg_toml_unesc` can both
  be deleted rather than only the reading half. A round-trip test asserts
  escape → parse returns the original bytes, which is the property mneme needs.
- **`tests/fixtures/toml/strings.vec` — 1,476 vectors from `tomllib`**,
  generated by `scripts/gen-toml-vectors.py` and regenerated byte-identically
  in CI (`tomllib` is stdlib from Python 3.11, so the gate installs nothing —
  the rule the pdf metric-table gate was rewritten to obey).

  This module is exactly why that discipline is worth paying for a third time.
  It shipped wrong from 1.0.0 to 1.5.2 with a green suite, because every TOML
  assertion in that suite had been written by reading bayan's output and
  writing it down. `tomllib` does not care what bayan does.
- **A truncation property test**: eight documents, cut at every length,
  asserting no key, value or section name reaches past its source buffer.

### Fixed — two CI gates that ran and proved less than they claimed

- **`scripts/consumer-check.sh` dropped the first compiler warning.** It matched
  `grep '^warning:'`, and cyrius prints warning #1 concatenated onto the
  `compile <src> -> <out> [arch] ` prefix line. So a bundle whose **only**
  defect was one undefined function was scored `ok`, and every `ok` this gate
  printed meant no more than "no warnings after the first". It had been hiding
  half of the real under-declaration in
  [2026-08-19](docs/development/issues/archived/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md)
  — both `bayan-toml` and `bayan-cyml` are missing `fmt_int_buf` as well as
  `fmt_int`, and that issue's table is corrected accordingly.

  Now matches anywhere, and subtracts a **measured** harness floor
  (`lib/syscalls.cyr` alone emits `undefined function 'alloc'`, which belongs to
  the scaffold, not to any bundle) — asserting that floor is exactly that one
  warning, so the exemption cannot widen silently. Only scaffold warnings are
  subtracted, never a declared leaf's: a leaf's unresolved call is precisely the
  under-declaration this gate exists to catch. Verified by injecting a single
  undefined call into a bundle and watching `ok` become `FAIL`.
- **`.github/workflows/ci.yml` had the same anchor** on its build and test
  warning gates. Same fix. Same family as the `lint`-always-exits-0 and
  `cyrfmt`-reads-only-argv[1] traps already recorded in `state.md`.

### Fixed — documentation that misstated the code

A doc comment that lies is how a consumer ends up hand-rolling a second
implementation, which is the outcome bayan exists to prevent. Each of these was
verified against the code it documents.

- `src/toml.cyr`'s supported-forms list omitted `[section]` headers (supported
  since v6.0.62) and `"""` strings, and it now carries an explicit
  **NOT SUPPORTED** block — quoted keys, dotted keys, inline tables, empty
  tables, duplicate keys, untrimmed header names — all filed together in
  [2026-08-28](docs/development/issues/archived/2026-08-28-toml-structural-subset-gaps.md).
- `bayan_toml_parse_file` was still headed "Reads up to 256KB" eleven lines
  above the block explaining that 1.5.1 removed the cap.
- `bayan_toml_get_sections` now states the cstring key contract that 1.5.1
  wrote onto `bayan_toml_get` and did not carry to its neighbour, which has the
  identical silent-empty-result trap. Same for `bayan_toml_get_array`.
- `bayan_json_parse` now states at the entry point that the flat API captures
  values verbatim and does NOT decode escapes. That contract existed only
  fourteen lines inside the function body, in a historical note.
- `bayan_json_get_int` was documented as returning 0 for a non-numeric value.
  It does not: `str_to_int` skips every non-digit byte, so `"1.5.1"` is 151 and
  `"12abc"` is 12. There is no "not an integer" signal, and the old comment
  invited a sentinel check that never fires.
- `src/cyml.cyr` claimed `bayan_cyml_parse` "can't really fail". True of input,
  not of memory: three unchecked allocations fault under exhaustion. Its 256 KiB
  read cap claimed to match a convention "used elsewhere" that no longer exists,
  and exceeding it truncates silently into an `Ok(...)`. It is also not the
  module's only fixed buffer: `_cyml_read_file_trimmed` cuts a `${file:PATH}`
  expansion at 4,095 bytes, equally silently. The first draft of that comment
  called the 256 KiB one "the last fixed cap in the project" and was refuted by
  a review of this release's own paperwork — in the release whose doc-fix
  section claims each of these "was verified against the code it documents".
- `src/csv.cyr` was billed as an RFC 4180 parser. It is a line-oriented subset:
  a trailing empty field is not emitted (`a,` parses to one field, not two),
  records are LF-terminated where the RFC says CRLF, and CR does not trigger
  quoting.

### Changed

- Cyrius pin **6.5.33 → 6.5.36**; `lib/` re-synced (11 files) and verified
  byte-for-byte against the **released** 6.5.36 tarball, not the local
  snapshot. They agreed this time; that was established by checking.
- `dist/` regenerated with the release toolchain. The full bundle is **16,308**
  lines, up from **15,598** at 1.5.2. (An earlier draft of this line said "was
  14,905" — the 1.5.0 figure, which `state.md` had carried unmeasured through
  two releases. Copying a number is not measuring it.)

### A note on what this release did NOT catch on its own

Three defects in this release's own work were found by adversarially reviewing
it, after the suite, the 1,476 vectors and every CI gate were green. All three
are fixed and guarded; they are recorded because "the tests passed" is exactly
the evidence that was available each time.

1. **A one-byte over-read.** The new escaped-quote rule in the array capture
   shipped without a bound and read past the end of a document ending in
   `a = ["x\`. The guard is now a truncation property test — eight documents cut
   at every length — which fails with three violations when the bound is removed.
2. **The inline-comment rule truncated inline tables.** It broke on `#`
   unconditionally, justified by "a `#` cannot occur inside an unquoted value
   (they are numbers, booleans and dates)". That enumeration omits the inline
   table, which is the one unquoted value carrying arbitrary string bytes:
   `srv = { host = "a#b" }` became `{ host = "a`. The break is now quote-aware.
3. **The array newline rule turned string content into document structure.** It
   fired on a raw newline seen inside a quote, to stop an unterminated quote
   swallowing the file — but the scanner toggles its quote state three times
   across a `"""` delimiter, so it fired on a multi-line element's own first
   newline. The array was truncated to `["""` and the parser resumed inside the
   string body, reading it as TOML: an array element containing the text
   `[boom]` **forged a section named `boom`** and relocated the following root
   key into it. The capture now tracks triple-quoted elements separately.

   This one was strictly worse than the bug the rule was added to fix, and it
   went in as a two-line change with a confident comment.

Ten mutations — one per part of this fix — were each confirmed to turn the
suite red. Two initially did not, and closing those gaps found that the
hand-written test for the *reported* multi-line defect could not actually
detect the bug it was written for.

Six documented numbers were also found to be wrong, all copied forward rather
than measured: the previous bundle size, the fuzz harness's input / parse /
page counts, ganita's version, mneme's PDF-writer line count, the `bin/`
correspondence, and the "last fixed cap in the project" claim. Each is now the
measured value, and the drift is noted where it happened.

## [1.5.2] — 2026-08-21

**Testing gaps closed, and one more defect found by closing them.** Reference
coverage goes from **51% to 100%** — 450 of 450 public functions across all ten
modules — and the CI floor is pinned there. Assertions: **775**, up from 544.

1.5.1's lesson was that a carved module whose tests stayed behind is uncovered,
not covered-elsewhere. This release finishes the job on the modules that were
still thin, and the finish was not a formality: `u128` had 3 of 35 functions
referenced, and testing the rest found a call that kills the process.

### Fixed

- **`bayan_u64_mulmod` took SIGFPE on ordinary inputs, and the two
  architectures disagreed about it.** x86's `DIV` raises `#DE` when the
  **quotient** does not fit in 64 bits — not only when the divisor is zero — so
  a 128-bit product over a small modulus killed the process. Measured:
  `mulmod(0xfdec65fe72129737, 0x93548b905e5c7474, 0x7222d728)`, an unremarkable
  31-bit modulus.

  The precondition (`a < m` and `b < m`) *was* documented, which is why the
  1.5.1 sweep's reviewer refuted a finding here — one counterexample did not
  trap, so the report was dismissed. That was too narrow: **a refuter finding a
  non-triggering case does not clear a finding.** The real defect was underneath
  the precondition anyway — the aarch64 path went through the u128 pipeline and
  returned the right answer for unreduced operands, so code written and tested
  on one target died on the other, with a comment as the only warning.

  Operands are now reduced up front when Cyrius's signed `%` is provably the
  unsigned one (both operands and the modulus below 2^63 — the common case, two
  extra hardware divisions), and anything else takes the wide path that aarch64
  always used. Both targets now compute the same answer for every input, and a
  zero modulus returns 0 instead of faulting. `bayan_u64_powmod` inherits it.
  Mutation-verified: restoring the unguarded fast path makes the vector suite
  die with SIGFPE again.

### Added — oracle-driven arithmetic vectors

`tests/vectors.tcyr` runs **12,334 u128 checks and 656 f64 checks** whose
expected values come from Python — arbitrary-precision integers for the
integer ops, and its shortest-round-trip formatter for floats. That
independence is the whole point: `bayan_u256_mul` shipped for five releases
with 46% of its products wrong because every test compared bayan against bayan.

The u128 vectors deliberately concentrate where fixed-width code breaks: the
2^64 limb boundary from both sides, the sign bit of the low limb, shift counts
of 0 / 63 / 64 / 65 / 128 / 200 (hardware shifts take the count modulo the
width), and unreduced modular operands — which is what surfaced the `mulmod`
fault. Every one of the 12,334 checks passes.

The f64 vectors assert **round-trip** (`to_json` then `parse` returns identical
bits) rather than byte-identical text, because Grisu2 is documented as
shortest-*or-near*-shortest and its output may legitimately differ from
Python's while being just as faithful. They also check that bayan's parser
agrees with Python's formatter, so the parser is verified independently of the
formatter. 328 values including denormals, 1e308, the 2^53 boundary, and 300
random bit patterns.

Vectors are regenerated by `scripts/gen-numeric-vectors.py`, and CI now
requires that regeneration to be byte-identical — otherwise "independent
oracle" decays into whatever was checked in once.

### Added — the rest of the coverage

Every module reached 100%: `u128` 3/35 → 35/35, `toml` 6/17 → 17/17, `json`
40/69 → 69/69, `pdf` 63/115 → 115/115, `cyml` 10/17 → 17/17, `dtoa` 2/3 → 3/3,
`base64` 2/4 → 4/4, and `bigint`, `yaml`, `csv` completed.

Two of the newly-covered functions are worth naming, because both exist to fix
earlier bugs and neither had ever been tested:

- **`bayan_json_v_obj_get_by_str`** — added in 1.4.1 as the fix for
  `obj_get` taking a cstring while callers held a `Str`, which made `strlen`
  walk the 16-byte header and return a silent not-found.
- **`bayan_yaml_frontmatter_split_a`** — given its missing allocation check in
  1.5.1. It is now tested against a deliberately exhausted arena.

New fixtures: `tests/fixtures/toml/sample.toml` and
`tests/fixtures/cyml/sample.cyml`, both structure-checked against Python's
`tomllib` where applicable. The file-loader tests generate documents larger
than the caps 1.5.1 removed (352 KB of TOML, 26 KB of JSON) and assert that
every key survives, so those fixes cannot regress quietly.

### Changed — CI

- **The reference-coverage floor moves from 30 to 100.** Adding a public
  function without a test now turns the build red. That is the pressure this
  project turned out to need.
- Numeric vector regeneration is gated.

### Note on what reference coverage is

100% means every public function is *called* by a test. It does not mean every
function is *correct* — that is what the oracle vectors and the mutation-
verified regression guards are for. The number is a floor, and the CHANGELOG
for 1.5.1 is a list of what passing a lower floor failed to catch.

## [1.5.1] — 2026-08-21

**P-1 security and hardening sweep.** Every module audited under five lenses
(bounds, overflow, termination, byte accounting, silent wrong answers), each
finding handed to a separate reviewer instructed to **refute** it, and each
survivor fixed only after a reproducer measured it. Twenty defects confirmed
and repaired, plus four found by hand while writing the first tests three
modules had ever had.

No API changed. Two behaviours are deliberately stricter and are called out
below, because a caller relying on the old leniency will see a refusal where it
previously got a plausible wrong answer — which is the point.

### The context that made this necessary

Eight of bayan's ten modules were carved byte-identical out of cyrius's stdlib
at 1.0.0. Their tests stayed behind, and `cyrius coverage` reported
`csv 0/3`, `cyml 0/17`, `bigint 0/20` — three modules referenced by no test in
bayan's own suite, on the assumption their coverage still lived upstream. It
did not: bayan has owned that code since the carve, and `lib/csv.cyr` no longer
ships in cyrius at all. **Writing csv's first test found two heap buffer
overflows within the hour.**

The general form, now recorded in `state.md`: a carved module whose tests
stayed behind is not "covered elsewhere", it is uncovered.

### Fixed — memory safety

- **`csv`: two heap buffer overflows (CWE-787).** `bayan_csv_parse_line` gave
  each field a fixed `alloc(1024)` and wrote one byte per input byte with no
  bound — a 4,000-byte field wrote **2,976 bytes past the end**, content and
  length both attacker-controlled. `bayan_csv_write_line` did the same with a
  fixed `alloc(4096)` — **5,912 stray bytes** from a 10 KB row. Both now
  measure before allocating. Mutation-verified: restoring either fixed size
  makes the new regression test report those exact counts.
- **`base64`: a one-byte remote crash.** `bayan_base64_decode("=", 1)` computed
  `out_len = -1`, `alloc(0)` returned 0, and the unconditional terminator wrote
  through address `0xFFFFFFFFFFFFFFFF`. Verified SIGSEGV. Length and alphabet
  are both validated now; non-base64 bytes used to decode as `0xFF` filler.
- **`yaml`: an unchecked allocation.** `bayan_yaml_frontmatter_split_a` wrote
  through the result of `alloc_via` without checking it — an exhausted caller
  arena took SIGSEGV. Every other allocating entry in the module already
  checked.
- **`cyml`: an out-of-bounds read.** `bayan_cyml_doc_entry` was bare pointer
  arithmetic with no bounds check and no null check; a negative index read
  *before* the entry array and returned a garbage pointer the caller then
  dereferenced. Found by the module's first-ever test.

### Fixed — a remote memory-exhaustion DoS

- **`json` allocated the whole remaining document for every string.** The
  decode buffer was sized `len - pos + 1`, where `len` is the document length,
  so heap use was quadratic in input size and nothing is ever freed on a bump
  allocator. Measured: 40 KB of input took **200 MB**; 1 MB took **125 GB of
  heap / 46 GB RSS**. Both parsers shared the helper, so the **streaming**
  parser — whose documented purpose is bounded memory for multi-MB input — was
  the most quadratic path in the module. Now pre-scans for the closing quote
  and sizes from the string's own span: 40 KB of input takes 742 KB, and the
  heap-per-byte ratio is flat instead of growing.

### Fixed — wrong answers

- **`bigint`: `bayan_u256_mul` dropped carries.** The three-term inner sum
  detected overflow with a single comparison, missing the case where
  `lo + carry` wrapped on its own. **220 of 400 random 256-bit products were
  wrong**, and 53 of 100 `mulmod` results under Curve25519's p = 2^255-19.
  Single-limb inputs were all correct, which is exactly why the existing tests
  never saw it. Now verified against 201 vectors from Python's
  arbitrary-precision integers; mutation-verified at 120/201 wrong when the old
  logic is restored.
- **`bigint`: `bayan_u256_mod` reduced by repeated subtraction.** It spun
  **forever** on `p == 0` and needed up to 2^256 iterations for a small p
  (measured: 2.06e7 iterations/second, so `a mod 1` on a 256-bit `a` would not
  finish this century). Replaced with binary long division — 256 steps for any
  input — and `p == 0` now returns `-1`.
- **`json`: the flat parser ignored `\"` escapes, which let a value hide a
  key.** For the valid document `{"note":"hi\"there","admin":"false"}` the
  value ended at the escaped quote and the parser resynchronised mid-value,
  producing `[note]=[hi\]` and `[,]=[false]` — with `admin` gone. A caller
  checking a permission got a silent "not found" reachable through any string
  field.
- **`toml`: an unterminated string swallowed the following lines.** The scan
  ran to the end of the *document* looking for a closing quote, so
  `a = "oops` absorbed the next two lines and silently deleted their keys —
  `admin` and `b` simply absent from a config parse. A basic string may not
  contain a newline, so the newline now terminates it.
- **`json` and `toml` file loaders truncated and reported success.** Fixed
  16 KiB and 256 KiB read buffers, with the cut landing mid-token: a
  52 KB / 2,001-key JSON object parsed to **630 pairs**, and a 300 KB /
  15,000-key TOML file to **13,107** with `is_err_result() == 0`. Both now read
  through a growing builder — no cap remains.
- **`cyml`: `bayan_cyml_expand_value` discarded everything around the
  reference.** `"v${file:VERSION}-beta"` returned `"1.5.0"`, dropping 16 of 21
  bytes; `"https://${env:HOST}/api"` returned the host alone. It now
  substitutes in place and handles multiple references. Expanded text is
  deliberately not re-scanned, so a file containing `${...}` cannot drive an
  expansion loop.
- **`cyml`: a leading blank line hid the first entry.** `_cyml_is_entries`
  tested only for a marker at byte 0 when `pos == 0` and returned, so the
  marker at byte 1 was unreachable — one entry silently folded into the file
  header.
- **`cyml`: the entry scan capped at 256 and truncated silently.** 300
  `[[entries]]` blocks parsed as 256, with 44 gone and no diagnostic. The scan
  is now two-pass (count, allocate exactly, fill), which also retires the fixed
  stack array whose mis-sizing was an out-of-bounds stack write in
  CHANGELOG [6.0.79].
- **`bigint`: `bayan_u256_from_hex` accepted anything.** It truncated
  over-length input to its first 64 characters and treated every non-hex byte
  as a zero digit, so `"hello world"` parsed to a number and `"12-34"` to
  `0x12034`. Both now refuse.
- **`json`: malformed numbers parsed.** A lone `-` became the integer 0
  (`[-,-]` serialised back as `[0,0]`), as did `1.` and `1e`. And `_jp_atoi`
  wrapped silently, so `9223372036854775808` came back as
  `-9223372036854775808` — a value whose **sign** differs from the document's.
  Digits are now required in every position and the i64 range is enforced.
- **`json`: a JSON-pointer index wrapped mod 2^64.** Against a 3-element array,
  `/1` followed by 64 zeros selected element 0. An out-of-range pointer now
  resolves to nothing.
- **`json`: a scalar constructor's OOM was silent.** The parse returned 0 with
  `err_msg` empty, indistinguishable from a parse failure — measured on a real
  arena, 9 of 31 failing capacities reported no error at all.

### Fixed — portability

- **`cyml` used raw x86_64 syscall numbers** (`syscall(2, …)` open,
  `syscall(0, …)` read, `syscall(3, …)` close) for `${file:}` and `${env:}`
  expansion. On another target those numbers are different calls: on agnos the
  "open" returned the process's own pid, the `fd < 0` guard did not fire
  because a pid is positive, and the following "read" **terminated the
  process** (exit status 102 = pid mod 256). Now uses `lib/io.cyr`'s portable
  wrappers, which bayan already depends on.

### Changed — deliberately stricter

Two inputs that used to produce a value now produce a refusal. Both were
divergences rather than mere leniency:

- **`yaml` rejects duplicate mapping keys.** `obj_set` appends, so
  `role: admin` / `role: guest` built a two-entry object where
  `bayan_json_v_obj_get` returned the **first** while the serialiser emitted
  `{"role":"admin","role":"guest"}` and every downstream JSON reader took the
  **last**. Two components reading one document disagreed about a role. YAML
  1.2 makes duplicates an error.
- **`yaml` no longer types an out-of-range integer as an int.**
  `uid: 18446744073709551616` used to become the integer `0`. It now falls
  through to a string, which is what an unrepresentable scalar is. (This one
  came free with the json number fix — yaml delegates to json's scanner.)

### Added — tests for three modules that had none

`csv`, `bigint` and `cyml` had zero references in bayan's own suite. They now
have full groups, alongside a regression guard for every defect above. The
suite is **525 asserts + 19 in `pdf_flate.tcyr`**, up from 452.

### Also

- `scripts/check-widths.py` — verifies the standard-14 font metric tables using
  only the Python stdlib, so the CI gate no longer depends on groff being
  installed. `scripts/gen-widths.py` now discovers groff's font directory
  instead of hardcoding a version path, and fails with an actionable message
  rather than a traceback. This fixed a CI failure introduced in 1.5.0.
- `bayan_toml_get`'s doc comment claimed the key could be a cstring **or** a
  `Str`; it compares with `str_eq_cstr`, so a `Str` yields a silent "not found"
  — the 1.4.1 trap. Comment corrected, and the asymmetry with
  `bayan_json_get` (which takes a `Str`) recorded as a known gap, since
  reconciling them is a breaking change rather than a patch.

## [1.5.0] — 2026-08-21

**PDF read/write — `bayan_pdf_*`.** The roadmap's P2 item lands: a PDF writer
and a PDF reader with text extraction, as `src/pdf.cyr` (9,348 lines, 152
public functions). Its one known consumer, **mneme**, has shipped a hand-rolled
writer since its port; that hand-roll is superseded here, and the defects found
while reading it are what this module is shaped around.

Also in this release: the Cyrius pin moves `6.5.28` → `6.5.33`.

### Added — the writer

- `bayan_pdf_new()` → document, `bayan_pdf_add_page`, the standard-14 fonts,
  text and graphics operators, `/Info` metadata, `bayan_pdf_to_bytes`, and
  `bayan_pdf_write_file`.
- **Every byte offset in the cross-reference table is MEASURED, never
  predicted.** The offset for an object is read off the output builder
  immediately before that object is appended, and `_pdfw_selfcheck` then
  re-reads every recorded offset and confirms it lands on `<n> 0 obj` before
  `to_bytes` returns. mneme predicts offsets from `var offset = 9;` — the
  length of `"%PDF-1.4\n"` — which is correct only until a second header line
  exists. bayan emits the conventional binary-comment line, so the predicted
  constant would have been wrong for every object in the file.
- **Object numbers come from a counter, not closed-form arithmetic.** mneme's
  `4+2p` / `5+2p` scheme is correct today and must be re-derived the moment
  anything — `/Info`, a second font, an `/ID` — is added.
- **Real AFM font metrics.** The standard-14 width tables are derived from
  Adobe's original AFM data (via groff's `afmtodit`-generated metrics) by
  `scripts/gen-widths.py`, which self-verifies against 22 documented spot
  widths, a whole-family monospace check, and a decode round-trip.
- **`/Encoding /WinAnsiEncoding` is declared, and text is transcoded to match.**
  mneme declares no encoding, so viewers fall back to StandardEncoding, where
  only 54 of the 128 high codes exist: `Résumé` renders `RÃ©sumÃ©` and an
  em-dash disappears entirely. Declaring the encoding without transcoding would
  merely change the flavour of mojibake, so bayan does both.
- **A newline inside show-text is rejected**, not silently deleted. A newline
  means "break the run"; accepting and dropping it is a silent content change.
- **`bayan_pdf_write_file` propagates the write failure.** mneme ignores
  `file_write_all`'s return and reports success on a full disk.

### Added — metric text measurement

- `bayan_pdf_text_width` and `bayan_pdf_wrap` lay text out by **measured
  advance width**. mneme wraps at 80 characters, but in a proportional face 80
  characters spans a **4.26× range** — 80 `l` is 195 pt (43% of a 451 pt
  column) while 80 `W` is 831 pt (184%, running 308 pt off a 595 pt page).
  Verified on the release fixture: the widest wrapped line measures 450.2 pt in
  a 451 pt column, and no line overflows.
- WinAnsi transcoding both ways (`bayan_pdf_winansi`, `bayan_pdf_from_winansi`),
  with a strict mode that refuses an unrepresentable codepoint and a substitute
  mode that emits `?`.

### Added — the reader

- `bayan_pdf_parse*` → an object graph, plus `bayan_pdf_extract_text`.
- Classic cross-reference **tables** and PDF-1.5 cross-reference **streams**,
  `/Prev` chains, objects stored inside **object streams**, and PNG **and**
  TIFF predictors.
- Filters: `FlateDecode` (through the hook below), `ASCIIHexDecode`,
  `ASCII85Decode`, `RunLengthDecode`. An unrecognised filter is an error, not a
  pass-through — returning still-encoded bytes as "text" is a silent wrong
  answer.
- **Inherited page attributes** (`/Resources`, `/MediaBox`, `/CropBox`,
  `/Rotate`) are honoured. A reader that consults only the `/Page` dict reports
  a missing `/MediaBox` on a large fraction of real files.
- **Text decoding follows the font**, not a fixed encoding: `/ToUnicode` CMaps
  (`beginbfchar`, `beginbfrange` in both forms, surrogate pairs, ligature
  destinations), `/Type0` composite fonts consuming two-byte codes,
  `/Encoding /Differences` by Adobe glyph name, and the WinAnsi / MacRoman /
  Standard base encodings. Parsed maps are cached per font.

  This is what makes the reader work on modern files. `glm/manual.pdf` uses
  `/Type0` `/Identity-H`; decoding it a byte at a time yields
  `* / 0        0 D Q X D O` where the page reads `GLM 0.9.9 Manual`.
- **`/Encrypt` is detected and rejected** before any string or stream is
  touched. Encryption is out of scope for 1.5.0, and a half-handled encrypted
  file presents ciphertext as text.
- Bounded on five independent axes — object nesting, indirect-reference chains,
  xref `/Prev` sections, page-tree depth, and total inflated bytes — each with
  its own counter and its own message, so a refusal names the bound it hit.

### Added — compression, without a sankoch dependency

`FlateDecode` / `FlateEncode` is reached through consumer-installed function
pointers, `bayan_pdf_set_inflate(&zlib_decompress)` and
`bayan_pdf_set_deflate(&zlib_compress)`. bayan folds INTO cyrius's stdlib, so a
hard `include "lib/sankoch.cyr"` would create a module-ordering hazard in that
fold for a filter many consumers never touch. With no hook installed the writer
emits valid uncompressed output and the reader reports a specific error naming
the missing hook — both paths are tested, the hook-absent one in
`tests/bayan.tcyr` and the hook-present one in `tests/pdf_flate.tcyr`.

`[deps].stdlib` is unchanged and `[lib.pdf]` is a **single-module closure** —
pdf carries its own object graph and its own decimal number emitter, so neither
`json.cyr` nor `dtoa.cyr` rides along.

### Design notes worth keeping

- **No floating point anywhere in the module.** Geometry is integer
  milli-points (1 pt = 1000 mpt) and a PDF real is captured losslessly as
  `(scaled, places)`, so parse and emit are exact inverses and `0.50`
  round-trips as `0.50` rather than normalising to `0.5`. `bayan_f64_to_json`
  is unusable here: it emits exponent notation and the token `null`, both
  invalid PDF number syntax, and both of which compile clean.
- **A separate `bayan_pdf_obj_*` tree rather than reusing `bayan_json_v_*`.**
  PDF has name, indirect-reference, and stream types with no JSON analogue, and
  `JTAG_STR` is documented as decoded UTF-8 while PDF strings are raw bytes.
- **Ten subsystem helper prefixes, never a bare `_pdf_`.** mneme defines 14
  bare `_pdf_*` helpers and will have both files in scope during its migration;
  a duplicate function name in cyrius is only a *warning*, with
  last-definition-wins that rebinds even textually-earlier call sites.

### Added — the acceptance oracle

`scripts/pdfcheck.py` is a strict, stdlib-only PDF validator, and it is the
gate CI runs the writer's output through. It is deliberately stricter than
poppler and mupdf, which reconstruct a broken cross-reference by scanning for
`N 0 obj` and thereby hide exactly the byte-accounting bugs it exists to catch:
every offset is checked against the byte it claims to point at. It was itself
mutation-tested — a corrupted xref offset, a `/Length` off by one, and a stale
`/Size` must each be caught — and that exercise found two bugs in the oracle
before it was trusted: a `\s*endstream` match that let an off-by-one `/Length`
slide through, and a tuple/int comparison that crashed on any PDF-1.5 file.

`scripts/gen-pdf-fixtures.py` generates the checked-in fixtures — the `ref-*`
ones must parse and the `bad-*` ones must be refused, and CI asserts BOTH
directions. A validator that quietly goes lenient passes every happy-path check
ever written; the polarity assertion is the only step that would notice.

**Font metrics are verified without needing groff.** `scripts/gen-widths.py`
*derives* the tables from groff's afmtodit-generated Adobe metrics, so it needs
groff installed — the wrong dependency for a gate, and it broke CI on the first
run for exactly that reason: a hardcoded `/usr/share/groff/<version>/` path
that existed only on the authoring machine. Two changes:

- the generator now **discovers** groff's font directory across the usual
  roots instead of pinning a version, and fails with an actionable message
  rather than a `FileNotFoundError` traceback;
- `scripts/check-widths.py` is new and is what CI actually gates on. It decodes
  the tables straight out of `src/pdf.cyr` and checks them against documented
  Adobe Core-14 widths and Python's own `cp1252` codec — no groff, no network,
  stdlib only. The byte-for-byte regeneration diff still runs, but only where
  groff is present, and is skipped rather than failed when it is not: groff's
  absence says nothing about whether the tables are right.

The checker is mutation-tested — corrupting a width, filling one of the five
undefined CP1252 codes, truncating a table, and breaking the WinAnsi block are
each caught. It also found its own first bug on contact with real data: it
applied the undefined-codes rule to Symbol and ZapfDingbats, which are symbolic
faces carrying their own built-in encodings where those codes are real glyphs.

### Fixed before release — an adversarial review of the new module

`src/pdf.cyr` was reviewed under five lenses (bounds, overflow, termination,
byte accounting, silent wrong answers) with every finding handed to a separate
agent instructed to **refute** it. Eighteen candidate defects; ten survived
refutation with a reproducer, and all ten are fixed here. Recording them
because "the parser passed its tests" and "the parser is safe on hostile input"
are different claims, and only the first was true before this pass.

- **A near-i64-max `/Length` segfaulted the reader.** The reach check was
  `start + n > len`. The number lexer admits values up to 9223372036854775799
  (its range guard runs *before* the multiply-accumulate), so `start + n`
  wrapped to a large **negative** i64 — neither `n < 0` nor `> len` — the guard
  passed, and `load8(buf + e)` then read about 9.2 exabytes below the buffer.
  Reproduced as a SIGSEGV from a 428-byte file, with the wrapped value visible
  in the backtrace. Now compared by subtraction (`n > len - start`), which
  cannot overflow because `start <= len` always holds.
  **Mutation-verified**: restoring the additive form makes the new
  `bad-huge-length.pdf` fixture crash the process again.
- **The object-stream memo was keyed on the document pointer alone.**
  `alloc_reset()` rewinds the bump allocator and a `PdfDoc` is the first thing a
  parse allocates, so document *addresses* are recycled and a second document
  could be handed a freed record whose vec and Str words now held unrelated
  bytes. Documents now carry a monotonic generation stamp that the key includes.
  The decompression budget already defended against exactly this recycling; the
  memo had been given the same rationale in a comment but not the same guard.
- **`/XRefStm` chains bypassed `_PDF_MAX_XREF`.** The hybrid-reference path
  recurses `_pdfx_read_table` → `_pdfx_read_section` → `_pdfx_read_table`
  without passing through the `/Prev` loop that holds the counter, so one of
  the two chains was bounded and the other exhausted the native stack. Now
  bounded on the shared visited-set length, which covers both chains.
- **Indirect `/Length` chains recursed without bound.** Every
  `_pdfp_resolve_d` call site passes a literal depth of 0 and its visited set
  is per-call, so neither survived the trip back through `_pdfp_stream_a`;
  `k 0 obj<</Length k+1 0 R>>` repeated N times recursed N deep. Bounded by a
  per-document re-entry counter.
- **The page-tree walk was exponential.** `_PDF_MAX_TREE` caps *depth* and the
  cycle set is *path*-scoped — correct for a node that reaches itself, useless
  for a node reached down many distinct paths. Thirty `/Pages` nodes each
  listing the same kid twice is 2^30 visits at depth 30: inside every existing
  bound and indistinguishable from a hang. Now carries a total-work budget.
- **The cross-reference table grew by exact request.** `_pdfx_alloc_table` is
  called once per subsection and nothing is freed, so a table of N one-entry
  subsections allocated O(N²) bytes — tens of gigabytes from a 1 MB file.
  Growth is now geometric, with the allocated capacity tracked separately from
  the logical `/Size` so a resolve still cannot reach past what the trailer
  declares.
- **`/ToUnicode` `bfrange` had no cumulative work budget.** Each entry may span
  65,536 codes and the outer loop admitted 65,536 entries, so a ~2 KB
  compressed CMap could drive ~4e9 map writes.
- **The writer's depth cap never fired through a stream.** `_pdfw_obj` forwarded
  `depth` on every composite arm except `PTAG_STREAM`, which hard-coded it, so
  a stream whose own dictionary referenced the stream recursed until the stack
  died. Now forwarded like every other arm.
- **`bayan_pdf_raw_op`'s comment described behaviour the code did not have** —
  it claimed a `q` inside a literal string was not matched, when delimiters
  make `(a q b)` tokenise as `a`, `q`, `b` and be refused. The refusal is the
  safe direction and is kept deliberately; the comment now says so, rather than
  a string-aware lexer being added inside a safety check.

Two reviewer findings were **refuted** and deliberately not changed: the writer
does not leak partial output on a failed content operator (the failure fires
before anything is appended), and the shared empty `Str` is not a dangling
pointer.

### Changed (toolchain)

- **Cyrius pin `6.5.28` → `6.5.33`**, with `cyrius lib sync --full`. `lib/`
  matches the **release tarball** exactly — 0 of 108 files differ — verified by
  comparing the trees rather than trusting the sync's exit code, and against
  the released tarball rather than `~/.cyrius`, which on a machine that also
  develops cyrius can carry unreleased in-flight edits at the same version
  number. (This time the local snapshot and the release agreed.)

## [1.4.2] — 2026-08-19

Toolchain + CI release. No behavioural change: the compiled smoke binary is
**byte-identical** (sha256 `9c5e4c3d…`) before and after every source edit
below. What did change is that the project now *checks* considerably more of
itself, and two of the new checks immediately found something.

### Changed (toolchain)

- **Cyrius pin `6.5.16` → `6.5.28`**, with `cyrius lib sync --full` run against
  it. `lib/` matches the pinned snapshot **exactly — 0 of 108 files differ**,
  confirmed by comparing the trees rather than trusting the sync's exit code
  (see the 1.4.0 note on why: that time `--full` exited 0 and still left five
  files stale). Build and test now emit neither the shadow-lib nor the
  pin-drift warning.
- **`lib/` grew 99 → 108 files.** The 6.5.28 snapshot adds `unicode/` (7 files —
  `_decode` / `categories` / `casefold` / `normalize` plus their generated data
  tables), `async_macos.cyr`, and `thread_macos.cyr`; 48 existing modules were
  refreshed, six of which bayan had been shadowing at older versions
  (`sakshi` 2.4.7, `sigil` 3.12.2, `sandhi` 1.9.8, `vani` 1.1.2,
  `sankoch` 2.7.6, and bayan's own fold at 1.3.0).
- **The `6.5.4` → `6.5.16` step was never recorded.** 1.4.0 shipped on `6.5.4`;
  commit `97a3476` ("lang bump", 2026-08-10) moved the pin to `6.5.16` with no
  CHANGELOG entry and no `state.md` refresh. Noting it here so the history is
  contiguous: the span this release actually crosses is `6.5.4` → `6.5.28`.

### Fixed

- **`src/toml.cyr` no longer builds with warnings.** `_toml_parse_str` and
  `_toml_parse_multiline_q` both return a `Str` (`str_new` / `str_from`) but
  were declared `: i64`, so every assignment into the `Str`-typed `value` drew
  an `assigning non-pointer to typed pointer` warning — three of them, at 257 /
  261 / 266, present since the multiline parser was parameterized. Annotating
  the two helpers (and the `_toml_parse_multiline` back-compat wrapper) `: Str`
  clears all three. **Diagnostic only, and proven so**: the compiled binary is
  byte-for-byte identical to the pre-annotation build. Same shape as the 1.4.1
  `cstring` annotation, and both helpers are file-private with call sites only
  inside `toml.cyr`.
- **Lint is clean across all 12 `src/` files** (was 1 warning + 1 untracked
  deferral). The >120-char `cyml_split` forwarding shim in `_compat.cyr` is
  wrapped; the `\uXXXX` in `json.cyr`'s doc comment — read by the deferral
  scanner as an `XXX` marker — carries `#skip-lint: \u-escape notation, not a
  deferral`, matching how `lib/sigil.cyr` handles the identical false positive.
- **`tests/bayan.tcyr` is canonically formatted.** 21 continuation lines sat at
  column 0; `cyrius fmt` indents them to 2. Whitespace only — still 292 asserts,
  still green. It had gone unnoticed because `cyrius audit` scopes fmt to `src`.

### Added — CI now confirms the whole project

`.github/workflows/ci.yml` went from 4 steps (install / deps / build / test) to
a full gate. The new checks, and why each one is a gate rather than a printout:

| Gate | Notes |
|---|---|
| Toolchain pin resolves with no drift | every gate below is worthless if it measured the wrong compiler |
| Version consistent across `VERSION` / manifest / CHANGELOG / all 9 dist headers | |
| `lib/` matches the pinned snapshot exactly | the tree diff, per the standing 1.4.0 rule |
| Format — `src/` **and** `tests/` | `cyrius audit` only covers `src/`; the drift above was in `tests/` |
| Lint — zero warnings, zero untracked deferrals | `cyrius lint` always exits 0, so the gate reads its report, not `$?` |
| Include-dependency audit (`cyrius vet`) | fails on any untrusted / missing dep |
| Build — **zero compiler warnings** | `cyrius build` only *warns* on bad pointer typing, lib/ shadowing and pin drift; `--strict` does not cover them, so the warning text is the gate |
| Smoke exits 42 | |
| Test | |
| Fuzz · bench harness · `cyrius coverage --min 30` | a floor that ratchets up, never down |
| **Distribution ×3** | see below |

`release.yml` gains a CHANGELOG-entry check alongside the existing tag/VERSION
check, and both workflows lost the `|| true` that let a half-finished toolchain
install pass as success.

**Both workflows now install via the upstream installer** rather than
untarring a release by hand:

```sh
curl -sSf .../cyrius/main/scripts/install.sh | CYRIUS_VERSION="$pin" sh
```

The hand-rolled step (inherited from the original scaffold, and still present
in ganita) laid the toolchain down at `~/.cyrius/{bin,lib}` as real
directories. 6.5.28's `cyrius deps` requires the snapshot at
`~/.cyrius/versions/<pin>/lib` specifically and errors with *"pins version
6.5.28 but it is not installed"* — CI's first red. The installer creates
`versions/<pin>/{bin,lib}` and symlinks `~/.cyrius/{bin,lib}` at them, which is
what every path-sensitive command expects; the `lib/`-vs-snapshot gate compares
against `versions/<pin>/lib` for the same reason. The pipe carries
`set -eo pipefail` — without it a failed download pipes empty input to `sh`,
`sh` exits 0, and the install silently no-ops.


**The three distribution gates**, since `dist/` is what bayan actually ships:

1. `cyrius distlib --all --check` — the bundles are regenerable from `src/`.
2. Regenerating leaves no tree diff — the *committed* bundles are what a fresh
   regeneration produces, sidecars included.
3. `scripts/consumer-check.sh` (new) — every bundle compiles for a downstream
   repo that supplies **only** the leaves its `.deps` sidecar declares.

Gate 3 has to build with `cyrius build --no-deps`. Without it, `cyrius build`
auto-prepends everything in bayan's own `[deps].stdlib`, so a consumer missing
a declared leaf still compiles and the check passes vacuously — verified by
deleting leaves from a sidecar one at a time and watching all eight still
report clean.

### Found by the new gates

- **Two sublib sidecars under-declare their dependencies.** With `--no-deps` in
  place, `bayan-toml` fails on `memcpy` / `memeq` / `fmt_int_buf` / `fmt_int`
  and `bayan-cyml` on `fmt_int`. `cyrius distlib` generates each sidecar from
  the leaves *bayan's* code touches and does not close over the stdlib's own —
  `lib/str.cyr` calls memcpy/memeq/fmt_int with no include lines at all,
  `lib/result.cyr` calls fmt_int, `lib/io.cyr` calls memcpy. Verified minimal
  fix: `bayan-toml` needs `+string +fmt`, `bayan-cyml` needs `+fmt`. The
  compiler reports these as *warnings*, so a consumer following the sidecar
  gets a green build and a broken binary. Filed as
  [2026-08-19](docs/development/issues/archived/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md)
  — the sidecars are generated, so bayan cannot fix it in-repo. The two are
  carried in the script's `EXPECTED_FAIL` list, which **fails if either starts
  passing**, so the exemption cannot outlive the bug.
- **`dist/` must be generated by the PINNED toolchain, and briefly wasn't.**
  The first cut of this release regenerated `dist/` with a local `cyrius` that
  self-reports `6.5.28` but is actually a **`.29`-in-flight build** — it carries
  the two 2026-08-18 distlib profile-sidecar fixes
  (`distlib-named-profile-sidecar-from-sit`,
  `distlib-profile-sidecar-empty-under-auto-prepend`). Those emit `syscalls`
  into the `bayan-cyml` / `bayan-json` / `bayan-toml` / `bayan-yaml` sidecars
  and write an empty `dist/bayan-u128.deps`. **Released 6.5.28 emits neither**,
  so `distlib --all --check` on CI reported four bundles STALE — sidecar bytes
  count toward staleness, not just the `.cyr`. Reproduced locally by installing
  the release tarball into an isolated `CYRIUS_HOME`, which returned CI's output
  line for line, down to the absent `u128` sidecar. `dist/` is regenerated with
  released 6.5.28 and `dist/bayan-u128.deps` removed; both come back on the
  re-pin to `.29`. **Verify against the release tarball, not `~/.cyrius`, whenever
  the toolchain repo is mid-flight.**

### Verified on 6.5.28

| Gate | Result |
|---|---|
| `cyrius build src/main.cyr` | OK, **0 warnings**; smoke exits 42 |
| `cyrius test` / `cyrius tests` | **292 passed, 0 failed** (+ 1/1 `[build].test`) |
| `cyrius fmt --check` (src + tests) | clean |
| `cyrius lint` (12 files) | 0 warnings, 0 untracked deferrals |
| `cyrius vet src/main.cyr` | 20 deps, 0 untrusted, 0 missing |
| `cyrius distlib --all --check` | 9 bundles current (deterministic over 6 runs) |
| `scripts/consumer-check.sh` | 7/9 clean, 2 known-under-declared |
| `cyrius fuzz` · `cyrius bench` | 1/1 · 1/1 |
| `cyrius coverage` | 102/335 fns (30%) reference coverage |

### Known, not fixed here

Surfaced by the state review and recorded in
[`state.md`](docs/development/state.md) — each is its own change:

- `tests/bayan.fcyr` and `tests/bayan.bcyr` are still `cyrius init` scaffolds.
  The fuzz harness feeds a 4-byte literal into a body that returns immediately;
  the bench measures a no-op. Both report PASS — a false green on two v1.0
  criteria, and the CI gates that run them are correspondingly vacuous.
- `bigint` (0/20), `cyml` (0/17) and `csv` (0/3) are referenced by no test in
  bayan's own suite; their coverage still lives upstream in cyrius.
- `lib/bayan.cyr` is bayan's own fold vendored back into bayan's own `lib/` by
  `lib sync --full`. Inert (nothing includes it) but it defines the same symbols
  as `src/` — the hazard the ten dead pre-carve modules were removed for at
  1.4.0, and not durably fixable in-repo since `--full` re-adds it.
- `README.md` still says "Status **1.0.0** — Seven modules"; `docs/adr/` holds
  no ADRs; roadmap M1/M2 are unfilled template stubs; `CLAUDE.md` Project
  Identity and Goal are still `TODO`.

## [1.4.1] — 2026-08-05

### Fixed — `json_v_obj_get` takes a C-string while `json_v_obj_set` stores a `Str`

The object API is asymmetric and always has been: `bayan_json_v_obj_set` writes `key`
straight into the pair as a `Str`, while `bayan_json_v_obj_get` does `strlen(key)`.
Cyrius is i64-everywhere, so both spellings compile and the symmetric-looking pair is
memory-unsafe.

The failure is worse than a crash. Passing a `Str` to the getter makes `strlen` walk the
16-byte header and terminate a few bytes in on the data pointer's zero high bytes, so it
yields a junk length, the compare misses, and the lookup returns 0 — **"not found", a
silent wrong answer.** The SIGSEGV reporters saw comes later and elsewhere, from
`bayan_json_v_str(0)` → `str_len(0)`.

Three changes, none of which touch a call site:

- `bayan_json_v_obj_get(v, key: cstring)` — the annotation arms cyrius's existing
  Str→cstring diagnostic, which was inert only because the parameter was untyped. It
  fires at every call site passing a `Str`-typed local, at any argument position, and is
  **diagnostic only**: the compiled output is byte-identical.
- `json_v_obj_get` in `_compat.cyr` gets the same annotation, so the ~40 consumers using
  the short spelling are covered too.
- `bayan_json_v_obj_get_by_str(v, key: Str)` — the symmetric spelling, additive.
  ⚠ Deliberately NOT `..._obj_get_str`: a trailing `_str` is a reserved cyrius overload
  slot, and claiming it would silently reroute `obj_get` calls with a literal key.
- `obj_set`'s doc comment now states that the key is stored as a `Str` — the getter's
  side already said "C-string key" and had done since 2026-06-10; the setter's half was
  the one actually missing.

**Not done, deliberately:** renaming the getter to `_cstr` and giving the bare name a
`: Str`. ~115 call sites across ~16 repos pass a non-literal cstr and would break
silently, and each break is worse than the current defect (`str_len` on a raw cstr is
arbitrary garbage). That is a cross-repo migration, not a patch.

## [1.4.0] — 2026-07-31

### Added

- **The allocator-threaded (`_a`) JSON value surface is complete.** Six new
  entry points close the three gaps that made an arena cover only part of a
  request:

  | New | Signature | Was reachable through an arena before? |
  |---|---|---|
  | `bayan_json_v_obj_set_a` | `(a, obj, key, val) → 0 / -1` | no — pair cells went to the global bump |
  | `bayan_json_v_build_a` | `(a, v) → Str / 0` | no |
  | `bayan_json_v_build_pretty_a` | `(a, v, indent) → Str / 0` | no |
  | `bayan_json_v_parse_ctx_a` | `(a, ps, buf, len) → json_v* / 0` | no |
  | `bayan_json_v_parse_buf_a` | `(a, buf, len) → json_v* / 0` | no |
  | `bayan_json_v_parse_a` | `(a, src: Str) → json_v* / 0` | no |

  The eight value **constructors** have had `_a` forms since v5.8.36. What was
  missing was everything around them: you could allocate each cell of a tree
  through an arena and still leak the pair cells, the parse, and the serialized
  output onto the no-free global bump. That measures as "the arena works" right
  up until someone checks `alloc_used()`.

  Pinned by a test that fails when the threading is removed — verified by
  mutation, not assumed. Reverting a single `alloc_via(a, …)` to `alloc(…)` in
  the string parser turns the zero-growth assertion into `got 35200, expected 0`.

  | 200 × parse → obj_set → build | global bump growth |
  |---|---|
  | non-`_a` path | **> 100 KB** |
  | `_a` path through an arena | **0 bytes** |

### Fixed

- **The string parser never checked its allocation.** `_jp_parse_string` called
  `alloc(cap + 4)` and wrote through the result unconditionally. On the global
  bump that is near-unreachable (`alloc` returns 0 only for `size <= 0` or
  `> ALLOC_MAX`, and a failed chunk mmap exits inside `alloc_init`), so it never
  bit. Through an arena it is ordinary — a small arena runs dry — and the
  unchecked write would have gone to address 0. `_jp_parse_string_a` checks, and
  reports it as a normal `"out of memory in string"` parse error. `_jp_parse_array_a`
  and `_jp_parse_object_a` do the same for their container constructors.

### Changed

- **`_jb_walk`, `_jb_append_string` and `_jb_emit_indent` now have one body, not
  two.** Each is implemented as its `_a` form and the original name is a wrapper.
  The wrappers preserve the **abort**-on-OOM contract of the non-`_a`
  `str_builder` verbs they used to call directly, because turning an abort into a
  silently truncated JSON string would be a worse failure than the crash it
  replaced. The `_a` forms return `-1` instead, which is the contract an arena
  caller needs — the same split `bayan_json_v_arr_push_a` already used.
- **`_jb_emit_indent_a` emits its newline and spaces via `str_builder_add_cstr_a`**
  rather than `str_builder_add_byte`, which has no `_a` form. Both literals are
  one byte, so pretty output is byte-identical; this only moves the growth onto
  `a` and makes the failure reportable. No cyrius-side change was needed.

### Changed (toolchain)

- **Cyrius pin `6.4.68` → `6.5.4`**, with `cyrius lib sync --full` run against it.
  `lib/` now matches the pinned snapshot exactly — 0 of 99 files differ, and the
  build no longer emits a drift or shadow warning.

  `lib sync --full` alone did not achieve that: it copied 99 files and left five
  behind (`niyama` 1.0.5, `pam`, `shadow`, `vani` 1.1.1, `yantra` 1.0.0), all dated
  from the 2026-07-16 sync and none in bayan's `[deps] stdlib` list. They were
  refreshed from the snapshot directly. **A green `lib sync --full` is not proof
  that `lib/` matches the pin — compare the trees.**

### Removed

- **Ten dead pre-carve modules deleted from `lib/`** (109 → 99): `json`, `base64`,
  `bigint`, `csv`, `cyml`, `toml`, `u128`, `matrix`, `linalg`, `agnosys`. The first
  seven are content that was carved *out* of the cyrius stdlib *into bayan* at 1.0.0
  / cyrius 6.1.25 — so bayan was vendoring a stale copy of its own API, defining the
  same symbols as `src/`. Nothing included them, but a single `include` would have
  silently shadowed the real implementations under last-definition-wins. `matrix` and
  `linalg` moved to ganita at 6.1.26; `agnosys` is unrelated to this package. None was
  referenced by `src/`, `tests/`, or `cyrius.cyml`.
- The six `# Usage: include "lib/<mod>.cyr"` header lines that still advertised those
  removed paths now name `lib/bayan.cyr` (full bundle) or `lib/bayan-<profile>.cyr`
  (sublib).

### Notes

- **The parser state layout is unchanged at 48 bytes.** Putting the allocator in
  `ps` would have been tidier — every `_jp_*` already takes `ps` — but callers
  are documented to declare their own `var ps[48]`, so widening the struct would
  have silently overflowed their buffers. The allocator is an explicit first
  parameter instead, which is also what keeps the parse reentrant: a file-scope
  "current allocator" global would have undone the v1.0.3 thread-safety work.
- **`_a` is a naming convention, not a Cyrius dispatch suffix.** Unlike `_str`
  and `_ptr` (which the compiler routes to automatically — see the `1.3.0`
  `_str` → `_buf` entry), `_a` carries no overload behaviour, so these names
  cannot collide with the dispatch rules.
- The **serializer recursion is still uncapped**, matching every prior release.
  Both *parsers* cap at `_JP_MAX_DEPTH` (128); the serializer only ever walks a
  tree the caller built, so it is not an untrusted-input path. Do not build
  unbounded-depth values from user data.

## [1.3.0] — 2026-07-28

### Breaking

- **The cstr+len parse entries are renamed `_str` → `_buf`.** The old names were
  actively breaking their own Str-taking siblings (see Fixed below), so they
  could not be kept as aliases — the name *is* the defect.

  | Removed | Replacement | Signature |
  |---|---|---|
  | `bayan_json_v_parse_str` | `bayan_json_v_parse_buf` | `(buf, len)` |
  | `bayan_yaml_parse_str` | `bayan_yaml_parse_buf` | `(buf, len)` |
  | `json_v_parse_str` (alias) | `json_v_parse_buf` (alias) | `(buf, len)` |

  Migration is mechanical: `s/_parse_str(/_parse_buf(/`. Stale calls do **not**
  fail silently — the removed name is an undefined function, so the build
  refuses to emit a binary. Callers already passing a `Str` should prefer the
  bare `bayan_json_v_parse(src)` / `bayan_yaml_parse(src)`, which now work.

  `bayan_json_stream_parse_str`, `bayan_json_v_parse_ctx_str` and
  `bayan_yaml_parse_ctx_str` are **unchanged** — those genuinely take a `Str`
  first argument, which is what the `_str` suffix is supposed to mean.

### Fixed

- **`bayan_json_v_parse(src)`, `bayan_yaml_parse(src)` and the `json_v_parse`
  alias returned 0 for every input, including valid documents.** Cyrius routes a
  call `X(a, …)` to `X_str` whenever `a` is `Str`-typed at the call site and an
  `X_str` exists — the same overload dispatch that routes `&IDENT` to `_ptr`.
  Because the cstr+len forms were named `bayan_json_v_parse_str` /
  `bayan_yaml_parse_str`, every `bayan_json_v_parse(someStr)` in the ecosystem
  was rewritten by the compiler into a **1-argument call to a 2-argument
  function**: `len` bound garbage and the parse failed. The only outward sign was
  a `'bayan_json_v_parse_str' expects 2 arguments, got 1` warning, easily lost in
  build output. Renaming the cstr+len forms to `_buf` vacates the `X_str` slot
  and the dispatch has nothing to hijack.

  In Cyrius `X_str` means "the `Str`-taking variant of `X`", so a cstr+len form
  may never occupy that name. Both renamed functions now carry a comment saying
  so, to stop this recurring.

  Discovered while porting agnosai's `core/message.rs`, where
  `bayan_json_v_parse` silently failed to round-trip a message.

### Added

- **Regression coverage for the bare `Str` entries** (`tests/bayan.tcyr`, +11
  assertions, 263 → 274). `bayan_json_v_parse`, `bayan_yaml_parse` and
  `json_v_parse` had **no test calling them at all** — the suite only ever
  exercised the cstr+len forms, which is why a total failure of the public Str
  API went unnoticed. The new group asserts each returns a real tree, that the
  `Str` and `_buf` entries produce identical output, and that a null source is
  still rejected cleanly.

## [1.2.1] — 2026-07-20

### Changed

- **f64 JSON is now round-trip-correct** (`src/dtoa.cyr`, new). Replaced the
  6-decimal `fmt_float_buf(v, 6)` formatter — which lost ~9 mantissa bits on
  values like `1/3`, flushed `|x| < 5e-7` to `0`, and emitted the **non-JSON**
  token `-.00000-` for `Inf`/`NaN`/`|x| >= 2^63` — with a **Grisu2** (Loitsch)
  formatter: integer-only, always-succeeds, output guaranteed to round-trip.
  Non-finite values now serialize as `null` (serde_json / JS convention).
- **Parser is now correctly rounded + DoS-safe.** `_jp_atof` (bayan's JSON number
  parser) is replaced by a Clinger-fast-path + normalized-DiyFp `strtod`
  (`bayan_f64_from_json` / `bayan_f64_parse`) that agrees with a reference
  `strtod` on every tested input — killing the old 1-ULP divergence against
  `math f64_parse`. Its exponent scan **saturates**: the old O(exponent-VALUE)
  apply loop turned a 17-byte `{"x":1e100000000}` into ~237 ms of wasted CPU (an
  algorithmic-complexity DoS); it is now O(len).
- Validated **bit-exact across the entire double range** (all powers of two,
  subnormals, boundaries, 5000+ randoms) for both format→parse round-trip and
  reference-`strtod` parse agreement. +16 tests in `tests/bayan.tcyr`.

## [1.2.0] — 2026-07-16

### Added

- **Per-format sublibs** (the sigil/sandhi `[lib.<name>]` pattern) —
  `cyrius distlib <name>` → `dist/bayan-<name>.cyr` (+ `.deps` stdlib-leaf
  sidecar) for json / yaml / toml / cyml / csv / base64 / u128 / bigint, so
  a consumer that wants one parser doesn't pull the whole bundle as it
  grows. Each is the compile-verified self-contained closure of its
  format's entry points; the 7 carved modules have no cross-deps, so most
  closures are one module — yaml's carries `json.cyr` (shared value tree,
  parser state, number scanner; 2,458 lines vs the full bundle's ~4,750).
  Sublibs expose canonical `bayan_*` names only: `_compat.cyr` aliases
  reference every `bayan_*` symbol and ride only the full `dist/bayan.cyr`.

- **yaml: new module — YAML subset parser into the shared tagged value tree**
  (`src/yaml.cyr`). `bayan_yaml_parse` / `_parse_str` / `_parse_ctx` /
  `_parse_ctx_str` parse a pragmatic YAML subset into the SAME
  `JTAG_*`-tagged `bayan_json_v_*` node graph the JSON value parser produces,
  so one consumer traverses one node shape across both formats (the
  serde-data-model property the Rust originals have). Filed by **agnosai**
  (definition files) and driven equally by **mneme** (Markdown frontmatter) —
  see `docs/development/issues/archived/2026-07-16-agnosai-yaml-parse-into-tagged-value-tree.md`.
  In the subset: block mappings (plain/quoted keys) nested by indentation,
  block sequences (incl. compact `- key: value` items and sequences at the
  parent key's indent), single-line flow sequences, `#` comments
  (quote-aware; mid-word quotes like `O'Brien` are literal), scalars typed as
  null/`~`/bool, strict-JSON-grammar numbers (via the json module's scanner;
  `01`/`1e` fall back to strings), and verbatim quoted strings (one layer
  stripped, no `\`-escape decoding — the toml convention). One leading `---`
  and one `...` marker; leading UTF-8 BOM skipped. **Everything out of
  subset fails loudly** — anchors/aliases/tags (value AND key position),
  block scalars, flow mappings (incl. implicit `[a: b]` entries), multi-doc
  streams, content on marker lines, tabs in indentation, empty flow elements,
  malformed/unterminated quotes — never a silent mis-parse. Reentrant from
  day one (shares the json per-call parser state; errors via
  `bayan_yaml_state_error*` or the `bayan_yaml_last_error*` mirror) and
  depth-capped from day one (shared 128 cap, block + flow). Strings share
  the source buffer (no copy). Hardened by a 36-agent adversarial review
  pass pre-release (6 parser bugs found and fixed, all pinned by tests).
- **yaml: Markdown frontmatter split.** `bayan_yaml_frontmatter_split(src)`
  (+ `_a` variant) splits `---` -fenced YAML frontmatter from a Markdown
  body (`...` also closes; CRLF tolerated; no/unclosed fence → `{0, whole
  input}`, mirroring mneme's interim parser). Accessors
  `bayan_yaml_fm_yaml` / `bayan_yaml_fm_body`.
- `tests/bayan.tcyr` — yaml group: scalar typing, quoting, comments,
  nesting, block/flow sequences, compact items, markers, frontmatter,
  reentrancy, err_pos, depth caps (block + flow), and a loud-rejection
  battery for every out-of-subset form; suite 101 → 249 asserts.

## [1.1.1] — 2026-07-16

### Changed

- **Toolchain: cyrius pin bumped 6.4.10 → 6.4.64.** `cyrius lib sync --full`
  re-synced the vendored `lib/` snapshot (99 files — sakshi/niyama/sigil/
  sandhi/yukti/patra/vani/mabda/sankoch had drifted behind their pins). Full
  suite green on 6.4.64: 86/86 asserts + full-bundle compile smoke.

### Fixed

- **json: parsers now cap recursion depth at 128 (serde_json parity).** Neither
  the value parser (`_jp_parse_value`) nor the streaming parser
  (`_js_parse_value`) bounded its descent, so a deeply nested document
  (`[[[[…` — 2 bytes per level) recursed once per level until the calling
  thread's stack was exhausted — an untrusted-input DoS, and a **parity
  regression** vs the Rust originals, which inherit serde_json's default
  128-level limit. The per-call parser state grew one slot
  (`_JP_STATE_SIZE` 40 → 48, `depth@+40`, zeroed in `_jp_state_init`); both
  descents increment it on entering an array/object branch, decrement on exit,
  and past 128 (`_JP_MAX_DEPTH`) fail through the existing per-call error path
  with `"nesting too deep"` — exactly like any other parse error (value path:
  `bayan_json_state_error()` / mirrored `bayan_json_last_error()`; stream
  path: `JS_EV_ERROR` + the same mirror). 128 open containers still parse;
  the 129th fails. `bayan_json_parse_state_size()` already reports the state
  size, so callers reserving via it are transparent; the documented stack
  pattern is now `var ps[48]`. Reported by agnosai (untrusted HTTP bodies on
  its server surface — blocker #2). See
  `docs/development/issues/archived/2026-07-16-agnosai-json-no-recursion-depth-cap.md`.
  Covered by a new `tests/bayan.tcyr` group (200-deep rejected on both
  parsers, 100-deep parses, exact 128/129 boundary, legacy-entry mirror,
  `_compat` alias parity); suite 86 → 101 asserts.

## [1.1.0] — 2026-07-06

### Added

- **toml: array VALUE element access.** `bayan_toml_parse` has always captured
  an array value (`key = [a, b, c]`) verbatim as one raw bracketed `Str` but
  gave callers no way to reach its elements short of hand-rolling a comma
  splitter. Four new helpers decompose that raw value on demand:
  `bayan_toml_array_parse` (and its allocator-threading `_a` variant) returns a
  vec of top-level element `Str`s; `bayan_toml_is_array` reports whether a value
  is a `[...]` array; `bayan_toml_get_array` is the `get` + `parse` convenience
  (returns `0` for an absent key, else a possibly-empty vec). Elements are
  whitespace-trimmed; a single layer of matching quotes (`"` basic / `'`
  literal) is stripped with the body captured verbatim (no `\`-escape decoding,
  matching the scalar string parser); nested-array elements are returned whole
  for recursive re-parsing; trailing commas yield no phantom element; and `#`
  comments (leading full-line or trailing inline, outside strings) are skipped.
  Element `Str`s share the value's buffer (no copy), like the rest of the
  parser. Legacy `toml_*` aliases added in `_compat.cyr`.

### Fixed

- **toml: array-value capture is now quote-aware for `'…'` and skips `#`
  comments.** The multi-line array-capture scanner in `bayan_toml_parse` only
  tracked `"` basic-string state and had no comment handling, so a literal
  string element containing `]` (e.g. `key = ['a]', 'b']`) closed the outer
  bracket early and truncated the captured value, and a `]` inside a `#` comment
  line of a multi-line array did the same. The scanner now tracks whichever
  quote char opened the string (`"` or `'`) and skips `#`-to-end-of-line
  comments, so both forms round-trip intact. Exercised by the new
  `tests/bayan.tcyr` array group.

## [1.0.4] — 2026-07-03

### Fixed

- **toml: `"""…"""` multi-line strings are no longer silently dropped.** The
  TOML value parser only recognized `'''` (triple **single**-quote) as a
  multi-line delimiter; a `"""` (triple **double**-quote) value fell through to
  the single-line `"…"` branch, where the opening `"` immediately closed against
  the second `"` and the entire body was parsed as an empty string — no error,
  just silent data loss. This broke every consumer whose TOML used `"""`,
  notably takumi building zugot recipes: 436 of 563 recipes use `"""` for their
  `make`/`configure`/`install` build steps, so those steps parsed empty and
  takumi produced zero-payload `.ark` packages with no diagnostic. Fixed by
  parameterizing the multi-line parser/end-finder by delimiter char
  (`_toml_parse_multiline_q` / `_toml_multiline_end_q`, `q` = 34 `"` or 39 `'`)
  and adding a `"""` branch to the value dispatch **before** the single-line
  `"` case. Both triple forms are captured **verbatim** (bayan does not expand
  `\`-escapes anywhere; a `\` at a line end is preserved, so shell build steps
  with backslash line-continuations round-trip intact). The original `'''`
  entry points are kept as thin back-compat wrappers. Covered by a new
  `tests/bayan.tcyr` group (verbatim `"""`, `'''` regression, dispatch
  ordering, embedded quotes, empty `""`) plus an adversarial edge-probe pass
  (EOF/no-close bounds, 4-/6-quote counts, mixed delimiters, real zugot
  recipes) — all green.

## [1.0.3] — 2026-06-23

### Fixed

- **json: value + streaming parsers are now reentrant (thread-safe).** The
  recursive-descent value parser (`bayan_json_v_parse*`) and the event-streaming
  parser (`bayan_json_stream_parse*`) kept their lexer cursor in three process
  globals (`_jp_buf` / `_jp_len` / `_jp_pos`) plus shared error slots, so two
  concurrent parses clobbered each other's cursor mid-descent — wrong/garbage
  value trees or out-of-bounds loads. Replaced the global cursor with a per-call
  40-byte parser-state struct (`{buf, len, pos, err_msg, err_pos}`) threaded as
  the first argument through every parser helper. `bayan_json_v_parse_str` /
  `bayan_json_v_parse` / `bayan_json_stream_parse` keep their signatures and now
  stack-allocate their own state (so existing single-threaded callers are
  unchanged **and** concurrent), mirroring the per-call error into the legacy
  `bayan_json_last_error()` slots only as a back-compat courtesy. Node allocation
  is unchanged — the filed race was the cursor, not the node arena. Reported by
  thoth (parallel MCP tool-result parsing). See
  `docs/development/issues/archived/2026-06-23-thoth-json-value-parser-global-cursor-not-thread-safe.md`.

### Added

- **Reentrant parse API.** `bayan_json_v_parse_ctx(ps, buf, len)` and
  `bayan_json_v_parse_ctx_str(ps, src)` parse into a caller-owned state buffer
  and touch no module globals — the path concurrent consumers use.
  `bayan_json_state_error(ps)` / `bayan_json_state_error_pos(ps)` read the error
  from that state; `bayan_json_parse_state_size()` returns the bytes to reserve
  (stack `var ps[40]` or heap).
- `tests/bayan.tcyr` — JSON value-parser group (nested object/array, ctx path,
  per-call error reporting, trailing-content rejection) and streaming-parser
  group (real `&fn` callbacks asserting per-event dispatch through the reentrant
  `_js_*` path: object/array/key/string/int/float/bool/null/error counts, the
  error mirror, and the `_parse_str` convenience entry); suite 8 → 48 asserts.

### Changed

- `cyrius` pin bumped 6.2.1 → 6.2.37 (closes the manifest/toolchain drift). No
  unrelated source changes; `.tcyr` suite green on 6.2.37.

## [1.0.2] — 2026-06-19

### Fixed

- **u128: aarch64 portability (SIGILL).** `bayan_u128_divmod` and
  `bayan_u64_mulmod` carried unguarded x86 `div`/`mul` inline asm — the raw x86
  machine-code bytes emitted verbatim into the text section on non-x86 targets and
  trapped (SIGILL) on aarch64. Guarded both x86 fast paths with
  `#ifdef CYRIUS_ARCH_X86`: `divmod` falls through to its existing portable
  shift-subtract loop, and `mulmod` gains a `#ifdef CYRIUS_ARCH_AARCH64` path that
  computes the 128-bit product + remainder via the u128 pipeline
  (`bayan_u128_mul` + `bayan_u128_mod`). x86 is byte-identical (the asm path is
  unchanged). Surfaced by cyrius's VR-01 full-tcyr-on-arm64 gate.

## [1.0.1] — 2026-06-12

### Changed

- `cyrius` pin bumped 6.1.24 → 6.2.1 (ecosystem-wide stdlib pin sweep onto the
  current toolchain). No source changes — bayan's `[deps]` carries no carved-out
  modules. Verified green on 6.2.1: `cyrius deps` resolves cleanly, `.tcyr` suite
  8/8, bench 1/1, `dist/bayan.cyr` regenerated via `cyrius distlib`.

## [1.0.0] — 2026-06-10

**Initial carve out of the Cyrius stdlib** (cyrius v6.1.25, first half of
Phase E — the bayan/ganita data/math split). bayan becomes the upstream
source of truth for the data-format & big-integer modules; cyrius folds
`dist/bayan.cyr` byte-identical into `lib/bayan.cyr` (sandhi pattern).

### Added
- **Seven modules carved from cyrius stdlib** (`json`, `toml`, `cyml`,
  `csv`, `base64`, `bigint`, `u128`) — ~3,350 lines, 149 public functions,
  zero cross-module dependencies. Rename-only transform: every public
  function gained the `bayan_` prefix (`json_parse` → `bayan_json_parse`,
  `u256_add` → `bayan_u256_add`, …); internal helpers (`_jp_*` / `_jv_*` /
  `_add64` / …) unchanged.
- **`src/_compat.cyr` back-compat alias module** — 149 forwarding shims
  exporting the legacy cyrius-stdlib names so downstream consumers build
  unchanged during the migration window. Deprecated; removed once the
  ecosystem re-pins.
- **`[lib]` distlib config** — `cyrius distlib` bundles the 7 modules +
  aliases into `dist/bayan.cyr` (3,500 lines), includes stripped, for the
  stdlib fold.
- Smoke entry (`src/main.cyr`, exits 42) + `tests/bayan.tcyr` (canonical
  API + alias parity). Deep coverage lives in cyrius's
  `json`/`toml`/`csv`/`base64`/`bigint`/`u128`/`cyml` `.tcyr` suite.
