# bayan

> **Data-format & big-integer distfile for the AGNOS-lineage Cyrius
> ecosystem** — `json`, `toml`, `cyml`, `csv`, `base64`, `bigint` (u256),
> and `u128`. Carved out of the Cyrius stdlib so bare-metal / firmware
> consumers don't drag data-format code into kernel objects. Foldable into
> stdlib byte-identical per the sandhi pattern.

**bayan** (Arabic بيان — *statement, exposition, clear data*) is the home
for the data-domain modules that don't belong in the primitives-only
stdlib floor. Written in [Cyrius](https://github.com/MacCracken/cyrius).

## Status

**1.0.0** — initial carve out of cyrius stdlib (cyrius v6.1.25). Seven
modules, ~3,350 lines, 149 public functions, zero cross-module
dependencies. Folded byte-identical into `cyrius/lib/bayan.cyr`.

## Modules

| Module | Public prefix | Surface |
|--------|---------------|---------|
| `json`   | `bayan_json_*`   | parser + tagged value tree + builder + streaming + JSON-pointer |
| `toml`   | `bayan_toml_*`   | sections + key/value parse, multiline strings |
| `cyml`   | `bayan_cyml_*`   | Cyrius config (entries/docs, env expansion) |
| `csv`    | `bayan_csv_*`    | line parse / escape / write |
| `base64` | `bayan_base64_*` | standard + URL alphabet, encode/decode |
| `bigint` | `bayan_u256_*`   | 256-bit unsigned int (add/sub/mul/mod, modular arithmetic, hex) |
| `u128`   | `bayan_u128_*`   | 128-bit unsigned int (full arithmetic + bitwise + divmod) |

### Back-compat aliases

For the migration window, `src/_compat.cyr` forwards every legacy
cyrius-stdlib name (`json_parse`, `u256_add`, `base64_encode`, …) to the
canonical `bayan_*` API. Downstream consumers keep building unchanged
until they re-pin and migrate; the aliases are deprecated and will be
removed once the ecosystem has moved over.

## Build

```sh
cyrius deps                              # resolve stdlib deps
cyrius build src/main.cyr build/bayan    # compile the smoke (exits 42)
cyrius test                              # run tests/bayan.tcyr
cyrius distlib                           # regenerate dist/bayan.cyr (the fold artifact)
```

## Consuming

A consumer supplies the stdlib prereqs (notably `result`, which is *not*
in cyrius's stdlib auto-prepend set) and includes the bundle:

```cyrius
include "lib/result.cyr"
include "lib/fnptr.cyr"
include "lib/bayan.cyr"
```

## License

GPL-3.0-only
