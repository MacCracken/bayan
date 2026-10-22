# bayan — Roadmap

> The open work, in release order. State lives in [`state.md`](state.md); what shipped, and why,
> lives in [`CHANGELOG.md`](../../CHANGELOG.md). An item is deleted from this file in the release
> that ships it, and its CHANGELOG entry is the record.
>
> The slots are a sequence, not a promise: one can move, split or merge when a filing or a cyrius
> pin changes what comes first. A 1.6.x patch changes no public signature and no answer to valid
> input. A minor names, up front, the change a consumer has to make.
>
> Cleaned 2026-10-15 (1.6.0): every finished section was removed (the pin moves to 6.6.6, 6.7.5,
> 6.7.9 and 6.7.11, the 6.6.13 / 6.6.16 follow-ups, YAML, PDF, M0 and the scaffold's empty M1 / M2).
> The 6.6.6 by-value `Str` analysis, the one part with no other home, is now
> [architecture note 001](../architecture/001-str-parameters-are-handles.md).
> 1.6.1 (2026-10-15) shipped its slot whole and removed it; its two kept cyml delimiter answers
> joined 1.7.0.
> 1.6.2 (2026-10-15) shipped its slot whole and removed it. So did 1.7.0, whose cyml line rule also
> covers the end of a region and a last line with no newline; it added 1.7.1 and a 1.8.0 item.
> 1.7.1 (2026-10-15) and 1.8.0 (2026-10-15) each shipped their slot whole and removed it.
> 1.9.0 (2026-10-15) shipped its slot whole (`bayan_markdown_*`) and removed it; its `MD_*` names
> joined 1.10.0's `const` list.
> 1.10.0 (2026-10-22) shipped its slot whole and removed it, with the pin move to 6.7.16. Typed by
> what they are rather than by spelling, the names were 99 constants and 32 predicates, not 86 and
> 27 (ADR 0012). No name collided with another fold in 6.7.16's `lib/`.

## 1.11.0 — minor: TOML into the tagged tree; one lookup key type

- **`bayan_toml_v_parse`** into json's value tree, the way yaml already parses. 1.5.4 gave dotted
  keys and inline tables real answers inside the flat model, so this is less urgent than it was. It
  is still the right shape for the surface, and it is the answer to the next item.
- **The two flat lookups disagree on their key type** (Known gap 7). `bayan_json_get` needs a
  `Str`, `bayan_toml_get` a cstring, and the wrong one is a silent "not found". The fix is
  ADR 0004's: name the key type in the function and deprecate the bare name. `bayan_toml_get`'s key
  should also carry `: cstring`, so the named-`Str` diagnostic can fire.
- **The two subset edges the flat model cannot express** (Known gap 1). A dotted key whose quoted
  segment contains a dot (`a."b.c".d`) joins into a name indistinguishable from `a.b.c.d`, and a
  `[[array-of-tables]]` under a dotted parent is not merged with a same-named sibling. A tree keeps
  the segments apart, so both get an answer there. In the flat API they stay documented.

## 1.12.0 — the frozen surface

These are the open half of the criteria the scaffold set for a stable surface. The met half: a
reference-coverage floor of 100 in CI, the benchmarks, the fuzz harnesses, and a complete CHANGELOG.

- **A security audit pass** written to `docs/audit/YYYY-MM-DD-audit.md`, covering every parser that
  reads untrusted input. Its fixes ship as patches.
- **Every exported symbol documented and tested.** Then the public API is called frozen, and later
  changes follow the deprecate-then-remove path.
- (Not bayan's work, but part of the criterion: one downstream consumer green on the frozen
  surface.)

## Gated on cyrius — no slot until the gate opens

- **The SAX callbacks and the Flate hooks → traits**, once cyrius ships checked `dyn`. Today both
  are hand-rolled fn-pointer dispatch, and [ADR 0001](../adr/0001-flate-via-hooks-not-a-sankoch-dependency.md)
  explains why Flate is a hook.

## Out of scope

This list keeps work from being added by accident.

- **PDF encryption.** Detected and rejected with a specific message. Even "empty user password"
  documents need the full standard security handler (MD5/RC4/SHA-256/AES-CBC), which is `sigil`'s
  domain. Pulling it in would recreate the module-ordering hazard in the cyrius fold that the Flate
  hooks were designed to avoid.
- **PDF rendering.** bayan writes and reads PDF structure and text. Rasterising a page is a
  different problem and belongs with the image/graphics stack.
- **`LZWDecode` and the image codecs** (`DCTDecode`, `JPXDecode`, `CCITTFaxDecode`,
  `JBIG2Decode`). Rejected by name rather than silently passed through, because returning
  still-encoded bytes as "text" is the silent-wrong-answer shape this library refuses.
- **Full YAML 1.2.** The subset is documented, and everything outside it is rejected loudly.
