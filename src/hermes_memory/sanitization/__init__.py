"""Redact secrets, and report what was redacted.

The secret sanitizer boundary of ARCHITECTURE.md §8, the vocabulary its report speaks (§13), and
`PatternSecretSanitizer`, the implementation behind it: one ordered table of deterministic patterns
that replace a credential with `[REDACTED]` and leave the sentence it sat in intact.
"""

from hermes_memory.sanitization.pattern_sanitizer import PatternSecretSanitizer
from hermes_memory.sanitization.sanitizer import (
    RedactionCategory,
    RedactionReport,
    SanitizationError,
    SecretSanitizer,
)

__all__ = [
    "PatternSecretSanitizer",
    "RedactionCategory",
    "RedactionReport",
    "SanitizationError",
    "SecretSanitizer",
]
