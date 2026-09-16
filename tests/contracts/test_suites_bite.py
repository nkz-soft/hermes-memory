"""Every suite is watched failing (FR-020, SC-003).

One test per boundary. Each wires a deliberately broken implementation into its suite, calls the
rule that should reject it, and insists the rejection happens. The rule that was broken is named in
the test, so a reader can check the mapping against
specs/007-boundary-interfaces/contracts/contract-suites.md rather than trusting it.

The suite methods are called directly rather than through a nested pytest session: it is cheaper,
it is readable, and it is how this repository already proves a guard bites
(``test_the_behaviour_guard_still_bites``).
"""

from __future__ import annotations

import pytest

from hermes_memory.errors import BoundaryError
from tests.contracts import conversations as conversations_module
from tests.contracts.archive import RawArchiveContract
from tests.contracts.classifier import ProjectClassifierContract
from tests.contracts.sanitizer import SecretSanitizerContract
from tests.contracts.source import ConversationSourceContract
from tests.contracts.state import ImportStateContract
from tests.contracts.store import MemoryStoreContract
from tests.fakes import broken


class _BrokenSource(ConversationSourceContract):
    def make_source(self, conversations):
        return broken.SourceThatStopsAtTheFirstBadConversation(
            conversations_module.as_read(*conversations), frozenset()
        )

    def make_source_with_one_unreadable(self, conversations):
        return broken.SourceThatStopsAtTheFirstBadConversation(
            conversations_module.as_read(*conversations),
            frozenset({conversations[1].source_id}),
        )


class _BrokenSanitizer(SecretSanitizerContract):
    def make_sanitizer(self):
        return broken.SanitizerThatReportsWhatItDidNotDo()

    def secret_sample(self):
        from hermes_memory.sanitization import RedactionCategory

        return conversations_module.FAKE_SECRET, RedactionCategory.PASSWORD


class _BrokenClassifier(ProjectClassifierContract):
    def make_classifier(self):
        return broken.ClassifierThatRaisesInsteadOfAnsweringUnknown()


class _BrokenArchive(RawArchiveContract):
    def make_archive(self):
        return broken.ArchiveThatDropsMessageTimestamps()


class _BrokenStore(MemoryStoreContract):
    def make_store(self):
        return broken.StoreThatAppendsOnEveryRetain()


class _BrokenState(ImportStateContract):
    def make_state(self):
        return broken.StateThatRemembersOnlySuccesses()


def test_cs5_catches_a_source_that_stops_at_the_first_bad_conversation() -> None:
    """A generator is the obvious implementation, and §18 forbids it here."""
    with pytest.raises(AssertionError):
        _BrokenSource().test_cs5_one_unreadable_conversation_does_not_end_the_iteration()


def test_ss3_catches_a_sanitizer_that_reports_what_it_did_not_do() -> None:
    """The report looks compliant; the credential is still in the text (Principle V)."""
    with pytest.raises(AssertionError):
        _BrokenSanitizer().test_ss3_the_secret_is_gone_from_everything_that_leaves_the_sanitizer()


def test_pc2_and_pc5_catch_a_classifier_that_raises_instead_of_answering_unknown() -> None:
    """§15 makes the unresolved project ordinary; PC-5 is the rule that says so in the taxonomy."""
    with pytest.raises(BoundaryError):
        _BrokenClassifier().test_pc2_no_match_is_project_unknown_rather_than_a_failure()

    with pytest.raises(AssertionError):
        _BrokenClassifier().test_pc5_classification_raises_no_boundary_error()


def test_ra1_catches_an_archive_that_drops_message_timestamps() -> None:
    """The loss parses fine and replays wrong, years later (Principle I)."""
    with pytest.raises(AssertionError):
        _BrokenArchive().test_ra1_the_normalized_form_comes_back_equal()


def test_ms2_catches_a_store_that_appends_on_every_retain() -> None:
    """Principle II — the re-import that fills the bank with the same conversation twice."""
    with pytest.raises(AssertionError):
        _BrokenStore().test_ms2_retaining_the_same_conversation_twice_creates_no_duplicate()


def test_is4_catches_an_import_state_that_remembers_only_successes() -> None:
    """§18 — a failed import that looks like one never attempted strands the conversation."""
    with pytest.raises(AssertionError):
        _BrokenState().test_is4_a_failure_is_remembered_and_is_not_the_same_as_nothing()
