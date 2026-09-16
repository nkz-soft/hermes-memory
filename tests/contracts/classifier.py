"""The contract every project classifier must satisfy (ARCHITECTURE.md §8, row 3).

Rules PC-1 to PC-5 of specs/007-boundary-interfaces/contracts/contract-suites.md.

The rule worth reading is PC-5: this boundary declares no error, and the suite asserts that none is
raised. §15 says a substantial share of conversations will not resolve to a project, and that they
are imported anyway under `project:unknown` — so the unresolved case is the common case, and a
classifier that raised would make the pipeline's failure path its ordinary path.
"""

from __future__ import annotations

from hermes_memory.classification import UNKNOWN_PROJECT, ProjectClassifier
from hermes_memory.errors import BoundaryError
from hermes_memory.normalization import Conversation, ProjectTag
from tests.contracts import conversations


class ProjectClassifierContract:
    """Subclass this and implement `make_classifier`."""

    # --- what a subclass supplies ---------------------------------------------------------------

    def make_classifier(self) -> ProjectClassifier:
        raise NotImplementedError

    def unmatched_conversation(self) -> Conversation:
        """A conversation this classifier resolves no project for.

        Override where the default happens to match.
        """
        return conversations.conversation(
            "unmatched1",
            title="A question about nothing in particular",
            text="What is the difference between a duck?",
        )

    def classifiable_conversations(self) -> tuple[Conversation, ...]:
        """Conversations this classifier is expected to cope with. Override to widen the sweep."""
        return (
            conversations.conversation(),
            conversations.conversation_using_every_field(),
            self.unmatched_conversation(),
        )

    # --- the contract ---------------------------------------------------------------------------

    def test_pc1_every_call_returns_a_project_tag(self) -> None:
        classifier = self.make_classifier()

        for conversation in self.classifiable_conversations():
            assert isinstance(classifier.classify(conversation), ProjectTag)

    def test_pc2_no_match_is_project_unknown_rather_than_a_failure(self) -> None:
        """§15 — an answer with a value, not a missing one (ADR-002 keeps it retrievable)."""
        classified = self.make_classifier().classify(self.unmatched_conversation())

        assert classified == UNKNOWN_PROJECT
        assert str(classified) == "project:unknown"

    def test_pc3_classification_is_deterministic(self) -> None:
        classifier = self.make_classifier()

        for conversation in self.classifiable_conversations():
            assert classifier.classify(conversation) == classifier.classify(conversation)

    def test_pc4_the_conversation_is_left_alone(self) -> None:
        conversation = conversations.conversation()
        before = conversation.model_copy(deep=True)

        self.make_classifier().classify(conversation)

        assert conversation == before

    def test_pc5_classification_raises_no_boundary_error(self) -> None:
        classifier = self.make_classifier()

        for conversation in self.classifiable_conversations():
            try:
                classifier.classify(conversation)
            except BoundaryError as raised:  # pragma: no cover - the failure path is the assertion
                raise AssertionError(
                    f"the classifier raised {raised!r}; §15 makes the unresolved project an "
                    "ordinary answer, so this boundary declares no error (contracts/errors.md E8)"
                ) from raised
