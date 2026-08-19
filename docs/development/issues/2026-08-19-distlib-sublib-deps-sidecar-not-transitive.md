# `cyrius distlib` sublib `.deps` sidecars under-declare — not closed over the stdlib's own deps

**Filed by**: bayan (2026-08-19 state review, surfaced by the new
`scripts/consumer-check.sh` CI gate)
**Against**: cyrius `distlib` (sidecar generation) — the sidecars are
auto-generated, so bayan cannot fix this in-repo
**Date**: 2026-08-19
**Version**: cyrius 6.5.28 (released tarball) / bayan 1.4.2
**Severity**: Medium — two shipped sublibs do not compile for a consumer that
follows their own `.deps` file. Undefined functions, not a wrong answer.

## What happens

`cyrius distlib <profile>` writes `dist/bayan-<profile>.deps`, documented as
"stdlib leaves this fold requires in scope". A downstream consumer is meant to
be able to include exactly those leaves plus the bundle and compile.

For two profiles that is not true:

| Sublib | Sidecar declares | Actually needs | Missing |
|---|---|---|---|
| `bayan-toml` | `alloc io vec str result` | + `string` `fmt` | `memcpy`, `memeq`, `fmt_int_buf`, `fmt_int` |
| `bayan-cyml` | `string alloc io result` | + `fmt` | `fmt_int` |

The other seven bundles (`bayan`, `bayan-json`, `bayan-yaml`, `bayan-csv`,
`bayan-base64`, `bayan-u128`, `bayan-bigint`) are correct.

## Root cause

The generator computes the leaves **bayan's own code** references. It does not
close over the leaves that those leaves themselves reference, and several
stdlib modules call across module lines without an `include` of their own:

| Module | Calls | Declares in its own `include` lines |
|---|---|---|
| `lib/str.cyr`    | `memcpy`, `memeq` (string), `fmt_int` (fmt) | *(none — no include lines at all)* |
| `lib/result.cyr` | `fmt_int` (fmt) | *(none)* |
| `lib/io.cyr`     | `memcpy` (string) | `syscalls`, `result` |

So any bundle whose sidecar names `str` / `result` / `io` but not `string` /
`fmt` under-declares by exactly that gap.

## Why it was invisible until now

`cyrius build` auto-prepends everything in the building project's
`[deps].stdlib`. bayan declares all twelve leaves, so building a
sidecar-faithful consumer *inside bayan* silently pulls in `string` and `fmt`
regardless of what the sidecar says, and the check passes vacuously. Only
`cyrius build --no-deps` — where the consumer's explicit includes are the sole
stdlib in scope — reproduces the consumer's real situation.

## Reproduction

```sh
# from the bayan repo root, at 1.4.2 / cyrius 6.5.28
cat > /tmp/consume_toml.cyr <<'EOF'
include "lib/syscalls.cyr"
include "lib/alloc.cyr"
include "lib/io.cyr"
include "lib/vec.cyr"
include "lib/str.cyr"
include "lib/result.cyr"
include "dist/bayan-toml.cyr"

fn main(): i64 { return 0; }
var r = main();
syscall(SYS_EXIT, r);
EOF
cyrius build --no-deps /tmp/consume_toml.cyr /tmp/consume_toml
# warning: undefined function 'memcpy'
# warning: undefined function 'memeq'
# warning: undefined function 'fmt_int_buf'
# warning: undefined function 'fmt_int'
```

Adding `include "lib/string.cyr"` and `include "lib/fmt.cyr"` (in canonical
single-pass order) compiles clean. Same for `bayan-cyml` with `fmt` alone.

## Asked for

`cyrius distlib` should emit the **transitive** stdlib leaf closure, not the
direct one — i.e. after collecting the leaves the fold references, keep
resolving each leaf's own unincluded symbol references until the set is
stable. The alternative (having `str.cyr` / `result.cyr` declare their own
includes) would fix it at the stdlib end and is arguably the more correct
place, but it changes include order for every consumer of those modules.

Note the compiler reports these as `warning:`, not `error:` — the consumer
build *succeeds*, and the undefined call only bites at runtime. A consumer
following the sidecar therefore gets a green build and a broken binary.

## Interim handling in bayan

`scripts/consumer-check.sh` gates all nine bundles in CI and carries
`bayan-toml` / `bayan-cyml` in an `EXPECTED_FAIL` list. The script **fails if
an expected-fail bundle starts passing**, so the exemption cannot outlive the
fix. Hand-editing the two `.deps` files is not an option — the next
`cyrius distlib --all` regenerates them.

Downstream consumers of `bayan-toml` / `bayan-cyml` should add `string` +
`fmt` / `fmt` to their include list until this lands.
