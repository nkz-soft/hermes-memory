"""Determine the project a conversation belongs to.

The project classifier boundary of ARCHITECTURE.md §8, and the §15 answer for a conversation no
rule matches. The alias rules that decide the rest arrive with #12.
"""

from hermes_memory.classification.classifier import UNKNOWN_PROJECT, ProjectClassifier

__all__ = ["UNKNOWN_PROJECT", "ProjectClassifier"]
