# 001 — A `: Str` parameter is a handle, and three PDF constructors keep it

Three constructors store their `: Str` parameter into an object that outlives the call:

| Function | Store |
|---|---|
| `bayan_pdf_obj_string_new_a(a, s: Str)` | `store64(o + 8, s)` |
| `bayan_pdf_obj_hex_new_a(a, s: Str)` | `store64(o + 8, s)` |
| `bayan_pdf_obj_stream_new_a(a, dict, data: Str)` | `store64(o + 24, data)` |

This is safe only because cyrius passes a `Str` as its one-slot heap handle, never as a copy in the
callee's frame. `struct Str { data; len; }` is 16 bytes, which puts it in the class cyrius 6.6.6
began **deep-copying** when passed by value (its item 5). The change excludes `Str`, `Result`,
`Option` and `Tagged` *by name* (`_local_is_sptr_param`): their slot holds a heap handle, they stay
value-passed, and assigning one to another stays the pointer rebind the stdlib is built on. The
deep copy applies only to user-declared structs, and bayan declares none as parameters.

If a cyrius release ever copies a `Str` parameter into the frame, these three objects keep a pointer
into a dead frame, and nothing at the call site shows it.

**Checked** at bayan 1.5.7, on the 6.6.6 pin: string and hex objects built by the `_a` constructors
survive `bayan_pdf_to_bytes` → `bayan_pdf_obj_parse_buf` intact. A stream is checked at document
level (the `pdfcheck.py` oracle gate and the compressed round-trip test), because
`obj_parse_buf` stops at the `stream` keyword by design: a stream's `/Length` may be indirect.

**Re-check** on any pin whose CHANGELOG touches by-value struct parameters or `Str` assignment.
