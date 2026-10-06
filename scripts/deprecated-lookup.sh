#!/usr/bin/env bash
#
# deprecated-lookup.sh — build tests/deprecated_lookup.cyr expecting EXACTLY its
# deprecation warnings, then run it.
#
# The program pins the answers of bayan's two deprecated lookups (see its header).
# From cyrius 6.6.16 every reference to a deprecated fn warns, so it cannot go
# through scripts/no-warnings.sh. The expectation is exact, not a pattern
# allowance: one warning per call of a deprecated name, on that call's line,
# carrying the exact advice — and no other warning at all.
#
# Usage: scripts/deprecated-lookup.sh [--aarch64] [outdir]    (default: build)
#
set -euo pipefail

ARCH=""
RUNNER=""
if [ "${1:-}" = "--aarch64" ]; then ARCH="--aarch64"; RUNNER="qemu-aarch64"; shift; fi
OUT="${1:-build}"
mkdir -p "$OUT"

SRC=tests/deprecated_lookup.cyr
BIN="$OUT/deprecated-lookup${ARCH:+-a64}"
DEPRECATED="bayan_json_v_obj_get json_v_obj_get"
MSG="use bayan_json_v_obj_get_by_cstr for a C-string/literal key, bayan_json_v_obj_get_by_str for a Str key"

# Expected: "<line> <name>" for every call of a deprecated name outside a comment.
want=$(grep -noE '[A-Za-z0-9_]+\(' "$SRC" | grep -v '^[0-9]*:#' | while IFS=: read -r n tok; do
    name=${tok%(}
    for d in $DEPRECATED; do
        if [ "$name" = "$d" ] && ! sed -n "${n}p" "$SRC" | grep -qE '^[[:space:]]*#'; then
            echo "$n $name"
        fi
    done
done | sort)
nwant=$(printf '%s\n' "$want" | grep -c . || true)
test "$nwant" -gt 0 || { echo "FAIL    no call of a deprecated name found in $SRC"; exit 1; }

if ! out=$(cyrius build $ARCH "$SRC" "$BIN" 2>&1); then
    echo "FAIL    $SRC does not compile:"; printf '%s\n' "$out" | tail -20; exit 1
fi
warns=$(printf '%s\n' "$out" | grep -o 'warning:.*' || true)
have=$(printf '%s\n' "$warns" | grep . | while IFS= read -r w; do
    rest=${w#warning:*:}            # "<line>:<col>: '<name>' is deprecated: <msg>"
    line=${rest%%:*}
    name=$(printf '%s\n' "$w" | sed -n "s/^warning:[^:]*:[0-9]*:[0-9]*: '\([A-Za-z0-9_]*\)' is deprecated: .*/\1/p")
    msg=$(printf '%s\n' "$w" | sed -n "s/^warning:[^:]*:[0-9]*:[0-9]*: '[A-Za-z0-9_]*' is deprecated: //p")
    if [ -n "$name" ] && [ "$msg" = "$MSG" ]; then echo "$line $name"; else echo "UNEXPECTED $w"; fi
done | sort)

if [ "$have" != "$want" ]; then
    echo "FAIL    $SRC: the warnings are not exactly one per deprecated call with its exact advice"
    diff <(printf '%s\n' "$want") <(printf '%s\n' "$have") | sed 's/^/        /' || true
    exit 1
fi
echo "ok      $SRC — exactly ${nwant} deprecation warning(s), one per call, each with its exact advice"

if [ -n "$RUNNER" ]; then "$RUNNER" "$BIN"; else "$BIN"; fi
