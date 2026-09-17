"""The thread a person saw, out of the graph a ChatGPT export stores (research R4).

An export does not keep a conversation as a list. It keeps a tree of message nodes, forked wherever
a message was edited or an answer regenerated, and a `current_node` marking where the interface
stood. The conversation is the path from the root to that node; every other branch is something the
person moved away from.

The graph is validated before it is walked. A walk over a malformed graph does not fail — it quietly
returns a different conversation, which is the class of defect Principle III exists for.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["Thread", "UnreadableRecord", "reconstruct"]


class UnreadableRecord(Exception):
    """One conversation record cannot be read. The message names the rule, never a value from it.

    Internal to this package: the source translates it into `SourceFormatError` with the
    conversation's identifier as its subject.
    """


@dataclass(frozen=True, slots=True)
class Thread:
    node_ids: tuple[str, ...]
    """From the root to the displayed node, in that order."""

    fallback_branch: bool
    """The export marked no valid current node, so the last-listed child was followed at forks."""

    abandoned: int
    """Nodes of the graph that are not on the thread."""


def _parent(node: Any) -> Any:
    return node.get("parent")


def _children(node: Mapping[str, Any]) -> list[str]:
    children = node.get("children", [])
    if not isinstance(children, list) or not all(isinstance(child, str) for child in children):
        raise UnreadableRecord("a node's children are not a list of node ids")
    if len(set(children)) != len(children):
        raise UnreadableRecord("a node lists the same child twice")
    return children


def _validate(mapping: Any) -> str:
    """Check that the mapping is one tree whose parent and child links agree. Returns the root."""
    if not isinstance(mapping, Mapping) or not mapping:
        raise UnreadableRecord("the conversation has no message mapping")

    roots = []
    for node_id, node in mapping.items():
        if not isinstance(node, Mapping):
            raise UnreadableRecord("a mapping entry is not a node")
        parent = _parent(node)
        if parent is None:
            roots.append(node_id)
        elif not isinstance(parent, str) or parent not in mapping:
            raise UnreadableRecord("a node names a parent that is not in the mapping")
        elif not isinstance(mapping[parent], Mapping) or node_id not in _children(mapping[parent]):
            raise UnreadableRecord("a node's parent does not list it as a child")
        for child in _children(node):
            if child not in mapping:
                raise UnreadableRecord("a node names a child that is not in the mapping")
            child_node = mapping[child]
            if not isinstance(child_node, Mapping) or _parent(child_node) != node_id:
                raise UnreadableRecord("a node's child does not name it as parent")

    if len(roots) != 1:
        raise UnreadableRecord(f"the mapping has {len(roots)} roots, not one")

    # Links agree and there is one root; the graph is a tree exactly when every node is reachable
    # from that root. Iterative, because a long conversation is deeper than the recursion limit.
    reached = 0
    pending = [roots[0]]
    while pending:
        reached += 1
        pending.extend(_children(mapping[pending.pop()]))
        if reached > len(mapping):
            break
    if reached != len(mapping):
        raise UnreadableRecord("the mapping contains a cycle or a node unreachable from the root")
    return roots[0]


def _last_child_leaf(mapping: Mapping[str, Any], root: str) -> str:
    node_id = root
    while children := _children(mapping[node_id]):
        node_id = children[-1]
    return node_id


def reconstruct(mapping: Any, current_node: Any) -> Thread:
    """Validate the graph and return the thread from its root to the displayed node."""
    root = _validate(mapping)

    fallback = not (isinstance(current_node, str) and current_node in mapping)
    leaf = _last_child_leaf(mapping, root) if fallback else current_node

    path = [leaf]
    while (parent := _parent(mapping[path[-1]])) is not None:
        path.append(parent)
    path.reverse()

    return Thread(
        node_ids=tuple(path), fallback_branch=fallback, abandoned=len(mapping) - len(path)
    )
