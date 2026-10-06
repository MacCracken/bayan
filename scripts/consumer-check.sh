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
# EMPTY as of 1.5.5, and that is the point of the list: it is not a permanent
# exemption, it is a bug ledger that fails when a bug goes away.
#
# `cyrius distlib` used to generate each sidecar from the leaves BAYAN's own
# code touches, without closing over the stdlib's own unincluded dependencies.
# `lib/str.cyr` calls memcpy/memeq (string) and fmt_int/fmt_int_buf (fmt) with
# no include lines of its own, `lib/result.cyr` calls both fmt entry points, and
# `lib/io.cyr` calls memcpy — so any bundle whose sidecar named str/result/io
# but not string/fmt under-declared. `bayan-toml` and `bayan-cyml` were both
# missing `fmt`.
#
# The cyrius 6.6.0 generator closes the set: `cyrius distlib --all` now reports
# "sidecar: re-added N leaf(s) the inference missed (compile-verified)" for both
# profiles and each writes `fmt`. Verified at the 6.6.0 bump — both went FIXED
# here, which is the signal this script exists to raise, so the exemption is
# removed rather than carried.
# See docs/development/issues/archived/2026-08-19-distlib-sublib-deps-sidecar-not-transitive.md
EXPECTED_FAIL=""

# --- The harness's own warning floor ---------------------------------------
# This script includes lib/syscalls.cyr unconditionally (its consumer body
# exits through SYS_EXIT), so a consumer with ZERO declared leaves is the
# scaffold alone. Whatever that emits has nothing to do with any bundle and is
# subtracted below.
#
# Under the cyrius 6.6.9 pin that floor is EMPTY (bayan 1.5.8). Through 6.6.8,
# syscalls.cyr's sigset/epoll/timer helpers called `alloc` while only its cx
# arm included lib/alloc.cyr, so this scaffold emitted exactly
# `warning: undefined function 'alloc'` and that one warning was expected here.
# cyrius 6.6.9 made the include unconditional (its CHANGELOG [6.6.9]), the
# scaffold now builds clean, and the assertion below failed on the pin bump —
# as it should. Nothing is subtracted now: every warning a bundle build prints
# is that bundle's.
#
# Only warnings the SCAFFOLD produces are subtracted, never ones a declared
# leaf produces: a leaf's unresolved call is precisely the under-declaration
# this gate exists to catch (see EXPECTED_FAIL above), so subtracting a
# per-bundle baseline would define the bug out of existence.
#
# The floor is asserted, not assumed. If it ever stops being exactly this —
# today, no warning at all — the script fails rather than widening the
# exemption silently, the same reason EXPECTED_FAIL fails when a known-bad
# bundle starts passing.
HARNESS_EXPECT=""
hbase="$OUT/_harness.cyr"
{
    echo 'include "lib/syscalls.cyr"'
    echo
    echo 'fn main(): i64 { return 0; }'
    echo 'var r = main();'
    echo 'syscall(SYS_EXIT, r);'
} > "$hbase"
hout=$(cyrius build --no-deps "$hbase" "$OUT/_harness.bin" 2>&1 || true)
echo "$hout" | grep -o 'warning:.*' | sort -u > "$OUT/harness.warn" || true
if [ "$(cat "$OUT/harness.warn")" != "$HARNESS_EXPECT" ]; then
    echo "FAIL    the consumer scaffold's own warning floor changed."
    echo "        expected exactly: $HARNESS_EXPECT"
    echo "        got:"
    sed 's/^/          /' "$OUT/harness.warn"
    echo "        Update HARNESS_EXPECT only after confirming the new warning is"
    echo "        the scaffold's and not a bundle's."
    exit 1
fi

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
    # The deprecation probe below compiles against this exact include preamble.
    cp "$src" "$OUT/pre_${name}.cyr"
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
        # Match `warning:` ANYWHERE, not at line start. cyrius prints the FIRST
        # warning concatenated onto the `compile <src> -> <out> [arch] ` prefix
        # line, so `^warning:` never saw it — a bundle whose only defect was ONE
        # undefined function was scored `ok`, and the `ok` verdicts this gate
        # printed meant no more than "no warnings after the first". Same family
        # as the `lint` and `cyrfmt` traps in docs/development/state.md: the
        # gate ran, and proved less than it said.
        echo "$out" | grep -o 'warning:.*' | sort -u > "$OUT/${name}.warn" || true
        problems=$(comm -13 "$OUT/harness.warn" "$OUT/${name}.warn" || true)
        [ -n "$problems" ] && ok=0
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

# --- Deprecations warn the CALLER, from every bundle that ships them -----------
# bayan 1.5.10 deprecated bayan_json_v_obj_get and its alias json_v_obj_get: the
# bare name does not say what the key is (see the banner above
# bayan_json_v_obj_get_by_cstr in src/json.cyr). A deprecation nobody is warned
# about is decorative, and two things could make it so with every other gate
# green: `cyrius distlib` dropping the `#deprecated(...)` line, or a toolchain
# that stops warning. bayan's own suite cannot see either — it reaches these
# names only through `&fn` so that it stays warning-free — so this compiles a
# DIRECT call of each name, against each bundle that ships it, and counts.
#
# Per row, the probe makes two calls and must get EXACTLY three warnings, all
# labelled as the probe's own (cyrius names the entry file `<source>`; anything
# else is a warning from inside the bundle or the stdlib):
#   - `fn(0, "k")`  -> one `'fn' is deprecated: <msg>` on that line;
#   - `fn(0, sk)`, `sk` a Str local -> the deprecation again, plus cyrius's
#     `passing Str-typed 'sk' ... expects a cstring`. That second warning is what
#     the deprecated names keep `key: cstring` for; drop the annotation and it goes.
# <msg> must be EXACTLY the row's DEPRECATED_MSG, at both calls. The advice is
# the point of the deprecation, and it is directional: it sends a C-string key to
# `_by_cstr` and a Str key to `_by_str`, so advice with the two swapped, or naming
# only one of them, would send callers to a silent wrong answer. Each `bayan_*`
# name in it must also be defined in the same bundle and not itself deprecated.
#
# DEPRECATED is exact in both directions: every bundle:fn row must be defined in
# that bundle and must warn as above, and each bundle's count of `#deprecated`
# attributes must equal its rows — so deprecating another fn fails this script
# until it is listed, and therefore probed. The count is taken over CODE ONLY
# (char literals, strings and comments stripped, line numbers kept) and matches
# `#deprecated` anywhere on a line, because that is where cyrius 6.6.12 honours it
# (all measured): on its own line, indented, with whitespace before the `(`, after
# another attribute (`#must_use #deprecated(..)`), and at the end of the previous
# fn's line (`fn a() { .. } #deprecated(..)`, which deprecates the NEXT fn). A
# line-start pattern missed the last two, and a deprecation spelt that way shipped
# unlisted and unprobed. (The probe calls `fn(0, <key>)`: a future row with
# another signature fails to compile here, loudly, until it gets a body.)
DEPRECATED="bayan:bayan_json_v_obj_get bayan:json_v_obj_get bayan-json:bayan_json_v_obj_get bayan-yaml:bayan_json_v_obj_get"
declare -A DEPRECATED_MSG=(
    [bayan_json_v_obj_get]="use bayan_json_v_obj_get_by_cstr for a C-string/literal key, bayan_json_v_obj_get_by_str for a Str key"
    [json_v_obj_get]="use bayan_json_v_obj_get_by_cstr for a C-string/literal key, bayan_json_v_obj_get_by_str for a Str key"
)
DEP_ATTR='(^|[[:space:]])#deprecated([[:space:]]*\(|[[:space:]]|$)'
drc=0

# File $1 with char literals, then string literals, then `# ` comments blanked,
# one output line per input line. Char literals go FIRST: a `'"'` would otherwise
# pair with the next string's quote and erase the code between them. A `#word`
# (an attribute or directive) is not a comment and stays.
SQ="'"
STRIP_CHR="s/${SQ}(\\\\.|[^${SQ}\\\\])${SQ}/0/g"
code_only() {
    sed -E -e "$STRIP_CHR" -e 's/"([^"\\]|\\.)*"/""/g' \
        -e 's/(^|[[:space:]])#([^a-z].*)?$/\1/' "$1"
}

# 0 if bundle $1 defines fn $2 under a `#deprecated` attribute. Walks back from the
# definition over blank and attribute-only lines, and stops at the first line
# holding other code — after looking at it, since an attribute at the end of the
# previous fn's line still applies. Code-only text, so a mention in a comment or a
# string is not an attribute.
is_deprecated() {
    code_only "$1" | awk -v fn="$2" '
        { line[NR] = $0 }
        $0 ~ ("^[ \t]*fn[ \t]+" fn "[ \t]*[(]") { def[++nd] = NR }
        END {
            for (d = 1; d <= nd; d++) {
                for (k = def[d] - 1; k >= 1; k--) {
                    if (line[k] ~ /(^|[ \t])#deprecated([ \t]*[(]|[ \t]|$)/) { exit 0 }
                    if (line[k] !~ /^[ \t]*(#[a-z_]+([ \t]*[(][^)]*[)])?[ \t]*)*$/) { break }
                }
            }
            exit 1
        }'
}

for bundle in dist/bayan.cyr dist/bayan-*.cyr; do
    [ -e "$bundle" ] || continue
    name=$(basename "$bundle" .cyr)
    have=$(code_only "$bundle" | grep -oE "$DEP_ATTR" | grep -c . || true)
    want=0
    for row in $DEPRECATED; do
        [ "${row%%:*}" = "$name" ] && want=$((want + 1))
    done
    if [ "${have:-0}" -ne "$want" ]; then
        echo "FAIL    ${name} — carries ${have:-0} #deprecated attribute(s); DEPRECATED lists ${want}."
        echo "        List a new deprecation in DEPRECATED so it is probed, or restore the lost attribute."
        drc=1
    fi
done

# bayan never calls its own deprecated names. On 6.6.12 a call that cyrius parsed
# before the definition did not warn at all, so the probes below would have read
# "nowhere in the bundle" while the bundle called the name; from 6.6.16 every
# path warns, and such a call would put that warning in every build that
# includes the bundle. Either way it is refused here. Code only: char literals, then string literals, then
# `# ` comments are stripped (char literals FIRST: a `'"'` would otherwise pair
# with the next string's quote and erase the code between them), and a fn's own
# definition (`fn NAME(`) is not a reference. ANY other reference counts, not just
# `NAME(`: a call cyrfmt splits across lines (`NAME` then `(..)` on the next) and
# `&NAME` are references too, and bayan has no legitimate one.
for fn in $(for row in $DEPRECATED; do echo "${row#*:}"; done | sort -u); do
    calls=""
    for f in src/*.cyr dist/*.cyr; do
        [ -e "$f" ] || continue
        nums=$(code_only "$f" \
            | sed -E -e "s/(^|[^A-Za-z0-9_])fn[[:space:]]+${fn}[[:space:]]*\(/\1fn (/g" \
            | grep -nE "(^|[^A-Za-z0-9_])${fn}([^A-Za-z0-9_]|$)" | cut -d: -f1 || true)
        for n in $nums; do
            calls="${calls}          ${f}:${n}: $(sed -n "${n}s/^[[:space:]]*//p" "$f")"$'\n'
        done
    done
    if [ -n "$calls" ]; then
        echo "FAIL    ${fn} is deprecated, and bayan calls it (use the replacement its message names):"
        printf '%s' "$calls"
        drc=1
    else
        echo "ok      ${fn} — no call in src/ or dist/"
    fi
done

for row in $DEPRECATED; do
    name=${row%%:*}
    fn=${row#*:}
    bundle="dist/${name}.cyr"
    pre="$OUT/pre_${name}.cyr"
    probe="$OUT/deprecated_${name}_${fn}.cyr"
    want_msg=${DEPRECATED_MSG[$fn]-}
    if [ ! -e "$bundle" ] || [ ! -e "$pre" ]; then
        echo "FAIL    ${name} — DEPRECATED names it but there is no ${bundle}"
        drc=1; continue
    fi
    if ! grep -q "^fn ${fn}(" "$bundle"; then
        echo "FAIL    ${name} — DEPRECATED names ${fn}, which the bundle does not define"
        drc=1; continue
    fi
    if [ -z "$want_msg" ]; then
        echo "FAIL    ${name} — ${fn} has no DEPRECATED_MSG entry: write down the exact advice it must give"
        drc=1; continue
    fi
    cp "$pre" "$probe"
    base=$(wc -l < "$pre")
    la=$((base + 4))
    lb=$((base + 5))
    cat >> "$probe" <<PROBE

fn main(): i64 {
    var sk = str_from("k");
    var a = ${fn}(0, "k");
    var b = ${fn}(0, sk);
    return a + b;
}
var r = main();
syscall(SYS_EXIT, r);
PROBE
    if ! out=$(cyrius build --no-deps "$probe" "$OUT/deprecated_${name}_${fn}.bin" 2>&1); then
        echo "FAIL    ${name} — the ${fn} deprecation probe does not compile:"
        echo "$out" | tail -20 | sed 's/^/          /'
        drc=1; continue
    fi
    warns=$(echo "$out" | grep -o 'warning:.*' || true)
    nw=$(printf '%s\n' "$warns" | grep -c . || true)
    foreign=$(printf '%s\n' "$warns" | grep -v "^warning:\(<source>\|${probe}\):" | grep . || true)
    dep_a=$(printf '%s\n' "$warns" | grep -cE "^warning:[^:]*:${la}:[0-9]+: '${fn}' is deprecated: ." || true)
    dep_b=$(printf '%s\n' "$warns" | grep -cE "^warning:[^:]*:${lb}:[0-9]+: '${fn}' is deprecated: ." || true)
    strw=$(printf '%s\n' "$warns" \
        | grep -cE "^warning:[^:]*:${lb}:[0-9]+: passing Str-typed 'sk' to '${fn}' which expects a cstring" || true)
    msgs=$(printf '%s\n' "$warns" | sed -n "s/^warning:[^:]*:[0-9]*:[0-9]*: '${fn}' is deprecated: //p")
    nmsg=$(printf '%s\n' "$msgs" | grep -c . || true)
    nexact=$(printf '%s\n' "$msgs" | grep -cxF -- "$want_msg" || true)
    repl=$(printf '%s\n' "$msgs" | grep -oE 'bayan_[a-z0-9_]+' | sort -u || true)
    bad_repl=""
    for t in $repl; do
        if ! grep -q "^fn ${t}(" "$bundle"; then
            bad_repl="${bad_repl} ${t}(not in this bundle)"
        elif is_deprecated "$bundle" "$t"; then
            bad_repl="${bad_repl} ${t}(itself deprecated)"
        fi
    done
    if [ "$nw" -eq 3 ] && [ -z "$foreign" ] && [ "$dep_a" -eq 1 ] && [ "$dep_b" -eq 1 ] \
        && [ "$strw" -eq 1 ] && [ "$nmsg" -eq 2 ] && [ "$nexact" -eq 2 ] && [ -n "$repl" ] && [ -z "$bad_repl" ]; then
        echo "ok      ${name} — ${fn} warns at both call sites with its exact advice, and nowhere in the bundle"
    else
        echo "FAIL    ${name} — ${fn} deprecation: ${nw} warning(s), want 3 (deprecated at lines ${la}"
        echo "        and ${lb}: ${dep_a}+${dep_b}, want 1+1; Str-typed at ${lb}: ${strw}, want 1;"
        echo "        exact advice at ${nexact} of ${nmsg} deprecation(s), want 2 of 2);"
        echo "        replacements named: [$(echo $repl)]${bad_repl:+, unusable:${bad_repl}}"
        echo "        want advice: ${want_msg}"
        [ -n "$foreign" ] && echo "        warnings NOT from the caller (the bundle itself warns):"
        printf '%s\n' "$warns" | sed 's/^/          /'
        drc=1
    fi
done

# --- The replacement keeps the diagnostics the deprecated name had --------------
# Every `bayan_json_v_obj_get` call is told to move to `_by_cstr` (a C-string key)
# or `_by_str` (a Str key). `_by_cstr` carries `key: cstring`, which buys two
# diagnostics: a Str-typed local passed to it warns, and an integer-literal key is
# a compile error. Dropping the annotation leaves every other gate green, and every
# migrated call then loses both — so they are pinned here, on the name callers
# are sent to, against each bundle that ships it. The Str-local probe must get
# EXACTLY the one `passing Str-typed` warning: no deprecation (the replacement is
# not deprecated) and nothing from inside the bundle.
TYPED_CSTR="bayan:bayan_json_v_obj_get_by_cstr bayan-json:bayan_json_v_obj_get_by_cstr bayan-yaml:bayan_json_v_obj_get_by_cstr"
for row in $TYPED_CSTR; do
    name=${row%%:*}
    fn=${row#*:}
    bundle="dist/${name}.cyr"
    pre="$OUT/pre_${name}.cyr"
    if [ ! -e "$bundle" ] || [ ! -e "$pre" ] || ! grep -q "^fn ${fn}(" "$bundle"; then
        echo "FAIL    ${name} — TYPED_CSTR names ${fn}, which ${bundle} does not define"
        drc=1; continue
    fi
    probe="$OUT/typed_${name}_${fn}.cyr"
    cp "$pre" "$probe"
    lb=$(( $(wc -l < "$pre") + 5 ))
    cat >> "$probe" <<PROBE

fn main(): i64 {
    var sk = str_from("k");
    var a = ${fn}(0, "k");
    var b = ${fn}(0, sk);
    return a + b;
}
var r = main();
syscall(SYS_EXIT, r);
PROBE
    ok=1
    if ! out=$(cyrius build --no-deps "$probe" "$OUT/typed_${name}_${fn}.bin" 2>&1); then
        ok=0; warns=$(echo "$out" | tail -20)
    else
        warns=$(echo "$out" | grep -o 'warning:.*' || true)
        nw=$(printf '%s\n' "$warns" | grep -c . || true)
        strw=$(printf '%s\n' "$warns" \
            | grep -cE "^warning:(<source>|${probe}):${lb}:[0-9]+: passing Str-typed 'sk' to '${fn}' which expects a cstring" || true)
        [ "$nw" -eq 1 ] && [ "$strw" -eq 1 ] || ok=0
    fi
    lit="$OUT/typed_lit_${name}_${fn}.cyr"
    cp "$pre" "$lit"
    cat >> "$lit" <<PROBE

fn main(): i64 {
    var c = ${fn}(0, 5);
    return c;
}
var r = main();
syscall(SYS_EXIT, r);
PROBE
    if lout=$(cyrius build --no-deps "$lit" "$OUT/typed_lit_${name}_${fn}.bin" 2>&1); then
        ok=0; litmsg="COMPILED (want a compile error)"
    elif ! echo "$lout" | grep -q "passing integer literal 5 to '${fn}' which expects a cstring"; then
        ok=0; litmsg="failed, but not on the cstring check: $(echo "$lout" | grep -m1 -o 'error:.*')"
    else
        litmsg="refused"
    fi
    if [ "$ok" -eq 1 ]; then
        echo "ok      ${name} — ${fn} warns on a Str local (and only that), refuses an integer key"
    else
        echo "FAIL    ${name} — ${fn} lost a diagnostic of its \`key: cstring\`: want exactly one"
        echo "        'passing Str-typed' warning at line ${lb} and an integer-literal key refused;"
        echo "        integer-literal key: ${litmsg}; Str-local probe warnings:"
        printf '%s\n' "${warns:-(none)}" | sed 's/^/          /'
        drc=1
    fi
done

if [ "$drc" -ne 0 ]; then
    echo
    echo "A deprecated bayan fn no longer warns its caller or gives its exact advice, bayan"
    echo "calls a deprecated fn, a bundle warns on its own, or the C-string lookup lost its"
    echo "diagnostics. See the DEPRECATED and TYPED_CSTR blocks in this script."
    rc=1
fi
exit "$rc"
