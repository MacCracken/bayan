# 002 — A program holds one copy of each bayan module that declares a `const`

cyrius refuses a top-level `const` declared twice, even when both declarations have the same value
(`const 'X' is declared twice`). It also refuses a `const` and a `var` with the same name, in
either order (`'X' is already declared as a top-level const`). Two copies of a `var` or of a `fn`
build: a `var` silently, and a `fn` with a "duplicate fn" warning, where the last definition wins.
Including the same file twice under the same spelling is deduplicated and is not a second copy.

So a module that declares a `const` can be in a program once. Measured at bayan 1.10.0 on cyrius
6.7.16, by building each pair with `--no-deps`:

| Module | Its top-level `const`s | A second copy |
|---|---|---|
| `json` (and `yaml`, whose bundle carries `json`) | `_JP_STATE_SIZE` (1.5.13); the public `JTAG_*`, `JSON_K_*`, `JS_EV_*`, `JV_SIZE`, `JSON_PAIR_SIZE` (1.10.0) | refused since 1.5.13 |
| `pdf` | `_PDF_STATE_SIZE` (1.5.13); `PTAG_*` and the public `PDF_*` (1.10.0) | refused since 1.5.13 |
| `markdown` | `_MD_*`, `_MN_*`, `_MP_*` (1.9.0); `MD_K_*`, `MD_EXT_*`, `MD_ALIGN_*` (1.10.0) | refused since 1.9.0 |
| `toml` | `TOML_K_*` (1.10.0) | **refused since 1.10.0** |
| `bigint` | `U256_SIZE` (1.10.0) | **refused since 1.10.0** |
| `base64`, `csv`, `u128`, `cyml`, `dtoa` | none | builds, with one "duplicate fn" warning per function |

A program gets a second copy in three ways:

- **Two sublibs that share a module.** `bayan-yaml` carries `json.cyr` and `dtoa.cyr`, so it cannot
  sit beside `bayan-json`.
- **A sublib beside the full bundle.**
- **Any bundle beside cyrius's own fold, `lib/bayan.cyr`.** Other stdlib files include that fold:
  at 6.7.16, `lib/sigil.cyr`, `lib/ws.cyr`, `lib/ws_server.cyr` and `lib/yantra.cyr`. bayan's own
  `lib/` holds the same file, vendored back by `lib sync --full`. `scripts/vendored-fold-guard.sh`
  keeps it out of bayan's builds (state.md, Known gap 4).

The modules that still build twice are not the safer case. Their second copy compiles, and its
functions silently replace the first copy's. If the two copies are different bayan releases, the
program runs whichever version came last. A refusal is the better outcome.

A program that needs several formats includes one bundle that carries all of them. If it already
reaches `lib/bayan.cyr` through another stdlib file, it uses that fold instead of a vendored bundle.

**Re-check** whenever a module gains or loses a top-level `const`, and on any pin whose CHANGELOG
touches duplicate declarations.
