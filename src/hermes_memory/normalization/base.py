"""Value semantics shared by every entity in the normalized conversation model.

Three things live here because all three entities need all three, and because putting them in any
one of `conversation.py`, `provenance.py` or `tags.py` would make the other two import that file
for a reason unrelated to what it is about (research.md R14).

Nothing in this module — or in any module beside it — may import Hindsight, HTTP or storage
(ARCHITECTURE.md §8, Principle IV). `tests/structure/test_normalization_boundary.py` enforces it.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, StringConstraints

__all__ = ["FrozenModel", "OpaqueIdentifier", "Slug", "Timestamp"]


class FrozenModel(BaseModel):
    """An immutable value that carries exactly the fields it declares.

    `frozen=True` means a conversation's content hash cannot go stale in the hand of a caller who
    mutated a message after computing it, and that the pipeline stages of ARCHITECTURE.md §7 are
    composable in the sense Principle IV asks for: each returns a new conversation rather than
    editing its argument, so a sanitizer cannot leave a half-redacted object behind on failure.

    `extra="forbid"` means a record from the raw archive that carries a field this model does not
    know fails loudly instead of parsing into an object that silently lost it (FR-015). In an
    archive that is the source of truth (Principle I), a quiet loss is the expensive kind.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


_UNUSABLE_IN_AN_IDENTIFIER = re.compile(r"[\s\x00-\x1f\x7f]")


def _reject_unusable_identifier(value: str) -> str:
    if _UNUSABLE_IN_AN_IDENTIFIER.search(value):
        raise ValueError(
            f"an identifier must contain no whitespace and no control character, got {value!r}"
        )
    return value


OpaqueIdentifier = Annotated[
    str,
    StringConstraints(min_length=1),
    # Not a pattern, so that the message says which rule was broken rather than printing a regex.
    AfterValidator(_reject_unusable_identifier),
]
"""An identifier minted by a source, carried verbatim.

What a source calls its conversations is the source's business, so the only rules are the two that
would make the value unusable rather than merely unfamiliar: it is not empty, and it survives a log
line or a URL without being trimmed into a different identifier.

A colon is deliberately allowed. `document_id` is `<source>:<native id>` (ARCHITECTURE.md §10) and
is never split back apart, so a colon inside the native id changes nothing (research.md R10).
"""


Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
"""A lowercase name used to scope memory — a project or a user (ARCHITECTURE.md §6).

Tags are the only scoping mechanism there is, and a typo in one does not fail: it files a
conversation where nobody will look for it. Hence a closed shape rather than a free string. `:` is
excluded in particular, because a slug containing one would forge a second namespace when the tag
is rendered (research.md R9).
"""


Timestamp = AwareDatetime
"""A moment in time that knows its offset.

Naive datetimes are refused everywhere in this model. The canonical form converts to UTC before
hashing (research.md R4), so a time without an offset is a hash that depends on where the code ran
— and by the time that is noticed, the original offset is gone (FR-008).
"""
