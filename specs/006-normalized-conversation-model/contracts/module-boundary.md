# Contract — the module's public surface and its boundary

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) R12–R14

Two contracts, because `normalization` is consumed by every other stage and constrained by
Principle IV from the other side: what it offers, and what it is forbidden to reach.

## What it offers

`hermes_memory.normalization` re-exports exactly these names. Consumers import from the module, not
from the files inside it, so the internal split of R14 can change without touching a caller.

| Name | Kind | Defined in |
|---|---|---|
| `Source`, `Role`, `NonTextKind`, `ConversationType`, `TagNamespace` | closed vocabularies | `conversation.py`, `tags.py` |
| `Conversation`, `Message`, `ToolActivity`, `NonTextPart` | the conversation tree | `conversation.py` |
| `Provenance`, `EnrichedConversation` | §3.3 provenance and the enrich-stage pairing | `provenance.py` |
| `Tag`, `SourceTag`, `ProjectTag`, `TypeTag`, `UserTag` | the §6 vocabulary | `tags.py` |
| `canonical_form`, `content_hash` | the §17 hash (see [canonical-form.md](./canonical-form.md)) | `canonical.py` |

`__all__` names them, and a test asserts that `__all__` and the module's actual public attributes
agree — so a name added without being exported, or exported without existing, fails rather than
drifting.

**No name in this list is a Hindsight term** (FR-017). There is no bank, no retain, no recall, no
item, no update mode. Replacing the memory engine (ADR-001's exit strategy) must touch
`memory/hindsight` and nothing here.

### Behaviour the surface guarantees

| # | Guarantee | Spec |
|---|---|---|
| B1 | Every entity validates on construction; an invalid value raises rather than being carried | FR-020 |
| B2 | Every entity is immutable; assignment to a field raises | R7 |
| B3 | Serialization and re-parsing return an equal value with an equal content hash | FR-014, SC-002 |
| B4 | Re-parsing a record missing a required field, or carrying a value outside a closed vocabulary, raises an error naming the field | FR-015 |
| B5 | `document_id` is derived and cannot be supplied | FR-006, Principle II |
| B6 | No timestamp has a default; a missing one stays missing | FR-007 |
| B7 | Importing the module requires no configuration, no environment variable and no file | FR-018 |

## What it may not reach

The module's imports — direct and transitive — stay inside:

* the Python standard library;
* `pydantic`;
* `hermes_memory.normalization` itself.

Forbidden, named explicitly because these are the ones that would actually be reached for:

| Forbidden | Why |
|---|---|
| `hermes_memory.memory.*` | Principle IV: only the memory store knows Hindsight |
| `httpx`, `requests`, `urllib.request`, `aiohttp` | §8: the domain model makes no calls |
| `sqlalchemy`, `sqlite3`, `boto3` | §8: the domain model persists nothing |
| `hermes_memory.settings` | FR-018: a model that reads configuration is a model that cannot be constructed in a test |

Enforced by two tests (R12):

1. **Static** — every `.py` under `normalization/` is parsed, its import roots collected, and
   asserted to fall inside the allowlist. Names the offending line.
2. **Runtime** — a subprocess imports the module and asserts no forbidden name appears in its
   `sys.modules`. Catches what arrives transitively through a helper.

Each catches what the other misses, which is why both exist rather than either.
