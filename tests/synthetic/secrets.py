"""One synthesized credential per category of ARCHITECTURE.md §13, with the sentence it sits in.

**Nothing here is a real credential, and nothing here may become one.** This repository is public
(CLAUDE.md), and a fixture is exactly where someone reproducing a bug is tempted to paste a live
token. Every value below is assembled from parts — `"ghp_" + "0" * 36` rather than the literal —
for two reasons: the source line then carries no credential-shaped string for a reader to mistake
for one, and Gitleaks, which scans this repository's full history on every pull request (#7), does
not have to be taught an exemption for each fixture. The values are still of the documented shape at
runtime, and `test_redaction_patterns.py` asserts that each one is matched by the pattern it is a
sample of (specs/009-secret-sanitizer/research.md R11).

`kept` is the other half of each sample and the reason this feature is not "delete the line": it
lists what must still be readable after redaction (§13, rule RR-2).
"""

from __future__ import annotations

from dataclasses import dataclass

from hermes_memory.sanitization import RedactionCategory

__all__ = ["SAMPLES", "Sample", "sample_for"]


@dataclass(frozen=True, slots=True)
class Sample:
    """A synthesized credential, the text around it, and what must survive redaction."""

    category: RedactionCategory
    value: str
    """The credential itself, as it would appear in a message."""

    sentence: str
    """A realistic line containing `value`."""

    kept: tuple[str, ...]
    """Substrings of `sentence` that must still be present after sanitization (RR-2)."""


_BASE62 = "0aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT"
"""A short alphabet to build from. Repeated and sliced, never a value anyone could mistake."""


def _filler(length: int) -> str:
    return (_BASE62 * (length // len(_BASE62) + 1))[:length]


_API_KEY = "ak" + "_" + _filler(32)
_BEARER = _filler(40)
_JWT = ".".join(
    (
        "eyJ" + _filler(17),
        "eyJ" + _filler(21),
        _filler(43),
    )
)
_GITHUB = "ghp" + "_" + _filler(36)
_GITLAB = "glpat" + "-" + _filler(20)
_ANTHROPIC = "sk" + "-ant-api03-" + _filler(40)
_OPENAI = "sk" + "-" + _filler(48)
_AWS_ID = "AKIA" + "Q7B4TYZ3KJ6MNP5X"
_AWS_SECRET = _filler(40)
_PRIVATE_KEY_BODY = "\n".join(_filler(64) for _ in range(3))
PEM_BEGIN = "-----BEGIN " + "OPENSSH PRIVATE" + " KEY-----"
PEM_END = "-----END " + "OPENSSH PRIVATE" + " KEY-----"
"""Assembled rather than written whole, so no line in this file is a PEM header to a scanner."""

_PASSWORD = "n0t-a-real-one!"
_DB_PASSWORD = "n0t-a-real-one-either!"
_DOTENV = _filler(36)
_K8S = _filler(24)

SAMPLES: tuple[Sample, ...] = (
    Sample(
        category=RedactionCategory.API_KEY,
        value=_API_KEY,
        sentence=f'curl -H "X-API-Key: {_API_KEY}" https://api.example.com/v1/jobs',
        kept=("X-API-Key:", "https://api.example.com/v1/jobs"),
    ),
    Sample(
        category=RedactionCategory.BEARER_TOKEN,
        value=_BEARER,
        sentence=f"Authorization: Bearer {_BEARER} returned HTTP 403 Forbidden",
        kept=("Authorization: Bearer", "HTTP 403 Forbidden"),
    ),
    Sample(
        category=RedactionCategory.JWT,
        value=_JWT,
        sentence=f"the gateway rejected the token {_JWT} as expired",
        kept=("the gateway rejected the token", "as expired"),
    ),
    Sample(
        category=RedactionCategory.GITHUB_TOKEN,
        value=_GITHUB,
        sentence=f"push failed with {_GITHUB}: the token has no workflow scope",
        kept=("push failed with", "the token has no workflow scope"),
    ),
    Sample(
        category=RedactionCategory.GITLAB_TOKEN,
        value=_GITLAB,
        sentence=f"GitLab request using token {_GITLAB} returned HTTP 401 Unauthorized",
        kept=("GitLab request using token", "returned HTTP 401 Unauthorized"),
    ),
    Sample(
        category=RedactionCategory.ANTHROPIC_KEY,
        value=_ANTHROPIC,
        sentence=f"ANTHROPIC_API_KEY was set to {_ANTHROPIC} in the wrong shell",
        kept=("ANTHROPIC_API_KEY", "in the wrong shell"),
    ),
    Sample(
        category=RedactionCategory.OPENAI_KEY,
        value=_OPENAI,
        sentence=f"the client was constructed with {_OPENAI} and hit a 429",
        kept=("the client was constructed with", "and hit a 429"),
    ),
    Sample(
        category=RedactionCategory.AWS_ACCESS_KEY,
        value=_AWS_ID,
        sentence=f"aws sts get-caller-identity for {_AWS_ID} says the key is inactive",
        kept=("aws sts get-caller-identity for", "says the key is inactive"),
    ),
    Sample(
        category=RedactionCategory.PRIVATE_KEY,
        value=_PRIVATE_KEY_BODY,
        sentence=(
            "the deploy key pasted below stopped working:\n"
            f"{PEM_BEGIN}\n"
            f"{_PRIVATE_KEY_BODY}\n"
            f"{PEM_END}\n"
            "and ssh-add reported an invalid format"
        ),
        kept=(
            "the deploy key pasted below stopped working:",
            PEM_BEGIN,
            PEM_END,
            "and ssh-add reported an invalid format",
        ),
    ),
    Sample(
        category=RedactionCategory.PASSWORD,
        value=_PASSWORD,
        sentence=f"the compose file had password={_PASSWORD} and the healthcheck still failed",
        kept=("password=", "and the healthcheck still failed"),
    ),
    Sample(
        category=RedactionCategory.CONNECTION_STRING,
        value=_DB_PASSWORD,
        sentence=(
            f"DSN postgresql://importer:{_DB_PASSWORD}@db.internal:5432/hermes "
            "pointed at the replica"
        ),
        kept=("postgresql://importer:", "@db.internal:5432/hermes", "pointed at the replica"),
    ),
    Sample(
        category=RedactionCategory.DOTENV_VALUE,
        value=_DOTENV,
        sentence=f"HINDSIGHT_API_TOKEN={_DOTENV}\nHINDSIGHT_BASE_URL=http://localhost:8000",
        kept=("HINDSIGHT_API_TOKEN=", "HINDSIGHT_BASE_URL=http://localhost:8000"),
    ),
    Sample(
        category=RedactionCategory.KUBERNETES_SECRET,
        value=_K8S,
        sentence=(
            "apiVersion: v1\n"
            "kind: Secret\n"
            "metadata:\n"
            "  name: hermes-importer\n"
            "data:\n"
            f"  api-token: {_K8S}\n"
        ),
        kept=("kind: Secret", "name: hermes-importer", "api-token:"),
    ),
)

_BY_CATEGORY = {sample.category: sample for sample in SAMPLES}


def sample_for(category: RedactionCategory) -> Sample:
    """The sample for one category, for a test that wants a specific shape."""
    return _BY_CATEGORY[category]


CONTRACT_SAMPLE = _BY_CATEGORY[RedactionCategory.GITLAB_TOKEN]
"""What the boundary contract suite is given.

A value-shaped credential, because the suite puts it in an attachment name (`{secret}.env`) and in a
title, where there is no key beside it for a keyed pattern to anchor on.
"""
