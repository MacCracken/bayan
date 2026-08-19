#!/usr/bin/env bash
#
# consumer-check.sh — compile a throwaway consumer against every dist bundle.
#
# bayan's product is `dist/*.cyr`, not `build/bayan`. `cyrius distlib --check`
# proves the bundles are regenerable from `src/`; this proves the other half of
# the contract — that a DOWNSTREAM repo can actually use one, supplying only
# the stdlib leaves that bundle's `.deps` sidecar declares and nothing more.
#
# The distinction matters because `distlib` strips includes. A bundle that
# quietly depends on a module outside its sidecar still builds inside bayan
# (bayan's own `lib/` holds the whole snapshot, and `cyrius build`
# auto-prepends everything in `[deps].stdlib`) while failing in a consumer
# that vendored only the declared leaves. Hence `--no-deps`: the consumer's
# explicit includes are the ONLY stdlib in scope, which is the consumer's
# real situation.
#
# Usage: scripts/consumer-check.sh [workdir]     (default: build/.consumer-check)
#
set -euo pipefail

OUT="${1:-build/.consumer-check}"
mkdir -p "$OUT"

# Canonical single-pass include order. cyrius is a single-pass compiler, so a
# module may only reference symbols defined earlier — the sidecar says WHICH
# leaves are needed, this list fixes the ORDER they go in.
ORDER="syscalls string alloc io vec str fmt tagged result fnptr assert bench"

# --- Known-incomplete sidecars ------------------------------------------------
# `cyrius distlib` generates each sidecar from the leaves BAYAN's own code
# touches; it does not close over the stdlib's own unincluded dependencies.
# `lib/str.cyr` calls memcpy/memeq (string) and fmt_int (fmt) with no include
# lines of its own, `lib/result.cyr` calls fmt_int, and `lib/io.cyr` calls
# memcpy — so any bundle whose sidecar names str/result/io but not string/fmt
# under-declares. Verified minimal fix: bayan-toml needs +string +fmt,
# bayan-cyml needs +fmt.
#
# The sidecars are generated, so editing them here would be undone by the next
# `cyrius distlib --all`. Until the generator closes the transitive set these
# two are expected failures — and this script FAILS if one of them starts
# passing, so the exemption cannot outlive the bug.
# See docs/development/issues/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md
EXPECTED_FAIL="bayan-toml bayan-cyml"

rc=0
for bundle in dist/bayan.cyr dist/bayan-*.cyr; do
    [ -e "$bundle" ] || continue
    name=$(basename "$bundle" .cyr)
    deps="dist/${name}.deps"
    src="$OUT/consume_${name}.cyr"

    # syscalls is unconditional — the consumer body below exits via SYS_EXIT.
    echo 'include "lib/syscalls.cyr"' > "$src"
    if [ -f "$deps" ]; then
        for m in $ORDER; do
            [ "$m" = syscalls ] && continue
            grep -qx "$m" "$deps" && echo "include \"lib/${m}.cyr\"" >> "$src"
        done
        # Any declared leaf this script has no canonical position for still
        # gets included — better a wrong-order compile error than a silent skip.
        while read -r m; do
            case "$m" in ''|'#'*) continue ;; esac
            echo " $ORDER " | grep -q " $m " || echo "include \"lib/${m}.cyr\"" >> "$src"
        done < "$deps"
    fi
    echo "include \"${bundle}\"" >> "$src"
    cat >> "$src" <<'BODY'

fn main(): i64 { return 0; }
var r = main();
syscall(SYS_EXIT, r);
BODY

    # grep -c exits 1 when the count is zero, which under `set -e` would abort
    # the sweep on a legitimately empty sidecar (bayan-u128 has one).
    leaves="no sidecar"
    if [ -f "$deps" ]; then
        n=$(grep -cve '^#' -e '^$' "$deps" || true)
        leaves="${n:-0} declared leaf(s)"
    fi

    ok=1
    problems=""
    if out=$(cyrius build --no-deps "$src" "$OUT/${name}.bin" 2>&1); then
        if echo "$out" | grep -q '^warning:'; then
            ok=0; problems=$(echo "$out" | grep '^warning:')
        fi
    else
        ok=0; problems=$(echo "$out" | tail -20)
    fi

    expected=0
    echo " $EXPECTED_FAIL " | grep -q " $name " && expected=1

    if [ "$ok" -eq 1 ] && [ "$expected" -eq 0 ]; then
        echo "ok      ${name} — clean from ${leaves}"
    elif [ "$ok" -eq 1 ] && [ "$expected" -eq 1 ]; then
        echo "FIXED   ${name} — now clean from ${leaves}."
        echo "        Drop it from EXPECTED_FAIL in this script and close the issue."
        rc=1
    elif [ "$expected" -eq 1 ]; then
        echo "known   ${name} — under-declared sidecar (${leaves}), see EXPECTED_FAIL:"
        echo "$problems" | sed 's/^/          /'
    else
        echo "FAIL    ${name} — does not compile from ${leaves}:"
        echo "$problems" | sed 's/^/          /'
        rc=1
    fi
done

if [ "$rc" -ne 0 ]; then
    echo
    echo "A bundle does not compile from the leaves its .deps sidecar declares."
    echo "Either the sidecar under-declares, or a module gained a dependency it"
    echo "should not have. Regenerate with 'cyrius distlib --all' and re-check."
fi
exit "$rc"
