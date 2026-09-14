"""A credential-shaped canary, placed everywhere a record can hold one.

The other redaction suites enumerate the escape routes someone thought of. The two holes a review
found — a credential in a mapping key, and one passed as `bytes` — were the routes nobody had
enumerated, and both were reachable through container types the walker met every day.

So this file does not enumerate. It builds every container shape a record plausibly carries, nests
them in every combination up to the depth the walker descends, puts the same canary at the bottom
of each, and asserts the canary never reaches the output. It is deliberately mechanical: its value
is that it covers combinations nobody chose.

Combinatorial rather than random, so a failure names a shape and reproduces on the next run — a
generative test that fails once and never again teaches nothing.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

import pytest

from hermes_memory.observability import get_logger

from .conftest import Rendered

CANARY = "ghp_CanaryAbCdEfGhIjKlMnOpQrStUvWx0123456789"
"""One value, shaped like a credential, recognisable in any rendering it survives into."""

CONTAINERS: dict[str, Callable[[Any], Any]] = {
    "dict_value": lambda inner: {"payload": inner},
    "dict_key": lambda inner: {inner if isinstance(inner, str) else repr(inner): "value"},
    "list": lambda inner: [inner],
    "tuple": lambda inner: (inner,),
    "set": lambda inner: {inner} if isinstance(inner, str) else [inner],
    "nested_dict": lambda inner: {"outer": {"inner": inner}},
    "object_repr": lambda inner: _Wrapping(inner),
}
"""The shapes a record plausibly carries. `set` degrades to a list for unhashable contents, which
is what a caller would have had to do anyway."""

LEAVES: dict[str, Callable[[], Any]] = {
    "str": lambda: CANARY,
    "bytes": lambda: CANARY.encode(),
    "bytearray": lambda: bytearray(CANARY.encode()),
    "in_prose": lambda: f"the call with {CANARY} was refused",
    "object_repr": lambda: _Wrapping(CANARY),
}
"""The forms the canary itself arrives in."""


class _Wrapping:
    """An object that reveals what it holds through `repr`, as most objects do."""

    def __init__(self, held: Any) -> None:
        self.held = held

    def __repr__(self) -> str:
        return f"_Wrapping({self.held!r})"


@pytest.mark.parametrize(
    ("leaf_name", "outer_name", "inner_name"),
    [
        (leaf, outer, inner)
        for leaf, (outer, inner) in itertools.product(
            LEAVES, itertools.product(CONTAINERS, CONTAINERS)
        )
    ],
)
def test_the_canary_never_reaches_the_output(
    rendered: Rendered, leaf_name: str, outer_name: str, inner_name: str
) -> None:
    """245 shapes, each carrying the canary somewhere the walker has to find it."""
    value = CONTAINERS[outer_name](CONTAINERS[inner_name](LEAVES[leaf_name]()))

    get_logger().info("a record", payload=value)

    text = rendered.text()

    assert CANARY not in text, f"leaked through {outer_name} → {inner_name} → {leaf_name}"
    assert "103, 104" not in text, "a byte string was walked into its code points"


@pytest.mark.parametrize("leaf_name", sorted(LEAVES))
def test_the_canary_never_reaches_the_output_as_a_bare_field(
    rendered: Rendered, leaf_name: str
) -> None:
    """The same canary with no container at all, for each form it can take."""
    get_logger().info("a record", payload=LEAVES[leaf_name]())

    assert CANARY not in rendered.text()


@pytest.mark.parametrize("leaf_name", sorted(LEAVES))
def test_the_canary_never_reaches_the_output_through_an_exception(
    rendered: Rendered, leaf_name: str
) -> None:
    """And through the path that assembles a string after the caller is done with it."""
    try:
        raise RuntimeError(f"failed: {LEAVES[leaf_name]()!r}")
    except RuntimeError:
        get_logger().exception("a record")

    assert CANARY not in rendered.text()


def test_the_canary_test_would_notice_a_leak(rendered: Rendered) -> None:
    """The canary is only worth having if it is detectable when it does escape.

    Without this, a canary that stopped being credential-shaped — an edit to the roster, a change
    to the prefix — would make every test above pass by describing nothing.
    """
    get_logger().info("a record", payload="ghp_NotTheCanaryAtAll0123456789abcdef")

    assert CANARY not in rendered.text()
    assert "[redacted]" in rendered.text(), (
        "the canary's shape is no longer recognised by the roster, so these tests prove nothing"
    )
