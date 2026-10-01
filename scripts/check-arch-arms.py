#!/usr/bin/env python3
"""Check that an arch-gated function sets `result` on every target, including
a target that defines no CYRIUS_ARCH_* macro at all.

WHY THIS EXISTS. CI compiles x86_64 and aarch64. The cx bytecode backend
predefines CYRIUS_TARGET_CX and no CYRIUS_ARCH_* macro, and its compiler is not
in the release toolchain CI installs, so no test ever compiles what cx
compiles. Through 1.5.9 bayan_u64_mulmod had an `#ifdef CYRIUS_ARCH_X86` arm,
an `#ifdef CYRIUS_ARCH_AARCH64` arm and nothing else. On cx neither arm
compiled, and every call with a, b and m below 2^63 returned the 0 that
`result` starts at, while both CI targets stayed green.

What it does: for each named function, it applies cyrius's conditional
directives to the body three times, as x86 (CYRIUS_ARCH_X86), as aarch64
(CYRIUS_ARCH_AARCH64) and as a target with neither (cx). Each time, the code
that survives must set `result`, through an `asm { }` block or a
`result = ...` statement. With neither macro it must also contain no `asm`
block, because those bytes would belong to some other machine. On x86_64 and
aarch64 it must contain one: a misspelt macro (`#ifdef CYRIUS_ARCH_X86_64`)
would otherwise drop the hardware arm, leave the portable arm setting `result`,
and pass every suite at several times the cost.

A directive it cannot evaluate (`#if` with a comparison, a `#define` inside
the body) fails the check rather than being guessed at.

Usage:  check-arch-arms.py FILE FN [FN ...]
        e.g. check-arch-arms.py src/u128.cyr bayan_u64_mulmod
Exit 0 when every target sets `result` in every named function, 1 otherwise.
"""
import re
import sys

TARGETS = (   # (name, predefined macros, must the surviving code hold an asm block?)
    ("x86_64", {"CYRIUS_ARCH_X86"}, True),
    ("aarch64", {"CYRIUS_ARCH_AARCH64"}, True),
    ("no CYRIUS_ARCH_* (cx)", set(), False),
)
PLAT = {"x86": "CYRIUS_ARCH_X86", "aarch64": "CYRIUS_ARCH_AARCH64"}
SETS_RESULT = re.compile(r"^\s*(asm\s*\{|result\s*=(?!=))")
ASM = re.compile(r"^\s*asm\s*\{")


class Unsupported(Exception):
    pass


def body_of(lines, fn):
    """The lines of `fn NAME(` up to the first line that is exactly `}`."""
    start = [i for i, l in enumerate(lines) if l.startswith("fn " + fn + "(")]
    if len(start) != 1:
        raise Unsupported(f"{len(start)} definitions of {fn}")
    for j in range(start[0] + 1, len(lines)):
        if lines[j].rstrip() == "}":
            return lines[start[0] + 1:j]
    raise Unsupported(f"no closing brace for {fn}")


def surviving(body, defs):
    """The non-directive lines a target with `defs` predefined compiles."""
    stack = []   # (enclosing region active, some branch already taken, this branch active)
    out = []

    def active():
        return not stack or stack[-1][2]

    for n, line in enumerate(body, 1):
        t = line.strip()
        word = t.split()[0] if t.startswith("#") and len(t) > 1 else ""
        arg = t.split()[1] if len(t.split()) > 1 else ""
        if word in ("#ifdef", "#ifndef", "#ifplat", "#if"):
            if word == "#ifdef":
                cond = arg in defs
            elif word == "#ifndef":
                cond = arg not in defs
            elif word == "#ifplat":
                cond = PLAT.get(arg) in defs
            else:
                if len(t.split()) != 2:
                    raise Unsupported(f"line {n}: cannot evaluate `{t}`")
                cond = arg in defs
            outer = active()
            stack.append((outer, cond, outer and cond))
        elif word == "#elif":
            if not stack or len(t.split()) != 2:
                raise Unsupported(f"line {n}: cannot evaluate `{t}`")
            outer, taken, _ = stack.pop()
            cond = arg in defs and not taken
            stack.append((outer, taken or cond, outer and cond))
        elif word == "#else":
            if not stack:
                raise Unsupported(f"line {n}: #else with no open conditional")
            outer, taken, _ = stack.pop()
            stack.append((outer, True, outer and not taken))
        elif word in ("#endif", "#endplat"):
            if not stack:
                raise Unsupported(f"line {n}: {word} with no open conditional")
            stack.pop()
        elif word in ("#define", "#elseif"):
            raise Unsupported(f"line {n}: `{word}` inside the body")
        elif active():
            out.append(line)
    if stack:
        raise Unsupported(f"{len(stack)} conditional(s) left open at the closing brace")
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__.split("Usage:")[1].strip(), file=sys.stderr)
        return 2
    path, fns = sys.argv[1], sys.argv[2:]
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    bad = 0
    for fn in fns:
        try:
            body = body_of(lines, fn)
            for name, defs, needs_asm in TARGETS:
                code = surviving(body, defs)
                has_asm = any(ASM.match(l) for l in code)
                if not any(SETS_RESULT.match(l) for l in code):
                    print(f"FAIL {path}: {fn}: on {name} no arm sets `result`, "
                          "so the fn returns the value it was declared with")
                    bad += 1
                elif not needs_asm and has_asm:
                    print(f"FAIL {path}: {fn}: on {name} an asm block survives; "
                          "its bytes belong to some other machine")
                    bad += 1
                elif needs_asm and not has_asm:
                    print(f"FAIL {path}: {fn}: on {name} no asm block survives; "
                          "the hardware arm is gone (a misspelt arch macro?)")
                    bad += 1
                else:
                    print(f"ok   {path}: {fn}: {name} sets `result`")
        except Unsupported as e:
            print(f"FAIL {path}: {fn}: {e}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
