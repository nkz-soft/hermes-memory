"""A credential does not escape by being given an innocuous name (User Story 2).

Checks 11-18 of specs/003-logging-telemetry-baseline/contracts/observability.md: secret-typed
values, the shape roster, nesting, depth, exceptions, fail-closed behaviour and cycles.

Every credential below is a literal invented here. Nothing in this suite needs a real one, and CI
runs on fork pull requests, so a repository secret must never be what makes it pass.

The shape roster is the last line of defence for a log line — not a secret scanner.
ARCHITECTURE.md §13's sanitizer is what protects conversation content on its way to the memory
engine, and nothing here may be mistaken for it (research.md R7).
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from hermes_memory.observability import REDACTED, get_logger
from hermes_memory.observability.redaction import MAX_DEPTH

from .conftest import Rendered

A_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
SHAPES = {
    "bearer": "Bearer aaaa1111bbbb2222cccc3333dddd4444",
    "basic": "Basic YWxhZGRpbjpvcGVuc2VzYW1l",
    "jwt": A_JWT,
    "openai_key": "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
    "anthropic_key": "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
    "github_token": "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
    "url_userinfo": "https://importer:hunter2ampersand@proxy.internal:8443/v1",
}
"""One value per shape on the roster, each under a field name that gives nothing away."""


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_credential_shape_is_withheld(rendered: Rendered, shape: str) -> None:
    """Check 12 — the value does not survive, whatever the field is called (FR-011)."""
    value = SHAPES[shape]

    get_logger().info("calling the proxy", note=value)

    assert value not in rendered.text()


def test_only_the_matched_span_is_replaced(rendered: Rendered) -> None:
    """Check 12, second half — Principle V redacts the value and keeps the context around it."""
    get_logger().info(
        "the proxy refused",
        note=f"tried {SHAPES['url_userinfo']} and it returned 403 after 2 retries",
    )

    note = rendered.one()["note"]

    assert "hunter2ampersand" not in note
    assert note.startswith("tried ")
    assert "it returned 403 after 2 retries" in note


def test_a_secret_typed_value_is_withheld_whatever_the_field_is_named(rendered: Rendered) -> None:
    """Check 11 — 002 made every credential a `SecretStr`; this is what that buys here (FR-010)."""
    get_logger().info("loaded settings", note=SecretStr("not-shaped-like-anything-in-particular"))

    assert "not-shaped-like-anything-in-particular" not in rendered.text()
    assert rendered.one()["note"] == REDACTED


def test_a_credential_nested_deep_in_a_structure_is_withheld(rendered: Rendered) -> None:
    """Check 13 — a mapping inside a list inside a mapping (FR-012).

    The realistic case: logging a request as the client assembled it, headers and all.
    """
    get_logger().info(
        "retrying",
        request={"attempts": [{"headers": {"Authorization": "Bearer abc123def456ghi789"}}]},
    )

    text = rendered.text()

    assert "abc123def456ghi789" not in text
    assert REDACTED in text


def test_a_value_past_the_depth_limit_is_withheld_rather_than_emitted(rendered: Rendered) -> None:
    """Check 14 — the limit fails closed, which is the only safe direction (FR-012)."""
    value: object = "a-value-at-the-bottom"
    for _ in range(MAX_DEPTH + 2):
        value = {"deeper": value}

    get_logger().info("deeply nested", payload=value)

    assert "a-value-at-the-bottom" not in rendered.text()


def test_a_cyclic_structure_terminates(rendered: Rendered) -> None:
    """Check 18 — the depth limit covers cycles, so no visited-set is needed (R9)."""
    cycle: dict[str, object] = {"name": "loop"}
    cycle["self"] = cycle

    get_logger().info("cyclic", payload=cycle)

    assert rendered.one()["event"] == "cyclic"


def test_a_credential_in_an_exception_message_does_not_appear(rendered: Rendered) -> None:
    """Check 15 — the traceback is rendered before redaction precisely so this works (FR-016).

    An exception carrying a credential in its message is ordinary: an HTTP client raising with the
    request URL in it does exactly this.
    """
    try:
        raise RuntimeError(f"POST {SHAPES['url_userinfo']} failed")
    except RuntimeError:
        get_logger().exception("the request failed")

    assert "hunter2ampersand" not in rendered.text()


def test_a_credential_in_exception_arguments_does_not_appear(rendered: Rendered) -> None:
    """The same claim through `exc_info`, which renders arguments as well as the message."""
    try:
        raise ValueError(SHAPES["jwt"])
    except ValueError as error:
        get_logger().error("rejected", exc_info=error)

    assert A_JWT not in rendered.text()


class Unrenderable:
    """An object whose inspection raises, which is the case fail-closed exists for."""

    def __repr__(self) -> str:
        raise RuntimeError("this object refuses to be rendered")


def test_a_value_that_cannot_be_inspected_is_withheld_and_the_record_survives(
    rendered: Rendered,
) -> None:
    """Check 17 — the record is still emitted and the logging call does not raise (FR-017).

    Both failure directions are wrong: a redactor that raises takes down the caller, and one that
    gives up and emits has leaked.
    """
    get_logger().info("odd payload", payload=Unrenderable(), source="chatgpt")

    record = rendered.one()

    assert record["payload"] == REDACTED
    assert record["source"] == "chatgpt"
    assert record["event"] == "odd payload"


class HoldsAToken:
    """An object whose `repr` carries a credential — the reason `repr` output is shape-scanned."""

    def __repr__(self) -> str:
        return f"HoldsAToken(token={SHAPES['github_token']!r})"


def test_an_unknown_object_is_rendered_but_its_repr_is_still_scanned(rendered: Rendered) -> None:
    """R9 — dropping unknown objects would lose diagnostics; emitting them raw would leak."""
    get_logger().info("odd payload", payload=HoldsAToken())

    text = rendered.text()

    assert SHAPES["github_token"] not in text
    assert "HoldsAToken" in text, "the object should still be identifiable in the record"


def test_a_credential_in_a_sequence_is_withheld(rendered: Rendered) -> None:
    """Lists are walked like mappings; a header list is an ordinary way to log a request."""
    get_logger().info("retrying", headers=["Accept: application/json", f"Authorization: {A_JWT}"])

    assert A_JWT not in rendered.text()


def test_the_standard_library_path_is_redacted_too(
    rendered: Rendered, complete_environment: dict[str, str]
) -> None:
    """FR-001 and R5 — httpx logging a URL with credentials in it is the realistic leak."""
    import logging as stdlib_logging

    from hermes_memory.observability import configure
    from hermes_memory.settings import load_settings

    configure(load_settings(env_file=None))

    stdlib_logging.getLogger("httpx").warning("GET %s failed", SHAPES["url_userinfo"])

    assert "hunter2ampersand" not in rendered.text()
