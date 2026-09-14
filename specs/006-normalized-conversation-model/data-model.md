# Phase 1 — Data model: Normalized conversation model

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**:
[research.md](./research.md)

Every model is frozen and forbids extra fields (research R7). Every sequence is a tuple. Every
datetime is timezone-aware (R5). Nothing here performs input or output.

---

## Closed vocabularies

| Vocabulary | Values | Fixed by |
|---|---|---|
| `Source` | `chatgpt`, `claude-chat`, `claude-code`, `codex`, `hermes` | §6, §10 |
| `Role` | `user`, `assistant`, `system`, `tool` | §7 |
| `TagNamespace` | `source`, `project`, `type`, `user` | §6 |
| `ConversationType` | `conversation`, `coding-session`, `decision`, `troubleshooting` | §6 |
| `NonTextKind` | `image`, `file`, `audio`, `other` | this feature (FR-019) |

A value outside a closed vocabulary is rejected at construction (FR-004, FR-005, FR-020). The
string form is the value itself, so `Source.CHATGPT` renders `chatgpt` and the document id and the
`source:` tag are built from the same constant rather than from two literals.

## `Conversation`

One conversation from one source, independent of that source's export format.

| Field | Type | Required | Rule |
|---|---|---|---|
| `source` | `Source` | yes | closed vocabulary |
| `source_id` | `str` | yes | non-empty; no whitespace, no control characters; otherwise opaque (R10) |
| `title` | `str \| None` | no | absent and empty are both allowed and hash identically (excluded from the hash) |
| `started_at` | `AwareDatetime` | yes | the source's real time; never the import time (FR-007) |
| `last_activity_at` | `AwareDatetime \| None` | no | the source's own; absent when the source carries none |
| `messages` | `tuple[Message, ...]` | yes | order is the tuple's order (R6); may be empty |

Derived, read-only:

* `document_id` → `f"{source}:{source_id}"` (§10, FR-006). No setter exists.
* `canonical_form()` → the deterministic payload of [contracts/canonical-form.md](./contracts/canonical-form.md).
* `content_hash()` → SHA-256 hex of that payload's bytes (§17, FR-013).

Invariants:

* `last_activity_at`, when present, is not earlier than `started_at`.
* Two conversations differing only in `title` have equal content hashes (ADR-006 decision 4).
* An empty `messages` tuple is valid and hashes to a defined value (spec edge case).

## `Message`

One turn. Content is text; anything the source carried that is not text is recorded rather than
modelled (R11, FR-019).

| Field | Type | Required | Rule |
|---|---|---|---|
| `role` | `Role` | yes | closed vocabulary |
| `text` | `str` | yes | may be empty — a message that carried only an image is still a message |
| `sent_at` | `AwareDatetime \| None` | no | absent where the source omits it; never defaulted (FR-007) |
| `tool_activity` | `tuple[ToolActivity, ...]` | no | empty when the source carries none |
| `non_text_parts` | `tuple[NonTextPart, ...]` | no | what the source carried beyond text |

Every field above is inside the content hash (R11).

## `ToolActivity`

What a source records about a tool the assistant used.

| Field | Type | Required | Rule |
|---|---|---|---|
| `name` | `str` | yes | non-empty |
| `request` | `str \| None` | no | what the tool was asked, as text |
| `result` | `str \| None` | no | absent for a call that errored or never completed (spec edge case) |

Modelled at the level a ChatGPT export carries. Claude Code and Codex record richer structure and
arrive with their own specification and decision record (§2); extending this entity then is
expected (spec Assumptions).

## `NonTextPart`

A marker that the source carried something this model does not represent.

| Field | Type | Required | Rule |
|---|---|---|---|
| `kind` | `NonTextKind` | yes | closed vocabulary |
| `name` | `str \| None` | no | the source's own label, when it has one |

No bytes, no path, no URL: this records that something existed, so a replay from the archive is not
silently missing content nobody knows about. Storing the content itself is the archive's question
(§14), not this model's.

## `Provenance`

The §3.3 record. A separate value, attached after classification (R8, FR-009).

| Field | Type | Required | Rule |
|---|---|---|---|
| `source` | `Source` | yes | matches the conversation it describes |
| `source_id` | `str` | yes | matches the conversation it describes |
| `project` | `str` | yes | a project slug, or `unknown` (§15) |
| `repository` | `str \| None` | no | when the source carries it; ChatGPT does not (§15) |
| `title` | `str \| None` | no | the conversation's title at import time |
| `imported_at` | `AwareDatetime` | yes | the import time — the only place it appears (§11) |
| `importer_version` | `str` | yes | non-empty; supplied by the caller |

Excluded from the content hash in full: it is importer-produced metadata (ADR-006 decision 4).

## `Tag`

The §6 convention as a type (R9, FR-010). A frozen value with a `namespace` and a `value`,
rendering to `namespace:value` and nothing else.

| Namespace | Value | Rule |
|---|---|---|
| `source` | a `Source` | closed vocabulary |
| `project` | slug | `[a-z0-9][a-z0-9._-]*`; `unknown` is ordinary (§15) |
| `type` | a `ConversationType` | closed vocabulary |
| `user` | slug | as `project` |

A value that would render a malformed tag is rejected at construction. Rendering goes through one
method, so the string form the memory store sends exists in one place.

## `EnrichedConversation`

The output of §7's enrich stage: what the archive persists and what the memory store receives.

| Field | Type | Required | Rule |
|---|---|---|---|
| `conversation` | `Conversation` | yes | |
| `provenance` | `Provenance` | yes | its `source` and `source_id` equal the conversation's |
| `tags` | `tuple[Tag, ...]` | yes | may be empty; duplicates are rejected |

Derived: `document_id` and `content_hash()` delegate to the conversation, so a caller holding the
enriched form never reaches past it to recompute either.

This is the type SC-001 predicts the six boundaries of §8 will name. It exists here so that #9
declares it once rather than three times (R8).

## Relationships

```text
EnrichedConversation
├── conversation : Conversation
│                  └── messages : Message*
│                                 ├── tool_activity  : ToolActivity*
│                                 └── non_text_parts : NonTextPart*
├── provenance   : Provenance
└── tags         : Tag*
```

`Conversation` → `document_id` (derived, §10) and `content_hash()` (derived, §17). Nothing in the
tree points upward, and no entity holds a reference to a store, a client or a session.

## State transitions

None. Every entity is a frozen value; the pipeline stages of §7 produce new values rather than
advancing an existing one through states. What changes over an import run is the import state
(§17), which is #14's entity and not defined here.
