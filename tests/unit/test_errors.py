"""The error taxonomy every boundary of ARCHITECTURE.md §8 declares against.

Contract: specs/007-boundary-interfaces/contracts/errors.md, rules E2 to E6.

The rule these tests exist for is E3: §18 names conditions that must never be retried — a rejected
request, an unauthorized one, invalid input — and FR-014 requires that they cannot be *expressed* as
retryable. A convention would leave that to whoever writes the sixth implementation at the end of a
long afternoon; a type refuses.
"""

from __future__ import annotations

import pytest

from hermes_memory.errors import BoundaryError, PermanentBoundaryError, TransientBoundaryError


def test_the_two_branches_answer_retryability_by_type() -> None:
    """E2 — a caller reads the answer from the class, never from a message (§18)."""
    assert TransientBoundaryError.retryable is True
    assert PermanentBoundaryError.retryable is False

    transient = TransientBoundaryError("memory store", "the gateway timed out")
    permanent = PermanentBoundaryError("memory store", "the request was rejected")

    assert transient.retryable is True
    assert permanent.retryable is False


def test_both_branches_are_catchable_as_one_boundary_failure() -> None:
    """E1 — #20 catches the transient branch; a reporter catches the base (§18)."""
    assert issubclass(TransientBoundaryError, BoundaryError)
    assert issubclass(PermanentBoundaryError, BoundaryError)

    with pytest.raises(BoundaryError):
        raise PermanentBoundaryError("raw archive", "the document was refused")


def test_no_constructor_accepts_a_retryable_flag() -> None:
    """E3 — the mistake is unavailable rather than discouraged (FR-014)."""
    with pytest.raises(TypeError):
        PermanentBoundaryError("memory store", "rejected", retryable=True)  # type: ignore[call-arg]


def test_retryability_cannot_be_rebound_on_an_instance() -> None:
    """E3 — a permanent failure cannot be talked into looking retryable."""
    error = PermanentBoundaryError("memory store", "the credentials were rejected")

    with pytest.raises(AttributeError):
        error.retryable = True  # type: ignore[misc]

    assert error.retryable is False


def test_an_error_carries_what_the_failure_report_needs() -> None:
    """E4 — §18 records the source id, the error and the time; the first two live here."""
    error = TransientBoundaryError(
        "conversation source",
        "the export could not be opened",
        subject="chatgpt:abc123",
    )

    assert error.boundary == "conversation source"
    assert error.subject == "chatgpt:abc123"
    assert error.message == "the export could not be opened"
    assert str(error) == "the export could not be opened"


def test_the_subject_is_optional() -> None:
    """Not every failure concerns one conversation — an unreachable export concerns none."""
    error = TransientBoundaryError("conversation source", "the export could not be reached")

    assert error.subject is None


def test_an_error_carries_nothing_beyond_those_three_fields() -> None:
    """E4 — and E5 by consequence: a field that does not exist cannot hold a secret."""
    error = PermanentBoundaryError("raw archive", "not held", subject="chatgpt:abc123")

    assert set(vars(error)) == {"boundary", "subject", "message"}


def test_an_error_does_not_timestamp_itself() -> None:
    """E6 — §18's report owns the time, and §11 forbids a captured clock standing in for one."""
    error = PermanentBoundaryError("import state", "the state file is unreadable")

    assert not any("time" in name or name.endswith("at") for name in vars(error))


def test_the_base_declares_no_retryability_of_its_own() -> None:
    """A failure is transient or permanent. The base is for catching, not for raising."""
    assert not hasattr(BoundaryError, "retryable")


def test_the_underlying_failure_is_chained_for_reading_not_for_catching() -> None:
    """E1 — a caller handles our type; the library's exception stays visible to a developer."""
    try:
        try:
            raise TimeoutError("the socket timed out")
        except TimeoutError as cause:
            raise TransientBoundaryError("memory store", "the call timed out") from cause
    except TransientBoundaryError as error:
        assert isinstance(error.__cause__, TimeoutError)
        assert "socket" not in str(error)


def test_a_subclass_cannot_redeclare_which_branch_it_is_on() -> None:
    """E3 closed from the other side: a permanent failure cannot be subclassed into a retryable one.

    Without this, `class Oops(PermanentBoundaryError): retryable = True` would be caught by a
    reporter as permanent and retried by #20 as transient — two answers to one question.
    """
    with pytest.raises(TypeError, match="retryable"):

        class Retryable(PermanentBoundaryError):
            retryable = True

    with pytest.raises(TypeError, match="retryable"):

        class NeverRetried(TransientBoundaryError):
            retryable = False
