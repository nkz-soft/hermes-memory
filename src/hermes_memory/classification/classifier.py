"""The project classifier boundary (ARCHITECTURE.md §8, row 3).

> Determine the project for a conversation.

§15 gives three levels: explicit metadata where the source carries a repository or working
directory, deterministic alias rules, and model-based classification — which is out of scope
(§21) and left an extension point. ChatGPT exports carry neither repository nor working directory,
so the MVP source rests on alias matching (#12).

The consequence §15 states plainly is the one this interface is shaped by: **a substantial share of
conversations will not resolve to a project.** They are imported anyway, tagged `project:unknown`,
and stay retrievable — which is possible precisely because there is one shared bank (ADR-002). So
an unresolved project is an answer with a value, not a failure, and this boundary declares no error
at all (contracts/errors.md E8, research.md R7).

Contract: specs/007-boundary-interfaces/contracts/interfaces.md, rules PC-1 to PC-5.
"""

from __future__ import annotations

from typing import Final, Protocol, runtime_checkable

from hermes_memory.normalization import Conversation, ProjectTag

__all__ = ["UNKNOWN_PROJECT", "ProjectClassifier"]

BOUNDARY = "project classifier"

UNKNOWN_PROJECT: Final[ProjectTag] = ProjectTag(value="unknown")
"""The §15 answer when no rule matches: `project:unknown`.

An ordinary value of the project tag. Named here so that every classifier and every test spells it
the same way — a second spelling would file conversations where nobody looks for them, and tags are
the only scoping mechanism there is (ADR-002).
"""


@runtime_checkable
class ProjectClassifier(Protocol):
    """Decides which project a conversation belongs to."""

    def classify(self, conversation: Conversation) -> ProjectTag:
        """Return the project tag for this conversation.

        Always returns one: no match is `UNKNOWN_PROJECT`, never `None` and never an exception
        (PC-2). `None` would be a second spelling of an answer §15 already names, and raising would
        make the pipeline's failure path its common path.

        The tag rather than a bare slug, because §6's `project:` tag is what reaches the memory
        store; the enrich stage derives the provenance's project from it rather than classifying
        twice (research.md R7).

        Deterministic and pure: the same conversation classifies the same way, the conversation is
        unchanged, and no I/O is performed (PC-3, PC-4).
        """
        ...
