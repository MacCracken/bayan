# bayan — Current State

> Refreshed every release. CLAUDE.md is preferences/process/procedures
> (durable); this file is **state** (volatile).

## Version

**1.2.0** — new `yaml` module: YAML-subset parser into the shared
`bayan_json_v_*` tagged value tree (`bayan_yaml_parse*`) + Markdown
frontmatter split (`bayan_yaml_frontmatter_split`); filed by agnosai,
driven equally by mneme (2026-07-16). Before that, 1.1.1 added the json
recursion-depth cap (128, serde_json wire-parity) and the cyrius 6.4.64
toolchain bump. Carved from cyrius stdlib at 1.0.0 (2026-06-10).

## Toolchain

- **Cyrius pin**: `6.4.64` (in `cyrius.cyml [package].cyrius`; bumped
  2026-07-16, `lib/` snapshot re-synced via `cyrius lib sync --full`)

## Source

Seven data/big-integer modules carved byte-identical from cyrius stdlib
(public functions prefixed `bayan_`), plus the greenfield `yaml` module
(1.2.0, written in-repo — parses into json's value tree, so it must sit
after `json.cyr` in bundle order):

| Module | Lines | Public fns | Canonical prefix |
|--------|-------|-----------|------------------|
| `src/json.cyr`   | 1584 | 62 | `bayan_json_*` |
| `src/yaml.cyr`   | 874  | 12 | `bayan_yaml_*` |
| `src/u128.cyr`   | 526  | 35 | `bayan_u128_*` / `bayan_u64_*` |
| `src/cyml.cyr`   | 420  | 17 | `bayan_cyml_*` |
| `src/bigint.cyr` | 365  | 20 | `bayan_u256_*` |
| `src/toml.cyr`   | 545  | 17 | `bayan_toml_*` |
| `src/base64.cyr` | 177  | 4  | `bayan_base64_*` |
| `src/csv.cyr`    | 97   | 3  | `bayan_csv_*` |

- `src/_compat.cyr` — 153 back-compat aliases (legacy names → `bayan_*`;
  yaml is new API, no aliases).
- `dist/bayan.cyr` — ~4,750-line bundle (canonical + alias + internal helper
  fns), regenerated via `cyrius distlib`. This is the artifact folded into
  `cyrius/lib/bayan.cyr`.
- `dist/bayan-<format>.cyr` — per-format sublibs (the sigil/sandhi
  `[lib.<name>]` pattern): json / yaml / toml / cyml / csv / base64 / u128 /
  bigint, each `cyrius distlib <name>`-generated, compile-verified
  self-contained, with a `.deps` stdlib-leaf sidecar (u128 needs none).
  yaml's closure carries json.cyr (shared value tree / parser state).
  Canonical `bayan_*` names only — `_compat` aliases ride the full bundle.

## Tests

- `tests/bayan.tcyr` — base64 encode/decode + u128 arithmetic + alias parity +
  json value-parser reentrancy (nested parse, ctx path, per-call error
  reporting, trailing-content rejection) + json streaming-parser callbacks
  (real `&fn` handlers asserting per-event dispatch) + json recursion-depth
  cap (200-deep rejected on both parsers, 100-deep parses, 128/129 boundary,
  alias parity) + toml triple-quoted strings + toml array-value element access
  (bare/quoted/literal-`'`/nested/empty/trailing-comma/multi-line-comment/
  nested-inline-comment + alias parity) + yaml (scalar typing, quoting,
  comments, nested mappings, block/flow/compact sequences, doc markers,
  frontmatter split, reentrancy, err_pos, block+flow depth caps, and a
  loud-rejection battery for every out-of-subset form). 249 asserts, green
  on 6.4.64.
- `src/main.cyr` — full-bundle compile smoke (exits 42).
- Deep per-module coverage lives in cyrius's `.tcyr` suite (json/toml/csv/
  base64/bigint/u128/cyml).

## Dependencies

Direct (declared in `cyrius.cyml [deps].stdlib`): string, fmt, alloc, io,
vec, str, syscalls, assert, bench, result, fnptr, tagged. The dist bundle
strips includes — consumers must supply these (notably `result`, which is
NOT in cyrius's own stdlib auto-prepend set).

## Consumers

- **cyrius** — folds `dist/bayan.cyr` → `lib/bayan.cyr` (fold refreshed
  2026-07-06 with the 1.1.0 bundle; cyrius now at v6.4.64).
- Downstream repos using json/toml/csv/base64/bigint/u128 migrate to
  `bayan_*` on re-pin (back-compat aliases bridge the window).

## Next

See [`roadmap.md`](roadmap.md). ganita (math-domain) is the sibling carve
(v1.0.3, pins cyrius 6.4.26).
