#!/usr/bin/env bash
# Run a command (a cyrius build, test, fuzz or bench), print its output, and
# fail on EITHER its exit status OR any compiler warning in that output.
#
#   scripts/no-warnings.sh cyrius build src/main.cyr build/bayan
#   scripts/no-warnings.sh cyrius test --aarch64
#
# Why a gate needs both halves: `cyrius build` exits non-zero on an error but
# only WARNS on the diagnostics that matter most here (bad pointer typing, lib/
# shadowing, pin drift, a deprecated call), and `cyrius fuzz` / `cyrius bench`
# exit 0 on a harness build that only warns. So the warning text is the gate.
#
# `warning:` is matched ANYWHERE in a line, not at its start (fixed 1.5.3).
# cyrius prints the FIRST warning concatenated onto the
# `compile <src> -> <out> [arch] ` prefix line, so `^warning:` never matched it
# and a build whose ONLY diagnostic was one warning passed. That anchor had
# hidden half of a real under-declaration in scripts/consumer-check.sh for
# months. Same family as the `lint`-always-exits-0 and `cyrfmt`-reads-only-
# argv[1] traps: the gate ran and proved less than it said.
#
# This one script holds that rule, so the CI steps cannot drift apart on it
# (1.5.10; before it, eight steps each carried their own copy).
set -uo pipefail
if [ "$#" -lt 1 ]; then
    echo "usage: $0 <command> [args...]" >&2
    exit 2
fi
out=$("$@" 2>&1)
rc=$?
printf '%s\n' "$out"
if [ "$rc" -ne 0 ]; then
    echo "::error::\`$*\` exited ${rc}"
    exit "$rc"
fi
if printf '%s\n' "$out" | grep -q 'warning:'; then
    echo "::error::\`$*\` emitted compiler warnings"
    printf '%s\n' "$out" | grep -o 'warning:.*'
    exit 1
fi
