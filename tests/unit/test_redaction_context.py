"""§13's standard, asserted character for character: the value goes, the sentence stays.

The easy implementation of Principle V drops the message or the tool output that matched. It is
rejected by §13 explicitly, because the surrounding sentence is what makes the memory useful — that
a 401 came from a token missing a scope, that a connection string pointed at the replica. This file
is where that is a test rather than an intention (rule RR-2, FR-003, FR-004).
"""

from __future__ import annotations

import pytest

from hermes_memory.sanitization import PatternSecretSanitizer, RedactionCategory
from hermes_memory.sanitization.scanner import REDACTED
from tests.synthetic.secrets import PEM_BEGIN, PEM_END, SAMPLES, Sample, sample_for


@pytest.fixture
def sanitizer() -> PatternSecretSanitizer:
    return PatternSecretSanitizer()


def test_the_example_of_section_thirteen_renders_exactly(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """The one line the architecture itself writes out."""
    sample = sample_for(RedactionCategory.GITLAB_TOKEN)

    redacted, _ = sanitizer.redact_text(sample.sentence)

    assert redacted == (f"GitLab request using token {REDACTED} returned HTTP 401 Unauthorized")


def test_a_dotenv_line_keeps_its_key(sanitizer: PatternSecretSanitizer) -> None:
    """`DATABASE_PASSWORD=[REDACTED]` is knowledge; a bare `[REDACTED]` is not."""
    redacted, _ = sanitizer.redact_text("DATABASE_PASSWORD=n0t-a-real-one!")

    assert redacted == f"DATABASE_PASSWORD={REDACTED}"


def test_a_pem_block_keeps_both_markers_and_loses_its_body(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """RC-9: the reader still learns a private key was there, which is often the whole point."""
    sample = sample_for(RedactionCategory.PRIVATE_KEY)

    redacted, _ = sanitizer.redact_text(sample.sentence)

    assert redacted == (
        "the deploy key pasted below stopped working:\n"
        f"{PEM_BEGIN}\n{REDACTED}\n{PEM_END}\n"
        "and ssh-add reported an invalid format"
    )


def test_a_connection_string_keeps_everything_but_the_password(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """RC-11: which database was involved is the knowledge; the password is the credential."""
    redacted, _ = sanitizer.redact_text(
        "DSN postgresql://importer:n0t-a-real-one@db.internal:5432/hermes?sslmode=require"
    )

    assert redacted == (
        f"DSN postgresql://importer:{REDACTED}@db.internal:5432/hermes?sslmode=require"
    )


def test_a_bearer_header_keeps_its_scheme(sanitizer: PatternSecretSanitizer) -> None:
    sample = sample_for(RedactionCategory.BEARER_TOKEN)

    redacted, _ = sanitizer.redact_text(sample.sentence)

    assert redacted == f"Authorization: Bearer {REDACTED} returned HTTP 403 Forbidden"


def test_a_secret_manifest_keeps_its_kind_metadata_and_keys(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """RC-13: only the value under `data:` goes — the manifest is how anyone reads the rest."""
    sample = sample_for(RedactionCategory.KUBERNETES_SECRET)

    redacted, _ = sanitizer.redact_text(sample.sentence)

    assert redacted == (
        "apiVersion: v1\n"
        "kind: Secret\n"
        "metadata:\n"
        "  name: hermes-importer\n"
        "data:\n"
        f"  api-token: {REDACTED}\n"
    )


def test_an_api_key_header_keeps_the_url_beside_it(sanitizer: PatternSecretSanitizer) -> None:
    sample = sample_for(RedactionCategory.API_KEY)

    redacted, _ = sanitizer.redact_text(sample.sentence)

    assert redacted == f'curl -H "X-API-Key: {REDACTED}" https://api.example.com/v1/jobs'


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.category.value)
def test_every_line_that_held_no_credential_survives_verbatim(
    sample: Sample, sanitizer: PatternSecretSanitizer
) -> None:
    """A message that carried words around a credential still carries them (SS-4).

    Lines that held part of the credential are excluded, because those are the lines redaction is
    supposed to change — and in the PEM case a three-line body collapses into one `[REDACTED]`,
    which is RC-9 working rather than a line going missing.
    """
    redacted, _ = sanitizer.redact_text(sample.sentence)
    value_lines = set(sample.value.splitlines())

    untouched = [
        line
        for line in sample.sentence.splitlines()
        if line not in value_lines and sample.value not in line
    ]

    assert redacted.strip()
    assert redacted != REDACTED
    for line in untouched:
        assert line in redacted
