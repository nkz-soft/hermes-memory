# Data model: Secret sanitizer

**Feature**: 009-secret-sanitizer (issue #11)

This feature adds no type that crosses a boundary. What crosses is #9's: a `Conversation` in, a
`Conversation` and a `RedactionReport` out. The types below are internal to
`hermes_memory.sanitization`, and are described here because they are where the rules of
contracts/redaction-rules.md live.

## Types that already exist and are used unchanged

| Type | Declared in | Role here |
|---|---|---|
| `Conversation`, `Message`, `ToolActivity`, `NonTextPart` | `hermes_memory.normalization` (#8) | the input, and the shape the rewriter rebuilds |
| `SecretSanitizer` | `hermes_memory.sanitization.sanitizer` (#9) | the protocol this feature satisfies |
| `RedactionCategory` | same | the closed §13 vocabulary a pattern reports in |
| `RedactionReport` | same | counts by category; the only thing besides the conversation that leaves |
| `SanitizationError` | same | raised when a conversation cannot be rewritten |

None of these is edited. Adding a category to `RedactionCategory` is not needed: §13's thirteen are
already declared.

## `Pattern` (internal)

One entry in the table.

| Field | Meaning |
|---|---|
| `category` | the `RedactionCategory` a match is reported under |
| `expression` | the compiled expression; every quantifier bounded, none nested (research R2) |
| `value_group` | which group holds the value to replace — the whole match for a value-shaped pattern, a named group for a keyed one or a block body |
| `minimum_length` | below which a matched value is treated as a placeholder (RR-7) |
| `within` | the regions of a text the pattern may match in; `None` means all of it |

Precedence is **not** a field: it is the entry's position in the sequence handed to the scanner, so
the table cannot disagree with itself about which of two patterns is the more specific (RR-6).

`within` exists for one category. What makes a line a Kubernetes secret is the mapping it belongs to,
and a regular expression cannot look arbitrarily far behind its own match.
`secret_manifest_blocks` computes those regions line by line: for each `data:`/`stringData:` key,
check whether its siblings — the lines of the same mapping — declare `kind: Secret`, and if so return
its block. A guard that merely asked whether the text mentioned `kind: Secret` would redact the
manifest's own metadata and the ConfigMap in the document beside it; one anchored at column 0 would
miss the `v1/List` form `kubectl get secrets -o yaml` emits (research R7).

**A `within` callable must return disjoint regions.** Two overlapping regions would hand the scanner
the same match twice. `_merge` drops the duplicate rather than trusting the caller, because `within`
is an extension point and the next callable will make the mistake this one made.

**Rules**: the table is built once at import and is immutable. Two patterns may share a category —
the AWS id and the AWS secret do (RC-8), and the vendor prefixes each have several spellings. No
pattern may report a category outside `RedactionCategory`, and a test asserts every category has at
least one pattern, so a category cannot be declared and quietly go unimplemented.

## `Span` (internal)

A region of one string that will be replaced.

| Field | Meaning |
|---|---|
| `start`, `end` | half-open bounds within the string scanned |
| `category` | what to count the replacement under |
| `precedence` | carried from the pattern, used to resolve an overlap |

**Rules**: spans are produced by every pattern, then resolved — sorted by start, and a span
overlapping one already kept is dropped (RR-6). Surviving spans are disjoint and ordered, and the
rewrite is one pass that concatenates the text between them with `[REDACTED]`. A `Span` never leaves
the module: it holds a position, and a position plus the archived original reconstructs the secret,
which is the reason #9's report has no offset field.

## `Redaction result` (internal)

What scanning one string produces: the rewritten string, and counts by category. Counting happens
here, on surviving spans, so the count is of replacements actually made (FR-013, RR-5) rather than
of matches found.

The conversation-level report is the sum of the per-string results, built as the rewriter walks the
fields of RR-3 in order.

## The rewrite, as a transformation

```text
Conversation
├── source, source_id, started_at, last_activity_at   → copied, never scanned (RR-4)
├── title                                             → scanned
└── messages[]
    ├── role, sent_at                                 → copied, never scanned
    ├── text                                          → scanned
    ├── tool_activity[] → name, request, result       → scanned
    └── non_text_parts[] → kind                       → copied
                        └─ name                       → scanned
```

`PatternSecretSanitizer` also offers `redact_text(text) -> tuple[str, RedactionReport]`, the
one-string case its own tests and the quickstart use. It is a convenience on the implementation, not
part of the boundary: nothing outside `sanitization` and its tests may depend on it, and a different
sanitizer is under no obligation to have it.

**Rules**: the output is a new value built with the model's own copy semantics; the input is never
mutated (SS-1). A field that is `None` stays `None` — a sanitizer does not invent an empty string.
A message whose text was entirely a secret becomes a message whose text is `[REDACTED]`, and stays
in place, because the order is the conversation (#8).
