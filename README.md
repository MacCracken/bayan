# bayan

> **Data-format, document and big-integer distfile for the AGNOS-lineage
> Cyrius ecosystem** — `json`, `yaml`, `toml`, `cyml`, `csv`, `base64`,
> `pdf`, `bigint` (u256) and `u128`. Carved out of the Cyrius stdlib so
> bare-metal / firmware consumers don't drag data-format code into kernel
> objects. Foldable into stdlib byte-identical per the sandhi pattern.

**bayan** (Arabic بيان — *statement, exposition, clear data*) is the home
for the data-domain modules that don't belong in the primitives-only
stdlib floor. Written in [Cyrius](https://github.com/MacCracken/cyrius).

## Status

**1.5.4** — ten modules, 16,750 lines of `src/`, 348 public functions.
Zero cross-module dependencies except `yaml`, which parses into `json`'s
value tree by design. Folded into `cyrius/lib/bayan.cyr`.

> ⚠ **1.5.3 and 1.5.4 both change TOML behaviour.** 1.5.3 decodes string
> values per the spec (they used to be the raw bytes between the quotes, and a
> literal string came back wearing its quotes) — **if your code compensated for
> that, remove the compensation or you will double-decode**. 1.5.4 changes the
> shape of `bayan_toml_parse`'s result: the root table is always `sections[0]`,
> empty tables are emitted, a dotted key names a table, a duplicate key
> resolves to the LAST value, and the pair struct is 24 bytes rather than 16.
> Both banners are in the [CHANGELOG](CHANGELOG.md).

Current version, surface area, dependency gaps and in-flight work live in
[`docs/development/state.md`](docs/development/state.md); this file stays
short on purpose.

## Modules

| Module | Public prefix | Surface |
|--------|---------------|---------|
| `pdf`    | `bayan_pdf_*`    | PDF writer + reader: pages, standard-14 fonts with real AFM metrics, text and graphics operators, metric word wrap, xref tables **and** 1.5 xref streams, object streams, text extraction |
| `json`   | `bayan_json_*`   | parser + tagged value tree + builder + streaming + JSON-pointer |
| `yaml`   | `bayan_yaml_*`   | pragmatic YAML subset into json's value tree, plus frontmatter split |
| `toml_tree` | `bayan_toml_v_*` | TOML 1.0.0 into json's value tree, strict: it accepts and refuses what Python's `tomllib` does (1.11.0) |
| `toml`   | `bayan_toml_*`   | tables + key/value parse, quoted and dotted keys, inline tables, spec-correct string decoding (basic, literal, both multi-line forms), escape/unescape helpers, array-value access, per-value kind |
| `cyml`   | `bayan_cyml_*`   | Cyrius config (entries/docs, env expansion) |
| `csv`    | `bayan_csv_*`    | line parse / escape / write |
| `base64` | `bayan_base64_*` | standard + URL alphabet, encode/decode |
| `bigint` | `bayan_u256_*`   | 256-bit unsigned int (add/sub/mul/mod, modular arithmetic, hex) |
| `u128`   | `bayan_u128_*`   | 128-bit unsigned int (full arithmetic + bitwise + divmod) |
| `markdown` | `bayan_markdown_*` | CommonMark 0.31.2 to a node tree and HTML, with GFM's tables, task lists, strikethrough and autolinks, and wiki links, behind flags (1.9.0) |
| `dtoa`   | `bayan_f64_*`    | f64 ⇄ decimal: Grisu2 out, correctly rounded parse in (1.5.7; the stdlib's `f64_parse_n` behind bayan's lenient NaN / Inf front from 1.5.14), used by `json` |

### Per-format sublibs

`cyrius distlib <name>` emits `dist/bayan-<name>.cyr` — the self-contained
closure of one format's entry points, for consumers that want one parser
without the full bundle's footprint. Each ships a `.deps` sidecar listing
the stdlib leaves it needs. `bayan-pdf` is a single-module closure: it
carries its own object graph and number emitter, so neither `json` nor
`dtoa` rides along. `bayan-yaml` and `bayan-toml-tree` carry `json`, the
tree they parse into; `bayan-toml` is the flat TOML parser alone.

### Back-compat aliases

For the migration window, `src/_compat.cyr` forwards every legacy
cyrius-stdlib name (`json_parse`, `u256_add`, `base64_encode`, …) to the
canonical `bayan_*` API. Downstream consumers keep building unchanged
until they re-pin and migrate; the aliases are deprecated and will be
removed once the ecosystem has moved over. `yaml` and `pdf` are new API
with no legacy names, so they have no aliases.

## Build

```sh
cyrius deps                              # resolve stdlib deps
cyrius build src/main.cyr build/bayan    # compile the smoke (exits 42)
cyrius test                              # run tests/*.tcyr
cyrius distlib --all                     # regenerate dist/ (the fold artifacts)
```

## Consuming

Every bundle opens with a compile-verified `# Requires` block that includes
the stdlib leaves its `.deps` sidecar names (cyrius ≥ 6.6.18 distlib), so
the bundle alone is enough. From 1.5.14 `bayan_f64_parse` delegates to the
stdlib's `f64_parse_n`, so a bundle needs cyrius ≥ 6.7.9 to compile:

```cyrius
include "lib/bayan.cyr"
```

⚠ **From 1.5.14 bayan needs stdlib `math`.** A consumer with a hand-written
include list must include **`lib/math.cyr`** before `lib/bayan.cyr` (the full
bundle and the json / yaml sublibs; the others do not), and must have it
vendored — the `.deps` sidecars of those three name `math`, so `cyrius deps`
does that.

⚠ **From 1.11.1 bayan needs stdlib `slice` too.** json's parsers read the
document through bounds-checked slices, so the same hand-written list must
include **`lib/slice.cyr`** before `lib/bayan.cyr` (the full bundle and the
json / yaml / toml-tree sublibs, which carry json); their `.deps` sidecars and
`# Requires` blocks name it. So, for those four and the flat toml sublib, does
**`lib/hashseed.cyr`**: json's duplicate-key set and both toml parsers' key
indexes hash a peer's keys with the stdlib's per-process seed.

### PDF compression is opt-in

`bayan_pdf_*` does **not** depend on `lib/sankoch.cyr`. bayan folds into
cyrius's stdlib, and a hard include of sankoch from a folded module would
create a module-ordering hazard there for a filter many consumers never
touch. So `FlateDecode` / `FlateEncode` is reached through hooks you
install:

```cyrius
include "lib/sankoch.cyr"
bayan_pdf_set_inflate(&zlib_decompress);
bayan_pdf_set_deflate(&zlib_compress);
```

Without them the writer emits valid uncompressed PDFs and the reader
reports a specific error on a compressed stream — never silent garbage.

If you parse untrusted PDFs, install a ratio-capped wrapper around
`zlib_decompress_with_ratio_cap` rather than the bare entry: the
four-argument hook signature cannot express sankoch's ratio limit, so
bayan's own defence is the destination cap it passes plus a per-document
total budget.

## Documentation

- [`docs/development/state.md`](docs/development/state.md) — live state snapshot
- [`docs/development/roadmap.md`](docs/development/roadmap.md) — open work, by release slot (1.x.x)
- [`docs/benchmarks.md`](docs/benchmarks.md) — captured by `cyrius bench`
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`CHANGELOG.md`](CHANGELOG.md) — complete from 1.0.0

## License

GPL-3.0-only
