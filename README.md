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

**1.5.0** — ten modules, ~14,900 lines of `src/`, 332 public functions.
Zero cross-module dependencies except `yaml`, which parses into `json`'s
value tree by design. Folded into `cyrius/lib/bayan.cyr`.

Current version, surface area, dependency gaps and in-flight work live in
[`docs/development/state.md`](docs/development/state.md); this file stays
short on purpose.

## Modules

| Module | Public prefix | Surface |
|--------|---------------|---------|
| `pdf`    | `bayan_pdf_*`    | PDF writer + reader: pages, standard-14 fonts with real AFM metrics, text and graphics operators, metric word wrap, xref tables **and** 1.5 xref streams, object streams, text extraction |
| `json`   | `bayan_json_*`   | parser + tagged value tree + builder + streaming + JSON-pointer |
| `yaml`   | `bayan_yaml_*`   | pragmatic YAML subset into json's value tree, plus frontmatter split |
| `toml`   | `bayan_toml_*`   | sections + key/value parse, multiline strings, array-value access |
| `cyml`   | `bayan_cyml_*`   | Cyrius config (entries/docs, env expansion) |
| `csv`    | `bayan_csv_*`    | line parse / escape / write |
| `base64` | `bayan_base64_*` | standard + URL alphabet, encode/decode |
| `bigint` | `bayan_u256_*`   | 256-bit unsigned int (add/sub/mul/mod, modular arithmetic, hex) |
| `u128`   | `bayan_u128_*`   | 128-bit unsigned int (full arithmetic + bitwise + divmod) |
| `dtoa`   | `bayan_f64_*`    | round-trip-correct f64 ⇄ decimal (Grisu2), used by `json` |

### Per-format sublibs

`cyrius distlib <name>` emits `dist/bayan-<name>.cyr` — the self-contained
closure of one format's entry points, for consumers that want one parser
without the full bundle's footprint. Each ships a `.deps` sidecar listing
the stdlib leaves it needs. `bayan-pdf` is a single-module closure: it
carries its own object graph and number emitter, so neither `json` nor
`dtoa` rides along.

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

A consumer supplies the stdlib prereqs (notably `result`, which is *not*
in cyrius's stdlib auto-prepend set) and includes the bundle:

```cyrius
include "lib/result.cyr"
include "lib/fnptr.cyr"
include "lib/bayan.cyr"
```

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
- [`docs/development/roadmap.md`](docs/development/roadmap.md) — milestones through v1.0
- [`docs/benchmarks.md`](docs/benchmarks.md) — captured by `cyrius bench`
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`CHANGELOG.md`](CHANGELOG.md) — complete from 1.0.0

## License

GPL-3.0-only
