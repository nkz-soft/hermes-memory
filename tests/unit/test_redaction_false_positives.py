"""Ordinary engineering content is not a credential.

The corpus is mostly this: hex digests, UUIDs, base64 fragments, example `curl` lines, a quoted
docker-compose file, the word `password` in a sentence. A sanitizer tuned only for recall redacts
them too, and the result is a corpus of `[REDACTED]` where the knowledge used to be — a quieter
version of the failure §13 rejects by refusing to drop the enclosing text.

Each case asserts the conversation comes back **equal** to the input, not merely free of a secret:
a test that only checked for absence would pass on a sanitizer that redacted the whole line
(FR-015, SC-002).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_memory.normalization import Conversation, Message, Role, Source
from hermes_memory.sanitization import PatternSecretSanitizer

STARTED_AT = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)

UNTOUCHED = {
    "a commit sha": "the regression landed in 9f3c2a7e51b04d6fa8e1c3b7d2409e5a6b8c1d2e",
    "a short sha": "git show 4c54f84 explains the change",
    "a uuid": "the run id was 3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "a hex digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "a base64 fragment": "the payload began iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ",
    "a version string": "we pinned pydantic 2.9.2 and structlog 24.4.0",
    "a dotted path": "the traceback pointed at hermes_memory.ingestion.chatgpt.records",
    "a bearer with a variable": 'curl -H "Authorization: Bearer $TOKEN" https://example.com',
    "a bearer with a template": "Authorization: Bearer {{ gitlab_token }}",
    "a documentation placeholder": "set api_key=<your-api-key> before running it",
    "a masked value": "the config showed api_key=*** which told us nothing",
    "a variable reference": "PASSWORD=$DB_PASSWORD is what the compose file had",
    "an empty assignment": 'HINDSIGHT_API_TOKEN=""',
    "the word password": "the password reset flow sends one email too many",
    "a password column": "the users table has a password column and a created_at column",
    "an already sanitized line": "HINDSIGHT_API_TOKEN=[REDACTED]",
    "a configmap": (
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: hermes-importer\n"
        "data:\n"
        "  logLevel: aW5mbw==\n"
    ),
    "a short sk word": "we wrote sk-notes in the shared doc",
    # The five below are the shapes a review found redacted into syntactically broken code. A
    # redaction that breaks the line destroys the context §13 exists to protect, which makes it
    # worse than an ordinary false positive.
    "a getenv call": 'api_key = os.getenv("OPENAI_API_KEY")',
    "a subscript": 'password = os.environ["DB_PASSWORD"]',
    "a function call": "const apiKey = getApiKey();",
    "a type declaration": "interface Credentials {\n  username: string;\n  password: string;\n}",
    "a sql column type": "ALTER TABLE users ADD COLUMN password varchar(72) NOT NULL;",
    "a configmap beside a secret": (
        "kind: ConfigMap\ndata:\n  greeting: SGVsbG8gd29ybGQhIQ==\n---\nkind: Secret\nmetadata:\n"
        "  name: unrelated\n"
    ),
    "an aws arn": "arn:aws:s3:::hermes-archive/chatgpt/2026/03/04",
    "a forty character base64 word": "the digest was wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEYX",
    "an example dsn without credentials": "postgresql://db.internal:5432/hermes is the DSN",
    "a url with a port": "the proxy listens on http://localhost:4000/v1 in development",
}
"""Each value must survive sanitization untouched. The name is the test's id."""


@pytest.fixture
def sanitizer() -> PatternSecretSanitizer:
    return PatternSecretSanitizer()


def conversation(text: str) -> Conversation:
    return Conversation(
        source=Source.CHATGPT,
        source_id="ordinary1",
        title="An ordinary conversation",
        started_at=STARTED_AT,
        messages=(Message(role=Role.ASSISTANT, text=text, sent_at=STARTED_AT),),
    )


@pytest.mark.parametrize("text", UNTOUCHED.values(), ids=list(UNTOUCHED))
def test_ordinary_content_is_returned_unchanged(
    text: str, sanitizer: PatternSecretSanitizer
) -> None:
    original = conversation(text)

    sanitized, report = sanitizer.sanitize(original)

    assert sanitized == original
    assert report.is_empty


def test_a_whole_ordinary_conversation_reports_nothing(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """All of them at once, in one conversation, as a run over real history would meet them."""
    original = Conversation(
        source=Source.CHATGPT,
        source_id="ordinary2",
        title="An ordinary conversation",
        started_at=STARTED_AT,
        messages=tuple(
            Message(role=Role.ASSISTANT, text=text, sent_at=STARTED_AT)
            for text in UNTOUCHED.values()
        ),
    )

    sanitized, report = sanitizer.sanitize(original)

    assert sanitized == original
    assert report.is_empty
