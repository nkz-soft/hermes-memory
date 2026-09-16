"""An in-memory project classifier: an alias map, and `project:unknown` for everything else.

§15's level 2 in miniature — deterministic rules over known names. The real alias rules are #12's;
what this proves is that the interface can answer without raising, which is the part §15 cares
about most.
"""

from __future__ import annotations

from collections.abc import Mapping

from hermes_memory.classification import UNKNOWN_PROJECT
from hermes_memory.normalization import Conversation, ProjectTag


class InMemoryProjectClassifier:
    """Matches an alias anywhere in the title or the message text."""

    def __init__(self, aliases: Mapping[str, str] | None = None) -> None:
        self._aliases = dict(aliases or {})

    def classify(self, conversation: Conversation) -> ProjectTag:
        haystack = " ".join(
            [conversation.title or "", *(message.text for message in conversation.messages)]
        ).lower()

        for alias, project in self._aliases.items():
            if alias.lower() in haystack:
                return ProjectTag(value=project)

        return UNKNOWN_PROJECT
