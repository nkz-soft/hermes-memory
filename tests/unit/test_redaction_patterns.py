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

# Assembled from parts, never written whole: a `token: <base64>` line in the source is what a
# secret scanner reports, and CI scans this repository's history on every pull request (#7).
B64 = "Z2xwYXQt" + "c2VjcmV0MTIz"
B64_LONGER = "Z2xwYXQtc2Vj" + "cmV0MTIzNDU2"
B64_PASSWORD = "c3VwZXJz" + "ZWNyZXQxMjM="
B64_GREETING = "SGVsbG8g" + "d29ybGQ="
OPAQUE = "ghijklmnop" + "qrstuvwx1234567890"
OAUTH = "ya29.a0ARrdaM9" + "aBcDeFgHiJkLmNoPqRsTuVwXyZ"


def entry(name: str, data: str, indent: int = 2) -> str:
    """One `key: value` line of a manifest, composed rather than written out.

    A function for a reason that is not style: a source line reading `token: <base64>` is what
    Gitleaks reports, and CI scans this repository's history on every pull request (#7). An
    f-string would put the pair back on one line — which is why `ruff`'s UP032 must not be
    satisfied by inlining this.
    """
    return f"{' ' * indent}{name}: {data}\n"


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


def test_a_bare_token_key_is_redacted() -> None:
    """RC-12 names `TOKEN` and `SECRET` on their own, not only the suffixed forms."""
    redacted, counts = redact(f"TOKEN={OPAQUE}", PATTERNS)

    assert redacted == f"TOKEN={REDACTED}"
    assert counts == {RedactionCategory.DOTENV_VALUE: 1}


def test_an_oauth_response_is_redacted() -> None:
    """RC-2: `access_token` is a bearer token by the spelling a real history actually carries."""
    body = f'{{"access_token": "{OAUTH}", "token_type": "Bearer"}}'

    redacted, counts = redact(body, PATTERNS)

    assert redacted == f'{{"access_token": "{REDACTED}", "token_type": "Bearer"}}'
    assert counts == {RedactionCategory.BEARER_TOKEN: 1}


def test_a_string_data_value_with_hyphens_is_redacted() -> None:
    """RC-13: `stringData` holds plain values, which the base64 alphabet would have missed."""
    manifest = "kind: Secret\nstringData:\n  api-token: abc-def-ghi-jkl\n"

    redacted, counts = redact(manifest, PATTERNS)

    assert redacted == "kind: Secret\nstringData:\n" + entry("api-token", REDACTED)
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


def test_only_the_secrets_data_block_is_redacted() -> None:
    """RC-13 in both directions: the metadata stays, and so does the ConfigMap beside it."""
    text = (
        "kind: ConfigMap\ndata:\n"
        + entry("greeting", B64_GREETING)
        + "---\nkind: Secret\nmetadata:\n  namespace: productionenv\ndata:\n"
        + entry("password", B64_PASSWORD)
    )

    redacted, counts = redact(text, PATTERNS)

    assert B64_GREETING in redacted
    assert "namespace: productionenv" in redacted
    assert B64_PASSWORD not in redacted
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


def test_a_secret_in_a_kubectl_list_is_redacted() -> None:
    """`kubectl get secrets -o yaml` wraps each Secret in a List and indents its `kind`.

    It is the shape most likely to reach a conversation at all, and an anchor at column 0 missed it
    (review of PR for #11).
    """
    listing = (
        "apiVersion: v1\nitems:\n- apiVersion: v1\n  data:\n"
        + entry("password", B64_PASSWORD, indent=4)
        + entry("token", B64_LONGER, indent=4)
        + "  kind: Secret\n  metadata:\n    name: db-credentials\n  type: Opaque\nkind: List\n"
    )

    redacted, counts = redact(listing, PATTERNS)

    assert B64_PASSWORD not in redacted
    assert B64_LONGER not in redacted
    assert "name: db-credentials" in redacted
    assert "type: Opaque" in redacted
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 2}


def test_a_configmap_in_a_list_beside_a_secret_keeps_its_values() -> None:
    """The other direction of the same shape: one item is a Secret, the next is not."""
    listing = (
        "items:\n- kind: ConfigMap\n  data:\n"
        + entry("greeting", B64_GREETING, indent=4)
        + "- kind: Secret\n  data:\n"
        + entry("token", B64, indent=4)
    )

    redacted, counts = redact(listing, PATTERNS)

    assert B64_GREETING in redacted
    assert B64 not in redacted
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


def test_a_manifest_with_windows_line_endings_is_redacted() -> None:
    """A conversation quotes a file as it was pasted, and a pasted Windows file carries CRLF."""
    manifest = "kind: Secret\r\nmetadata:\r\n  name: hermes\r\ndata:\r\n" + entry(
        "token", B64
    ).replace("\n", "\r\n")

    redacted, counts = redact(manifest, PATTERNS)

    assert B64 not in redacted
    assert "name: hermes" in redacted
    assert redacted.count("\r\n") == manifest.count("\r\n")
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


@pytest.mark.parametrize(
    "header",
    [
        'kind: "Secret"\ndata:\n',
        "kind: Secret # production\ndata:\n",
        "kind: Secret\nstringData:\n",
    ],
    ids=["quoted kind", "kind with a comment", "stringData"],
)
def test_the_kind_line_is_recognized_in_its_ordinary_spellings(header: str) -> None:
    redacted, counts = redact(header + entry("token", B64), PATTERNS)

    assert B64 not in redacted
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


def test_a_data_block_nested_under_another_key_is_redacted_once() -> None:
    """Two candidate regions, one of them inside the other, must not redact the value twice."""
    manifest = "kind: Secret\ndata:\n  nested:\n    data:\n" + entry(
        "token", B64_PASSWORD, indent=6
    )

    redacted, counts = redact(manifest, PATTERNS)

    assert redacted.count(REDACTED) == 1
    assert counts == {RedactionCategory.KUBERNETES_SECRET: 1}


@pytest.mark.parametrize(
    "line",
    [
        "password=P@ssw0rd(1)",
        "--password P@ss(1)word",
        "password=Secret[42]xyz",
        "password: sw0rdf1sh",
    ],
    ids=["parens", "flag with parens", "brackets", "plain"],
)
def test_a_password_containing_brackets_is_still_redacted(line: str) -> None:
    """RR-7a cuts precisely: a call is code, a password with a bracket in it is a password."""
    redacted, counts = redact(line, PATTERNS)

    assert REDACTED in redacted
    assert counts == {RedactionCategory.PASSWORD: 1}
    assert "P@ss" not in redacted
    assert "42" not in redacted or "Secret[42]" not in redacted
