"""The pattern sanitizer against the secret-sanitizer contract, SS-1 to SS-8.

The suite supplies the conversation and asks for a value this implementation must redact; the
sample comes from `tests/synthetic/secrets.py`, so the contract is run against the same synthesized
credentials as the unit tests rather than against a marker invented here.

SS-8 runs rather than skips. The failing sanitizer is the *real* class handed a pattern whose
expression raises — which is the defect the error translation exists for — so what the rule proves
is this implementation's behaviour, not a stub's.
"""

from __future__ import annotations

import re
from typing import Any, cast

from hermes_memory.sanitization import (
    PatternSecretSanitizer,
    RedactionCategory,
    SecretSanitizer,
)
from hermes_memory.sanitization.patterns import Pattern
from tests.contracts.sanitizer import SecretSanitizerContract
from tests.synthetic.secrets import CONTRACT_SAMPLE


class _ExplodingExpression:
    """A pattern that fails while scanning. `re` raises this on a catastrophic pattern."""

    def finditer(self, text: str) -> Any:
        raise re.error("the pattern could not be applied")


class TestPatternSecretSanitizer(SecretSanitizerContract):
    def make_sanitizer(self) -> SecretSanitizer:
        return PatternSecretSanitizer()

    def secret_sample(self) -> tuple[str, RedactionCategory]:
        return CONTRACT_SAMPLE.value, CONTRACT_SAMPLE.category

    def make_failing_sanitizer(self) -> SecretSanitizer | None:
        broken = Pattern(
            category=RedactionCategory.API_KEY,
            expression=cast(re.Pattern[str], _ExplodingExpression()),
        )
        return PatternSecretSanitizer(patterns=(broken,))

    def test_no_contract_rule_is_skipped(self) -> None:
        """A hook returning None would skip its rule silently; this one may not (SC-007)."""
        assert self.make_failing_sanitizer() is not None
