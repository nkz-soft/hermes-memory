"""Every field of the normalized model is either scanned for secrets or knowingly copied.

The rewriter visits named fields rather than walking every string it meets, because a generic walk
would redact `source_id` and so move `document_id` — Principle II's stable identity — the first time
a native id looked like a token (specs/009-secret-sanitizer/research.md R1).

The cost of naming fields is that a field added to #8's model later could be forgotten. That cost is
paid here: this test partitions each model's fields by the two lists the rewriter declares, and a
field in neither fails it. Whoever adds the field is told, in the commit that adds it, which side of
the line it falls on (rule RR-3).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from hermes_memory.normalization import Conversation, Message, NonTextPart, ToolActivity
from hermes_memory.sanitization.pattern_sanitizer import COPIED_FIELDS, SCANNED_FIELDS

MODELS: tuple[type[BaseModel], ...] = (Conversation, Message, ToolActivity, NonTextPart)


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_every_field_is_accounted_for(model: type[BaseModel]) -> None:
    scanned = SCANNED_FIELDS[model.__name__]
    copied = COPIED_FIELDS[model.__name__]

    unaccounted = set(model.model_fields) - scanned - copied

    assert not unaccounted, (
        f"{model.__name__} has fields the sanitizer neither scans nor copies: "
        f"{sorted(unaccounted)}. Add each to SCANNED_FIELDS if it can carry text a person wrote, "
        "or to COPIED_FIELDS if it is identity, structure or an enum (RR-3, RR-4)."
    )


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_no_field_is_on_both_lists(model: type[BaseModel]) -> None:
    both = SCANNED_FIELDS[model.__name__] & COPIED_FIELDS[model.__name__]

    assert not both, f"{model.__name__}: {sorted(both)} is both scanned and copied"


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_neither_list_names_a_field_that_does_not_exist(model: type[BaseModel]) -> None:
    """A list that drifted from the model would pass the partition test while enforcing nothing."""
    named = SCANNED_FIELDS[model.__name__] | COPIED_FIELDS[model.__name__]

    assert not named - set(model.model_fields)


def test_identity_is_on_the_copied_side() -> None:
    """The specific fields research R1 is about, asserted by name."""
    assert {"source", "source_id"} <= COPIED_FIELDS["Conversation"]
    assert "title" in SCANNED_FIELDS["Conversation"]
