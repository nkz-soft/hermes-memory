"""Redact secrets, and report what was redacted.

The secret sanitizer boundary of ARCHITECTURE.md §8, and the vocabulary its report speaks (§13).
The patterns that find the secrets arrive with #11.
"""

from hermes_memory.sanitization.sanitizer import (
    RedactionCategory,
    RedactionReport,
    SanitizationError,
    SecretSanitizer,
)

__all__ = ["RedactionCategory", "RedactionReport", "SanitizationError", "SecretSanitizer"]
