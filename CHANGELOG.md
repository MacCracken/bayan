# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
  see `docs/development/issues/2026-07-16-agnosai-yaml-parse-into-tagged-value-tree.md`.
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
  `docs/development/issues/2026-07-16-agnosai-json-no-recursion-depth-cap.md`.
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
  `docs/development/issues/2026-06-23-thoth-json-value-parser-global-cursor-not-thread-safe.md`.

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
