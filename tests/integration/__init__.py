"""Tests about several boundaries fitting together rather than about any one of them.

The suites in ``tests/contracts/`` hold one boundary each. What they cannot show is that the six
compose — that the sanitizer's output is what the classifier takes, that the archive and the memory
store agree on what a document is, that the import state's answer is reached before the store is
called. That is what lives here (ARCHITECTURE.md §7).
"""
