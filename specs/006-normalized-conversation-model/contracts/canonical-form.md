# Contract — the canonical form and the content hash

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) R1–R4, R11

This is the contract §17 depends on and ADR-006 decision 4 governs. It is stated as a contract
rather than left to the implementation because the import state stores its output for years, and
because a later reader asking "why did this conversation re-extract" reads this file.

## What is covered

**Included**: every message, in order — its role, its text, its timestamp, its tool activity and
its record of non-text parts.

**Excluded**: the conversation's title, its source, its native id, its `started_at` and
`last_activity_at`, every field of `Provenance`, and every tag.

The title is excluded because ADR-006 decision 4 excludes it, with the stale-title consequence
recorded there. The source and native id are excluded because they are the key the hash is filed
under, not part of what is compared (R11). `Provenance` is excluded because it is metadata the
importer produces.

**The conversation's own timestamps are a separate decision, and ADR-006 does not make it.** Its
decision 4 names the *messages'* timestamps as covered, and excludes the title and importer-produced
metadata; `started_at` and `last_activity_at` are neither. They are excluded here, deliberately,
and the reasoning is this feature's rather than the ADR's:

* Nothing else about the conversation is covered — not the title, not the identity — and a start
  time is a property of the conversation, not of its content. The messages and their own timestamps
  are what a reader would call "what was said, and when".
* Including them would make a parser improvement expensive. `last_activity_at` is absent for the MVP
  source; the day a parser learns to populate it, every conversation in the corpus would re-extract,
  for a value no retrieval reads.

**The consequence, stated rather than discovered**: exactly as with a rename, a corrected start time
does not re-import on its own. The value held in the bank goes stale until some other change to the
conversation moves the hash, or until the forced re-import ADR-006 requires of the import state is
run. If that trade is judged wrong, the fix is an amendment to ADR-006 — a governance change, out
of this feature's scope — and not a quiet edit to the function below.

The included set is written out by name in the implementation, never derived from a dump of the
model, so that a field added later is outside the hash until a commit deliberately puts it in (R1).

## The payload

```json
{
  "version": 1,
  "messages": [
    {
      "role": "user",
      "text": "the message text, exactly as it stands after sanitization",
      "sent_at": "2026-01-01T09:00:00.000000Z",
      "tool_activity": [
        {"name": "web.search", "request": "…", "result": "…"}
      ],
      "non_text_parts": [
        {"kind": "image", "name": "screenshot.png"}
      ]
    }
  ]
}
```

Rules:

1. `version` is a constant `1`. It exists so that a future change to this contract is a value a
   stored hash can be compared against, rather than a silent divergence. Changing what the canonical
   form covers means incrementing it, in a commit that says what re-extracts as a result.
2. Message order is the array order. There is no index field (R6).
3. `sent_at` is the message's own time converted to UTC and rendered `%Y-%m-%dT%H:%M:%S.%fZ`,
   microseconds always present. An absent time is JSON `null` — never the import time, never the
   current clock (FR-007, R4).
4. `tool_activity` and `non_text_parts` are arrays in their own order, empty when the source carried
   none. An absent `request` or `result` is `null`.
5. No other key appears at any level.

## The bytes

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

`sort_keys=True` makes key order independent of construction order. `separators` removes whitespace.
`ensure_ascii=False` keeps non-ASCII text as text — the corpus is substantially non-ASCII, and
escaping would make the bytes depend on something the content does not control (R2).

Text is hashed as it stands. No Unicode normalization, no whitespace trimming, no case folding: two
byte-different strings are two different contents, and the model does not decide otherwise on the
parser's behalf (R2).

## The hash

```python
hashlib.sha256(canonical_bytes).hexdigest()
```

64 lowercase hex characters. This is the value §17 stores in the import state and compares on the
next run.

## Guarantees the tests must hold to

| # | Guarantee | Spec |
|---|---|---|
| C1 | Two structurally identical conversations produce the same hash, in separate processes | SC-003 |
| C2 | Changing any message's text, role, position or timestamp changes the hash | SC-003 |
| C3 | Changing tool activity or a non-text part changes the hash | R11 |
| C4 | Changing only the title leaves the hash unchanged | SC-003, ADR-006 |
| C5 | Changing any provenance field or any tag leaves the hash unchanged | ADR-006 |
| C6 | The same instant expressed at two UTC offsets hashes equal | R4 |
| C7 | A whole-second timestamp and one with microseconds render in the same shape | R4 |
| C8 | A conversation with no messages has a defined hash rather than an error | spec edge case |
| C9 | The hash is stable across runs and processes regardless of hash seed or key insertion order | FR-011 |

C1, C6 and C9 are asserted in a subprocess, not only in the test process: a determinism claim
checked once inside one interpreter is not a determinism claim.
