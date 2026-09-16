"""The six types the boundaries own, and the rules they validate on construction.

#8 defined everything that describes a conversation, and its SC-001 reserved exactly this space: a
boundary may own a type the model deliberately does not define, as long as it does not invent a
second way of describing a conversation. These are those types
(specs/007-boundary-interfaces/data-model.md).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from hermes_memory.archive import OriginalPayload
from hermes_memory.ingestion import ImportRecord, ImportStatus
from hermes_memory.memory.interface import RecallResult
from hermes_memory.normalization import Provenance, Source
from hermes_memory.sanitization import RedactionCategory, RedactionReport

NOW = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)


def provenance() -> Provenance:
    return Provenance(
        source=Source.CHATGPT,
        source_id="abc123",
        project="hermes-memory",
        imported_at=NOW,
        importer_version="1",
    )


class TestRedactionReport:
    """§13 by way of contracts/errors.md and SS-5 to SS-7: counts, never values."""

    def test_it_counts_by_category(self) -> None:
        report = RedactionReport(counts={RedactionCategory.PASSWORD: 2, RedactionCategory.JWT: 1})

        assert report.counts[RedactionCategory.PASSWORD] == 2
        assert report.total == 3

    def test_an_empty_report_is_a_value_not_an_absence(self) -> None:
        """SS-6 — nothing to redact returns a report, never ``None``."""
        report = RedactionReport()

        assert report.is_empty
        assert report.total == 0
        assert report.counts == {}

    def test_a_category_with_nothing_redacted_is_absent_rather_than_zero(self) -> None:
        """A zero would claim the category was searched for, which the report cannot know."""
        with pytest.raises(ValidationError):
            RedactionReport(counts={RedactionCategory.PASSWORD: 0})

    def test_a_negative_count_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RedactionReport(counts={RedactionCategory.PASSWORD: -1})

    def test_the_category_vocabulary_is_closed(self) -> None:
        """A free string gives ``aws_key``, ``aws-key`` and ``AWS key`` for one thing (R6)."""
        with pytest.raises(ValidationError):
            RedactionReport(counts={"totally-a-secret": 1})  # type: ignore[dict-item]

    def test_it_covers_the_minimum_categories_of_section_13(self) -> None:
        """§13 fixes the minimum list; #11 may extend it, and may not turn it into a free string."""
        assert {category.value for category in RedactionCategory} >= {
            "api-key",
            "bearer-token",
            "jwt",
            "github-token",
            "gitlab-token",
            "anthropic-key",
            "openai-key",
            "aws-access-key",
            "private-key",
            "password",
            "connection-string",
            "dotenv-value",
            "kubernetes-secret",
        }

    def test_it_has_nowhere_to_put_a_redacted_value(self) -> None:
        """Principle V — a report carrying the secret defeats the mechanism that serves it."""
        assert set(RedactionReport.model_fields) == {"counts"}

        with pytest.raises(ValidationError):
            RedactionReport(counts={RedactionCategory.PASSWORD: 1}, value="hunter2")  # type: ignore[call-arg]


class TestOriginalPayload:
    """§14 and Principle I: the bytes a replay re-parses after the parser is fixed."""

    def test_it_carries_the_bytes_and_their_media_type(self) -> None:
        payload = OriginalPayload(content=b'{"id": "abc123"}', media_type="application/json")

        assert payload.content == b'{"id": "abc123"}'
        assert payload.media_type == "application/json"

    def test_an_empty_media_type_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            OriginalPayload(content=b"{}", media_type="")

    def test_empty_content_is_allowed(self) -> None:
        """An export can carry an empty conversation; refusing it here would lose the fact."""
        assert OriginalPayload(content=b"", media_type="application/json").content == b""


class TestImportRecord:
    """§17's record and §18's outcome vocabulary."""

    def record(self, **overrides: object) -> ImportRecord:
        fields: dict[str, object] = {
            "source": Source.CHATGPT,
            "source_id": "abc123",
            "content_hash": "0" * 64,
            "document_id": "chatgpt:abc123",
            "recorded_at": NOW,
            "status": ImportStatus.IMPORTED,
        }
        return ImportRecord(**(fields | overrides))  # type: ignore[arg-type]

    def test_it_carries_every_field_section_17_names(self) -> None:
        assert set(ImportRecord.model_fields) == {
            "source",
            "source_id",
            "content_hash",
            "document_id",
            "recorded_at",
            "status",
            "error",
        }

    def test_the_outcome_vocabulary_is_section_18s(self) -> None:
        assert {status.value for status in ImportStatus} == {"imported", "skipped", "failed"}

    def test_a_failure_may_explain_itself(self) -> None:
        failed = self.record(status=ImportStatus.FAILED, error="the gateway timed out")

        assert failed.status is ImportStatus.FAILED
        assert failed.error == "the gateway timed out"

    def test_an_error_on_a_successful_import_is_refused(self) -> None:
        """An imported conversation carrying an error is a record nobody can act on."""
        with pytest.raises(ValidationError):
            self.record(status=ImportStatus.IMPORTED, error="the gateway timed out")

    def test_the_recorded_time_is_timezone_aware(self) -> None:
        with pytest.raises(ValidationError):
            self.record(recorded_at=datetime(2026, 9, 16, 10, 0))


class TestRecallResult:
    """§16 and MS-5: what came back, and where it came from."""

    def test_it_carries_the_content_and_the_provenance_it_was_retained_with(self) -> None:
        result = RecallResult(content="we moved to Wolverine in March", provenance=provenance())

        assert result.provenance.source is Source.CHATGPT
        assert result.score is None

    def test_a_score_is_optional(self) -> None:
        result = RecallResult(content="a fact", provenance=provenance(), score=0.42)

        assert result.score == 0.42

    def test_no_field_names_the_engine_that_produced_it(self) -> None:
        """FR-009 — a field called ``bank`` would bind every caller to Hindsight."""
        assert set(RecallResult.model_fields) == {"content", "provenance", "score"}
