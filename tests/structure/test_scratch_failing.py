"""TEMP: a deliberately false assertion, to prove the test check turns a PR red (T028)."""


def test_deliberately_false() -> None:
    assert 1 == 2, "This test is meant to fail; it is reverted immediately."
