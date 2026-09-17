"""Reconstructing the displayed thread from a conversation's message graph (research R4)."""

from __future__ import annotations

import pytest

from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord, reconstruct
from tests.synthetic import chatgpt_export as synth


def _branched() -> dict[str, synth.Node]:
    """root → u1 → a1 (regenerated as a1b); u1 was also edited into u2 → a2.

    root
     ├─ u1 ─┬─ a1
     │      └─ a1b
     └─ u2 ─── a2
    """
    say = synth.message
    return {
        "root": synth.node("root", None, children=["u1", "u2"]),
        "u1": synth.node("u1", say("user", "first wording"), parent="root", children=["a1", "a1b"]),
        "a1": synth.node("a1", say("assistant", "first answer"), parent="u1"),
        "a1b": synth.node("a1b", say("assistant", "regenerated"), parent="u1"),
        "u2": synth.node("u2", say("user", "edited wording"), parent="root", children=["a2"]),
        "a2": synth.node("a2", say("assistant", "answer to edit"), parent="u2"),
    }


def test_a_linear_graph_is_its_own_thread() -> None:
    mapping, leaf = synth.chain(*(synth.message("user", str(i)) for i in range(3)))

    thread = reconstruct(mapping, leaf)

    assert thread.node_ids == ("root", "n1", "n2", "n3")
    assert thread.fallback_branch is False
    assert thread.abandoned == 0


@pytest.mark.parametrize(
    ("current", "expected", "abandoned"),
    [
        ("a2", ("root", "u2", "a2"), 3),
        ("a1", ("root", "u1", "a1"), 3),
        ("a1b", ("root", "u1", "a1b"), 3),
    ],
)
def test_a_branched_graph_follows_the_current_node(current, expected, abandoned) -> None:
    thread = reconstruct(_branched(), current)

    assert thread.node_ids == expected
    assert thread.fallback_branch is False
    assert thread.abandoned == abandoned


@pytest.mark.parametrize("current", [None, "no-such-node"])
def test_without_a_valid_current_node_the_last_child_is_followed(current) -> None:
    thread = reconstruct(_branched(), current)

    assert thread.node_ids == ("root", "u2", "a2")
    assert thread.fallback_branch is True


def test_the_current_node_may_be_an_inner_node() -> None:
    """The interface displays up to the current node, even when the graph continues past it."""
    thread = reconstruct(_branched(), "u1")

    assert thread.node_ids == ("root", "u1")
    assert thread.abandoned == 4


def _broken(mutate) -> dict[str, synth.Node]:
    mapping = _branched()
    mutate(mapping)
    return mapping


BROKEN = {
    "two roots": lambda m: m["u2"].update(parent=None) or m["root"]["children"].remove("u2"),
    "dangling parent": lambda m: m["a2"].update(parent="gone") or m["u2"]["children"].clear(),
    "dangling child": lambda m: m["a2"]["children"].append("gone"),
    "parent disagrees": lambda m: m["a2"].update(parent="u1"),
    "cycle": lambda m: (
        m["root"]["children"].append("a2")
        or m["a2"]["children"].append("root")
        or m["root"].update(parent="a2")
    ),
    "not a node": lambda m: m.update(u2="text"),
    "children not a list": lambda m: m["u2"].update(children="a2"),
    "duplicate child": lambda m: m["u2"]["children"].append("a2"),
}


@pytest.mark.parametrize("name", list(BROKEN))
def test_a_broken_graph_is_unreadable_and_says_which_rule(name: str) -> None:
    with pytest.raises(UnreadableRecord) as raised:
        reconstruct(_broken(BROKEN[name]), "a2")

    assert "wording" not in str(raised.value)
    assert "answer" not in str(raised.value)


def test_an_empty_mapping_is_unreadable() -> None:
    with pytest.raises(UnreadableRecord):
        reconstruct({}, None)


def test_order_is_the_graph_not_the_times() -> None:
    bodies = [synth.message("user", str(i), create_time=1000.0 - i) for i in range(3)]
    mapping, leaf = synth.chain(*bodies)

    assert reconstruct(mapping, leaf).node_ids == ("root", "n1", "n2", "n3")


def test_a_long_thread_does_not_recurse() -> None:
    mapping, leaf = synth.chain(*(synth.message("user", "x") for _ in range(10_000)))

    assert len(reconstruct(mapping, leaf).node_ids) == 10_001
