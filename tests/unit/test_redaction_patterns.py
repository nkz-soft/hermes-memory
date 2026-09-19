"""Thirteen categories, thirteen fixtures: rules RC-1 to RC-13.

Each test asserts three things at once, because any one of them alone would pass a broken
sanitizer: the credential is gone, the sentence around it still reads, and the report names the
category §13 gives it. A sanitizer that redacts the whole line passes the first; one that redacts
nothing passes the second; one that reports everything as `api-key` passes both.

These run at the string level, against `PATTERNS` through the scanner, so a failure here is a
failure in a regular expression. Whether the *conversation* is rewritten correctly is
`test_pattern_sanitizer.py`.
"""

from __future__ import annotations

import pytest

from hermes_memory.sanitization import RedactionCategory
from hermes_memory.sanitization.patterns import PATTERNS
from hermes_memory.sanitization.scanner import REDACTED, redact
from tests.synthetic.secrets import SAMPLES, Sample, sample_for


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.category.value)
def test_the_credential_is_gone(sample: Sample) -> None:
    redacted, _ = redact(sample.sentence, PATTERNS)

    assert sample.value not in redacted
    assert REDACTED in redacted


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.category.value)
def test_the_sentence_around_it_survives(sample: Sample) -> None:
    """RR-2 and §13: the context is usually the knowledge worth keeping."""
    redacted, _ = redact(sample.sentence, PATTERNS)

    for kept in sample.kept:
        assert kept in redacted, f"{kept!r} did not survive redaction of {sample.category.value}"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.category.value)
def test_it_is_reported_under_the_category_thirteen_gives_it(sample: Sample) -> None:
    _, counts = redact(sample.sentence, PATTERNS)

    assert counts.get(sample.category, 0) >= 1, (
        f"{sample.category.value} was reported as {dict(counts)}"
    )


@pytest.mark.parametrize("category", list(RedactionCategory), ids=lambda c: c.value)
def test_every_declared_category_has_at_least_one_pattern(category: RedactionCategory) -> None:
    """A category declared in #9 and left unimplemented would be a silent hole in §13's minimum."""
    assert any(pattern.category is category for pattern in PATTERNS)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.category.value)
def test_each_sample_is_matched_by_a_pattern_of_its_own_category(sample: Sample) -> None:
    """research R11: a fixture that drifted out of its shape makes a green suite meaningless."""
    matching = [
        pattern
        for pattern in PATTERNS
        if pattern.category is sample.category and pattern.expression.search(sample.sentence)
    ]

    assert matching, f"no {sample.category.value} pattern matches its own sample"


def test_an_anthropic_key_is_not_reported_as_an_openai_key() -> None:
    """RC-6 over RC-7: `sk-ant-` is a prefix of the `sk-` family, so precedence decides (RR-6)."""
    sample = sample_for(RedactionCategory.ANTHROPIC_KEY)

    _, counts = redact(sample.sentence, PATTERNS)

    assert counts == {RedactionCategory.ANTHROPIC_KEY: 1}


def test_a_jwt_in_a_bearer_header_is_redacted_once_as_a_jwt() -> None:
    """The overlap that occurs in real history: both patterns match, one redaction happens."""
    jwt = sample_for(RedactionCategory.JWT).value

    redacted, counts = redact(f"Authorization: Bearer {jwt}", PATTERNS)

    assert redacted == f"Authorization: Bearer {REDACTED}"
    assert counts == {RedactionCategory.JWT: 1}


def test_an_aws_secret_access_key_is_redacted_when_it_is_keyed() -> None:
    """RC-8: the id is found by shape, the secret only beside its name (research R6)."""
    secret = "wJalrXUtnFEMI" + "K7MDENGbPxRfiCYEXAMPLEKEY"

    redacted, counts = redact(f"aws_secret_access_key = {secret}", PATTERNS)

    assert secret not in redacted
    assert redacted.startswith("aws_secret_access_key = ")
    assert counts == {RedactionCategory.AWS_ACCESS_KEY: 1}


def test_a_kubectl_from_literal_keeps_its_key_name() -> None:
    """RC-13's second form: the command is the knowledge, the value is the credential."""
    value = "s0me-token-value"

    redacted, counts = redact(
        f"kubectl create secret generic hermes --from-literal=api-token={value}", PATTERNS
    )

    assert value not in redacted
    assert "--from-literal=api-token=" in redacted
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


def test_the_canary_of_the_logging_redaction_is_redacted_here_too() -> None:
    """#6 and #11 must agree on what a credential looks like.

    The canary of `tests/unit/test_redaction_canary.py` is the value that feature asserts never
    reaches a log line. If this sanitizer did not recognize it, the two halves of Principle V would
    disagree about the same string.
    """
    canary = "ghp" + "_CanaryAbCdEfGhIjKlMnOpQrStUvWx0123456789"

    redacted, counts = redact(f"the token {canary} expired", PATTERNS)

    assert canary not in redacted
    assert counts == {RedactionCategory.GITHUB_TOKEN: 1}
