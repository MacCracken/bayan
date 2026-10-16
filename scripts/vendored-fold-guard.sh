#!/usr/bin/env bash
# Fails when bayan's own build can reach lib/bayan.cyr, the vendored copy of bayan's fold.
#
# Usage: scripts/vendored-fold-guard.sh        (from anywhere; it checks the repo it lives in)
#
# cyrius folds dist/bayan.cyr into its stdlib as lib/bayan.cyr, and `cyrius lib sync --full` vendors
# the whole snapshot into bayan's own lib/, so every pin bump puts it back (state.md Known gap 4).
# It defines every symbol src/ does, from an OLDER release: whichever definition comes last wins,
# with only duplicate-definition warnings, so an accidental include would bring back what later
# releases fixed. That is the hazard the ten dead pre-carve modules were removed for at 1.4.0.
# Deleting the file is not durable, so this guard refuses the three ways bayan could reach it:
#
#   1. an include of lib/bayan.cyr, or of a lib/bayan-<name>.cyr sublib, from src/, tests/ or
#      scripts/ (comment lines are not includes: src/ headers name the bundle for consumers);
#   2. "bayan" in cyrius.cyml's [deps].stdlib, or a [deps.bayan] table: `cyrius build` prepends
#      every listed module to every build, so this would include it with no include line at all;
#   3. a "bayan" leaf in a dist/*.deps sidecar: scripts/consumer-check.sh includes each leaf from
#      lib/, so the consumer gate would compile the bundle against the old fold.
#
# Exits 1 and names each offending line; prints the count of what it checked otherwise.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

hits=$(grep -rnE '^[[:space:]]*include[[:space:]]+"(\.\.?/)*lib/bayan(-[a-z0-9]+)?\.cyr"' \
    src tests scripts || true)
if [ -n "$hits" ]; then
    echo "::error::an include of the vendored fold lib/bayan.cyr (bayan's own code, an older release)"
    printf '%s\n' "$hits"
    fail=1
fi

# [deps].stdlib is a multi-line array; collect the [deps] table up to the next table header.
deps=$(awk '/^\[deps\][[:space:]]*$/ { on = 1; next } /^\[/ { on = 0 } on' cyrius.cyml)
if printf '%s\n' "$deps" | grep -nE '"bayan(-[a-z0-9]+)?"' >/dev/null; then
    echo "::error::cyrius.cyml [deps].stdlib lists bayan: every build would prepend lib/bayan.cyr"
    printf '%s\n' "$deps" | grep -nE '"bayan(-[a-z0-9]+)?"'
    fail=1
fi
if grep -nE '^\[deps\.bayan(-[a-z0-9]+)?\]' cyrius.cyml; then
    echo "::error::cyrius.cyml declares bayan as a dependency of itself"
    fail=1
fi

sidecars=0
for d in dist/*.deps; do
    [ -e "$d" ] || continue
    sidecars=$((sidecars + 1))
    if grep -nxE 'bayan(-[a-z0-9]+)?' "$d"; then
        echo "::error file=$d::the sidecar names bayan as a leaf: consumer-check.sh would include lib/bayan.cyr"
        fail=1
    fi
done

test "$fail" -eq 0 || exit 1
echo "vendored fold unreachable: no include in src/ tests/ scripts/, not in [deps], not a leaf of $sidecars sidecars"
