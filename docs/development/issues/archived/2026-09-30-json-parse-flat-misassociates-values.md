# `bayan_json_parse` hands keys the wrong values: a missing `:` borrows the next pair's value, a nested value is cut at its first `,` or `}`, and TAB / CR do not end a value

> **RESOLVED — bayan 1.5.10 (2026-10-01).** The repro exits 0 (14 on 1.5.9; measured on the
> cyrius 6.6.12 release, x86_64 and aarch64). All four proposed parts landed, and review of the
> fix went further than the filing:
> - closer **kinds are matched**, so the "Limitation" below is closed: `{"meta":{"x":[}],...}`
>   now stops the parse instead of surfacing meta's `admin`;
> - a value followed by `:` stops the parse. `{"a":"b":2}` gave a = `b` — row 16's harm through a
>   comma-less spelling, which the proposal did not close;
> - a bare value cut by `"` `:` `[` `]` or `{` is refused rather than returned as the part before
>   the cut (`{"GBP":0.7:9}` would give 0.7); an unterminated string or nested value, or a bare
>   value the input ends on, is no longer returned truncated;
> - nesting is capped where the tree parser caps it (128 levels counting the top-level object);
> - any refused allocation returns 0, never a partial vec, and `bayan_json_parse(0)` is an empty vec.
>
> Follow-ups done: the 16 rows are in `tests/bayan.tcyr`; the key-followed-by-`:` invariant is in
> the new `tests/json.fcyr`, which also parses every document flush against a PROT_NONE page; the
> header's stale `bayan_json_v_parse_str` pointer is corrected. See CHANGELOG [1.5.10].

**Status:** ✅ **RESOLVED** in bayan 1.5.10 — found by abaco 2.4.9's project audit.
**Placement:** unpinned.
**Discovered:** 2026-09-30, abaco 2.4.9 project audit. The context is abaco's currency-rate loader `_ccy_load_body`, which passed the `rates` object of a fetched body to `bayan_json_parse`. Two findings came from it: `ai-io-04`, and the final review's "a rates body with a missing `:` loaded the next pair's value as this key's rate".
**Severity:** Medium. The parser returns silently wrong pairs, on valid JSON as well as malformed JSON. No measured input crashed it. A strict parser in the same file is a workaround. The repro's row 11 (the `meta` row in the table below) goes wrong the way 1.5.1's escaped-quote case did: the parser resumes inside a value and reads the rest of it as top-level pairs. That may argue for a higher rating.
**Affects:** bayan 1.5.9 (HEAD `821a1d0`), measured. Diffing the function across the tags shows its code is identical from 1.5.1 to 1.5.9. The three scans named here are unchanged since 1.0.0; 1.5.1 changed only the quoted-string scan. abaco 2.4.9 gets 1.5.9 through cyrius 6.6.12's stdlib, and its vendored `lib/bayan.cyr` carries the same function body.

## Summary

`bayan_json_parse(src)` (`src/json.cyr:61`) is the flat parser. It returns a vec of key/value pairs, and each value is the raw source bytes. The file header calls its vec return best-effort (`:11-13`), and `JsonParseErr` is "reserved for a future slot" (`:16-17`). So a malformed document is not expected to produce an error, but it should not produce a wrong answer either. Today it produces three kinds of wrong answer:

1. **Valid JSON, wrong value bytes.** A bare value (a number, `true`, `false` or `null`) ends only at `,`, `}`, a space or LF. TAB and CR are JSON whitespace (RFC 8259 §2). The main loop skips them before a value, but they do not end one. The last value of a CRLF document comes back as `0.79\r`, and a TAB after a value stays inside it.
2. **Valid JSON, wrong pairs.** A nested object or array value is scanned as if it were a bare value, so it is cut at its first `,`, `}`, space or LF. The loop then resumes inside the nested value. A string there can be read as a top-level key, and a `}` there ends the whole parse. Nested members appear as top-level pairs, and the real top-level pairs after them are lost.
3. **Malformed JSON, another key's value.** After reading a key, the parser skips every byte up to the next `:`, wherever that `:` is in the document. If the key's own `:` is missing, the key gets the value of the next pair that has one. Separately, `,` is skipped in every state, so a key with no value (`"a":,`) takes the next key's name as its value.

The file header also says the module "Parses flat JSON objects" (`:8`). That does not put nested values out of scope: the function accepts them without complaint and returns wrong pairs, and cyrius's `#derive` code passes it nested values (see "What a consumer sees").

The table shows nine of the repro's 16 rows, measured on 1.5.9:

| document | should be | 1.5.9 returns |
|---|---|---|
| `{\r\n  "EUR": 0.92,\r\n  "GBP": 0.79\r\n}` | EUR=`0.92` GBP=`0.79` | EUR=`0.92` GBP=`0.79\r` |
| `{"on":\ttrue\t,\t"n":\t5\t}` | on=`true` n=`5` | on=`true\t` n=`5\t` |
| `{"x":{"a":1,"b":2},"y":3}` | x=`{"a":1,"b":2}` y=`3` | x=`{"a":1` b=`2` |
| `{"x":{"a":1},"y":3}` | x=`{"a":1}` y=`3` | x=`{"a":1` |
| `{"tags":["a","b"],"n":1}` | tags=`["a","b"]` n=`1` | tags=`["a"` b=`1` |
| `{"meta":{"x":1,"admin":"true"},"admin":"false"}` | meta=`{"x":1,"admin":"true"}` admin=`false` | meta=`{"x":1` admin=`true` |
| `{"EUR":0.92,"GBP" 0.79,"JPY":149.5}` | EUR=`0.92`, then stop (or JPY=`149.5`) | EUR=`0.92` GBP=`149.5` |
| `{"role":"user","admin",false,"audit":true}` | role=`user`, then stop (or audit=`true`) | role=`user` admin=`true` |
| `{"a":,"b":2}` | nothing (or b=`2`) | a=`b` |

In the `tags` row, the array element `"b"` is read as a key and takes `n`'s value. In the `meta` row, `bayan_json_get(pairs, str_from("admin"))` answers `true` from inside `meta`. The document's top-level `"admin":"false"` is never returned.

## How this relates to earlier filings

This is not a duplicate. Nothing open or archived in this directory covers these scans:

- The open `2026-08-04-agnosai-json-obj-get-takes-cstr-while-obj-set-takes-str.md` is about the tagged-tree API's key type.
- In `archived/`, the thoth cursor filing (resolved 1.0.3) and the agnosai depth-cap filing (resolved 1.1.1) are about the tagged-tree and streaming parsers.
- The mneme TOML-strings filing mentions the flat JSON API only as the documented example of not decoding escapes.
- The TOML structural-gaps, prakash f64-parse, YAML and distlib-sidecar filings are about other modules.

Two earlier changes touched the same function, but not these scans:

- CHANGELOG [1.5.1] fixed `bayan_json_parse`'s quoted-string scan: `\"` ended a string and let a value inject keys. That change touched only the quoted-string scan and its comment (`:83-111`). The `meta` row goes wrong the same way 1.5.1's example did: the parser resumes inside a value and reads the rest of it as top-level pairs, and the document's own top-level `admin` is never returned. In 1.5.1's example `admin` was simply missing; here a nested member answers in its place.
- [1.5.3] moved the "values are the raw source bytes" contract to the function header (`:55`). The proposed fix below applies that contract to nested values.

Part 2 was already known on the cyrius side but never filed here. The cyrius `#derive` code generator says so in a comment (`src/frontend/lex_pp.cyr:2539-2544` in the cyrius 6.6.12 tree): `bayan_json_get` "truncates an array-of-objects value at the first inner comma", and whole-array capture "is a separate bayan hardening item". No bayan filing exists for that item, so this filing covers it.

## Reproduction

`repros/2026-09-30-json-parse-flat-misassociates-values.cyr` runs 16 documents through `bayan_json_parse`. For each one it prints the returned pair list next to the expected one. The exit code is the number of wrong rows.

- **Valid documents (rows 1–11)** must give the exact pair list, in order. A nested value is expected as its raw source span.
- **Malformed documents (rows 12–16)** must give the pairs that come before the defect. After that point, only pairs the document really contains may follow, so a parser that stops and one that skips the bad pair both pass. Any pair that carries another key's value fails.

```
cyrius build docs/development/issues/archived/repros/2026-09-30-json-parse-flat-misassociates-values.cyr /tmp/jsonflat
/tmp/jsonflat; echo "exit=$?"      # -> 14 on 1.5.9 (rows 3-16)
```

Rows 1–2 (one line, and LF line endings) are controls and pass today. If the toolchain does not compile `"\r"` and `"\t"` to bytes 13 and 9, the program stops with exit 100 instead. Under each row it also prints a `tree` line showing what the tagged-tree parser makes of the same document. That line is not counted; see the workaround section. An excerpt of the 1.5.9 output:

```
WRONG 3. CRLF line endings
      doc  {\r\n  "EUR": 0.92,\r\n  "GBP": 0.79\r\n}
      got  EUR=[0.92] GBP=[0.79\r]
      want EUR=[0.92] GBP=[0.79]
      tree EUR=[0.92] GBP=[0.79]
WRONG 11. a nested member shadows a top-level key
      doc  {"meta":{"x":1,"admin":"true"},"admin":"false"}
      got  meta=[{"x":1] admin=[true]
      want meta=[{"x":1,"admin":"true"}] admin=[false]
      tree meta=[{"x":1,"admin":"true"}] admin=["false"]
WRONG 12. missing ':' before a number
      doc  {"EUR":0.92,"GBP" 0.79,"JPY":149.5}
      got  EUR=[0.92] GBP=[149.5]
      want EUR=[0.92]   then nothing, or only: JPY=[149.5]
      tree refused at byte 18: expected ':' after key
```

`bayan_json_parse_file` and `bayan_json_parse_file_r` (`:228`, `:240`) and the `json_parse` alias (`src/_compat.cyr:11`) all call this function, so they behave the same way.

## What a consumer sees

**abaco.** Its audit report (`docs/audit/2026-09-30-audit.md`) records three effects. Before 2.4.9, `_ccy_load_body` passed the `rates` object of a fetched body straight to this parser, and:

- a key whose `:` was missing was cached with the next pair's rate (row 12 shows the bayan side: GBP = `149.5`, which is JPY's rate);
- a rate that a CRLF body handed over as `0.79\r` failed abaco's number parse and was dropped (row 3);
- every rate after a nested value was lost (row 6).

**cyrius `#derive(Serialize)`.** For a nested-struct field, the generated `<T>_from_json(pairs)` re-parses the field's value with `bayan_json_parse(v)` (`src/frontend/lex_pp.cyr:2589`, cyrius 6.6.12 tree). Test setup: `struct inner { a: i64; b: i64; }` and `struct outer { x: inner; y: i64; }`, decoding `{"x":{"a":1,"b":2},"y":3}` through `outer_from_json(bayan_json_parse(s))`, built with this repo's pin (cyrius 6.6.11).

- 1.5.9: x.a = 1, x.b = 0, y = 0.
- With the fix below: x.a = 1, x.b = 2, y = 3.

**A JSON-RPC body**, measured in the MCP `tools/call` shape:

```
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tarang_codecs", "arguments": {}}}
```

This gives params=`{"name":`, because the space ends the bare scan. The tool name then comes back as a top-level key: `tarang_codecs`=`{`.

These callers exist. tarang, bote, itihas and ark reach the function through the `json_parse` alias. I did not check them for exposure (paths are under the sibling-repo root):

- `tarang/cyr/src/mcp.cyr:148`
- `bote/src/registry.cyr:337`, vendored into hoosh, thoth and szal as `src/vendor/bote-core.cyr`
- `itihas/src/hoosh.cyr:471` and `:570`
- `shravan/src/serde.cyr:94`
- `ifran/src/dataset.cyr:288`
- `ark/src/transaction.cyr:134`
- `tarka/src/pref_ingest.cyr:136`

## Root cause

All four causes are in `bayan_json_parse`, `src/json.cyr`, at 1.5.9:

- **TAB / CR (part 1).** The bare-value scan's end test at `:136` is `vc == 44 || vc == 125 || vc == 32 || vc == 10`. The whitespace skip at `:77-80` treats bytes 32, 10, 13 and 9 as whitespace, but the end test leaves out 13 and 9.
- **Nested values (part 2).** The non-string branch at `:126-148` treats any non-`"` byte after a key as the start of a bare value, including `{` and `[`. Nothing tracks depth or strings, so the `:136` scan stops inside the nested value, and the main loop resumes there.
  - With `key == 0`, the nested value's next string is taken as a key (`:113`). This is rows 5, 8 and 11.
  - The nested value's `}` hits the `break` at `:82` and ends the parse. This is rows 5–7 and 9–11.
- **Missing `:` (part 3).** The "Skip to colon" loop at `:115-119` advances to the next byte 58, wherever it is, crossing values, commas and other keys. The next value after that `:` is then paired with this key.
- **Missing value (part 4).** `:81` skips `,` in every state, including right after a key's `:`. The next string is then taken as this key's value (`:120-125`). This is row 16.

The tagged-tree parser in the same file has none of these defects:

- `_jp_skip_ws` (`:706`) treats all four whitespace bytes alike.
- `_jp_parse_value_a` recurses into objects and arrays.
- `_jp_parse_object_a` refuses a key without a following `:` (`:1130`).

## Proposed fix

I implemented and tested this in a copy of 1.5.9. The patch changes only `src/json.cyr`: 71 lines added, 12 removed. It has four parts:

1. **Any JSON whitespace ends a bare value.** A helper, `_json_flat_ws(c)`, matches space, TAB, LF and CR, and the `:136` test uses it.
2. **A nested value is one value.** When the byte after a key is `{` or `[`, the parser skips one balanced, string-aware span and stores it verbatim, consistent with "values are the raw source bytes". If the span is never closed, it stops.
3. **A key must be followed by `:`.** After a key, it skips whitespace. If the next byte is not `:`, it stops instead of scanning ahead.
4. **A `:` must be followed by a value.** After the `:`, it skips whitespace. If the next byte is `,` or `}`, or the input ends, it stops.

Each `break` below leaves the main loop and returns the pairs read so far. The patch also adds two paragraphs to the function header. One says a nested value comes back as its raw source span. The other says where the parse stops on malformed input, and that bracket kinds are not matched.

```cyrius
# JSON whitespace (RFC 8259 section 2): space, TAB, LF, CR.
fn _json_flat_ws(c): i64 {
    if (c == 32 || c == 9 || c == 10 || c == 13) { return 1; }
    return 0;
}

# Index just past the object or array that opens at data[i], or -1 when it is
# not closed before slen. String-aware. Bracket KINDS are not matched.
fn _json_flat_span_end(data, slen, i): i64 {
    var depth = 0;
    while (i < slen) {
        var c = load8(data + i);
        if (c == 34) {
            i = i + 1;
            while (i < slen && load8(data + i) != 34) {
                if (load8(data + i) == 92) { i = i + 1; }
                i = i + 1;
            }
            if (i >= slen) { return 0 - 1; }
        } elif (c == 123 || c == 91) {
            depth = depth + 1;
        } elif (c == 125 || c == 93) {
            depth = depth - 1;
            if (depth == 0) { return i + 1; }
        }
        i = i + 1;
    }
    return 0 - 1;
}

# bayan_json_parse, key branch -- replaces "Skip to colon" (:115-119):
                key = qstr;
                while (ji < slen && _json_flat_ws(load8(data + ji)) == 1) { ji = ji + 1; }
                if (ji >= slen || load8(data + ji) != 58) { break; }
                ji = ji + 1;
                while (ji < slen && _json_flat_ws(load8(data + ji)) == 1) { ji = ji + 1; }
                if (ji >= slen) { break; }
                if (load8(data + ji) == 44 || load8(data + ji) == 125) { break; }

# bayan_json_parse, bare-value branch -- replaces the scan at :133-141:
                var vs = ji;
                if (c == 123 || c == 91) {
                    var ve = _json_flat_span_end(data, slen, ji);
                    if (ve < 0) { break; }
                    ji = ve;
                } else {
                    var done = 0;
                    while (ji < slen && done == 0) {
                        var vc = load8(data + ji);
                        if (vc == 44 || vc == 125 || _json_flat_ws(vc) == 1) {
                            done = 1;
                        } else {
                            ji = ji + 1;
                        }
                    }
                }
                val = str_new(data + vs, ji - vs);
```

### Test results on the patched copy

- **Repro:** exits **0** on the patched copy and still exits **14** on the unpatched copy.
- **Each part fixes its own rows.** I built copies with one part applied at a time: part 1 fixes rows 3–4, part 2 rows 5–11, part 3 rows 12–15 and part 4 row 16, and none of them changes another row. Applied in that order, they take the exit code from 14 to 12, 5, 1 and 0.
- **bayan's suite (`cyrius test`)** is green, with the same counts as unpatched 1.5.9 and no compiler warnings:
  - `tests/bayan.tcyr`: 1281/1281, which includes the flat-API groups "the flat parser honours escapes" and "the flat key/value API";
  - `pdf_flate.tcyr`: 19/19;
  - `vectors.tcyr`: 13/13.
- **Format and lint:** `cyrius fmt --check` and `cyrius lint` are clean on `src/json.cyr`.
- **Distribution:** `cyrius distlib --all` changes `dist/bayan.cyr`, `dist/bayan-json.cyr` and `dist/bayan-yaml.cyr`, which must be committed with the fix. No `.deps` sidecar changes, and `scripts/consumer-check.sh` passes all 10 bundles (`dist/bayan.cyr` and the 9 sublibs).
- **cyrius derive tests:** six of cyrius's own derive tests from `tests/tcyr/derive/` were built against this `src/` in place of `lib/bayan.cyr`. They pass 77/77 both before and after the fix: `derive_vec_primitive`, `derive_vec_struct`, `derive_str_deserialize`, `derive_serialize_f64`, `derive_serialize_roundtrip` and `derive_from_json_str_guards`.

### Patched behaviour on inputs outside the repro (measured)

- `{"x":{"s":"a\"}"},"y":1}` gives x=`{"s":"a\"}"}` y=`1`. On 1.5.9 it gives x=`{"s":"a\"` and loses y.
- An unclosed nested value, `{"x":{"a":1`, gives no pairs. On 1.5.9 it gives the fragment x=`{"a":1`.
- `{"a" : 1}` and `{"a"\r\n:\t1\r\n}` both give a=`1`, so whitespace before `:` is still accepted.
- 100,000 levels of `[` inside one value is handled in one linear scan; the span helper does not recurse.
- **Limitation:** bracket kinds are not matched. `{"x":[1},"y":2}` gives x=`[1}` y=`2`. A closer of the wrong kind can also end a span early, and what follows it is then read as top-level pairs:
  - `{"meta":{"x":],"admin":"true"},"admin":"false"}` gives meta=`{"x":]` admin=`true`, which is row 11's shape. 1.5.9 gives the same two pairs.
  - `{"meta":{"x":[}],"admin":"true"},"admin":"false"}` gives meta=`{"x":[}]` admin=`true`, where 1.5.9 gives only meta=`{"x":[`.

  Both documents are malformed outside any string. Only someone who controls the document's structure can cause this, and that person can already write a duplicate top-level key (`bayan_json_get` returns the first match). Matching kinds would need a stack, and I did not think the flat parser warranted one. If one is wanted, a 128-entry stack would match the tagged-tree parser's depth cap (`_JP_MAX_DEPTH`, `:684`).

### Changes a caller could notice

- **A nested value now comes back whole, and its members are no longer top-level pairs.** On 1.5.9, which nested strings surfaced, and whether as keys or values, depended on the member's position and on whitespace. In row 5, `b` surfaced and `a` did not. In the JSON-RPC body above, the tool name surfaced as a key. A caller that relied on this was relying on an accident. To reach a member, re-parse the span with `bayan_json_parse(bayan_json_get(pairs, key))`, as the derive code already does.
- **A malformed document can now return fewer pairs than before.** That is the intended change.

### Follow-ups

- Move the 16 repro rows into a `tests/bayan.tcyr` group. Neither `tests/bayan.bcyr` nor `tests/bayan.fcyr` calls `bayan_json_parse` today.
- Add a fuzz invariant: every key the parser returns is followed in the source, after whitespace, by `:`. Keys borrow the source bytes, so this can be checked directly.
- While editing that header: `:57` points callers to `bayan_json_v_parse_str`, which 1.3.0 renamed to `bayan_json_v_parse_buf`. The Str entry point is `bayan_json_v_parse`.

## Consumer-side workaround

**In bayan, today: use the tagged-tree parser.** That is `bayan_json_v_parse(src)` (`src/json.cyr:1209`), `bayan_json_v_parse_buf(buf, len)` (`:1235`) or the reentrant `bayan_json_v_parse_ctx(ps, buf, len)` (`:1194`). The repro's `tree` line shows its results on the same 16 documents:

- It returns the right members for all 11 valid documents.
- It refuses all 5 malformed ones:
  - rows 12–14: `expected ':' after key`, at bytes 18, 5 and 22;
  - row 15: `expected ',' or '}'`, at byte 9;
  - row 16: `unexpected character`, at byte 5.

Unlike the flat parser, it decodes escapes, and it returns typed nodes rather than raw bytes.

**abaco 2.4.9** (`abaco`, commit `5fdc9bc`, `src/ai.cyr`) kept the flat parser and added three guards around it:

- **`_json_doc_ok`** (`:771`, built on `_json_value_end` at `:734`) requires the whole currency body to be one RFC 8259 value, nested at most `CCY_MAX_JSON_DEPTH` (8) deep. `_ccy_load_body` (`:1181`) checks this at `:1185`, before reading any key. This guard covers part 3 and the missing-value case.
- **`_ccy_rates_flat`** (`:1162`) requires the `rates` object to contain no object or array, checked string-aware at `:1195`. This guard covers part 2.
- **`_ccy_load_body`** (`:1208-1217`) trims space, TAB, LF and CR from both ends of each value before parsing it as f64. This guard covers part 1.

abaco keeps no separate issue record for this; its audit report is the record.
