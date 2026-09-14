"""`.gitleaks.toml` keeps the promises `contracts/checks.md` makes about its exemptions.

What this file guards is the *shape* of an exemption, not its contents. The distinction is the
whole design: a reviewer can check a shape at a glance and cannot check a judgement. An exemption
here is the conjunction of three independent narrowings — one rule, one file, one value — so that
dropping any single one still leaves the other two biting.

The failure this prevents is not a typo. It is the one-line widening that makes a red build green:
`paths` alone, under the default OR condition, stops the scanner reporting *anything* in a file for
that rule. The files being exempted are the redaction tests, which is precisely where a real
credential is most likely to be pasted by someone reproducing a bug.

Whether the exemptions actually clear the repository is check C5's business, not this file's; C5 is
a command, and its verdict is the deliverable rather than an assertion about it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / ".gitleaks.toml"

# A path pattern must name a file. Anchoring alone is not enough: `^tests/unit/.*$` is anchored and
# exempts a directory. Requiring an extension at the end is the cheap, checkable form of "a file".
_FILE_SUFFIX = (".py", ".md", ".toml", ".ini", ".yml", ".yaml", ".txt", ".json", ".env", ".cfg")


def _config() -> dict[str, Any]:
    """The parsed configuration. Fails if it is not valid TOML — the scanner would not read it."""
    assert CONFIG.exists(), f"The scanner configuration is missing at {CONFIG.name}."

    try:
        return tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:  # pragma: no cover - only on a broken config
        raise AssertionError(
            f"{CONFIG.name} is not valid TOML, so the scanner will not read it: {error}"
        ) from error


def _allowlists() -> list[dict[str, Any]]:
    """Every top-level `[[allowlists]]` entry, which is where this project declares exemptions."""
    entries = _config().get("allowlists", [])
    assert isinstance(entries, list), "`allowlists` did not parse to a list of entries."
    return entries


def test_extends_the_default_rules() -> None:
    """The exemptions extend the upstream rule set rather than replacing it (check S5).

    Without `useDefault`, the configuration would define the *entire* set of things the scanner
    looks for — which for a file that contains only allowlists is nothing at all. The check would
    then pass on every repository in the world.
    """
    extend = _config().get("extend", {})

    assert extend.get("useDefault") is True, (
        "`.gitleaks.toml` does not set `[extend] useDefault = true`. Without it the upstream rules "
        "are replaced rather than extended, and a configuration of allowlists alone detects "
        "nothing."
    )


def test_every_exemption_requires_all_of_its_conditions() -> None:
    """Every entry sets `condition = "AND"` (check S6).

    This is the one that matters most, and it is not the default. Allowlist conditions default to
    OR, under which a `paths` entry alone exempts the whole file for the targeted rules — turning a
    narrow statement about one literal into a blanket one about a file.
    """
    offenders = [
        entry.get("description", "<no description>")
        for entry in _allowlists()
        if entry.get("condition") != "AND"
    ]

    assert not offenders, (
        f'These exemptions do not set `condition = "AND"`: {offenders}. The default is OR, under '
        "which `paths` alone exempts an entire file for the targeted rules."
    )


def test_every_exemption_narrows_rule_path_and_value() -> None:
    """Every entry declares all three narrowings, and says why it exists (check S7).

    `condition = "AND"` over a missing key is not a conjunction of three things; it is a
    conjunction of however many are present. Both halves are needed.
    """
    required = ("description", "targetRules", "paths", "regexes")
    offenders: list[str] = []

    for entry in _allowlists():
        missing = [key for key in required if not entry.get(key)]
        if missing:
            offenders.append(f"{entry.get('description', '<no description>')}: missing {missing}")

    assert not offenders, (
        "These exemptions do not narrow by rule, path and value with a stated reason: "
        f"{offenders}. "
        "An exemption missing one of them is broader than it looks."
    )


def test_no_exemption_names_a_directory() -> None:
    """Every `paths` pattern is anchored and names a file (check S8, FR-008).

    A directory exemption is the blanket FR-008 forbids. `tests/` in particular is the last place
    to stop scanning: the corpus this project handles makes fixtures a high-risk location, not a
    safe one.
    """
    offenders: list[str] = []

    for entry in _allowlists():
        description = entry.get("description", "<no description>")
        for pattern in entry.get("paths", []):
            anchored = pattern.startswith("^") and pattern.endswith("$")
            names_a_file = pattern.rstrip("$").endswith(_FILE_SUFFIX)
            if not (anchored and names_a_file):
                offenders.append(f"{description}: {pattern!r}")

    assert not offenders, (
        f"These path patterns are not anchored to a single file: {offenders}. A pattern that can "
        "match a directory exempts everything under it for the targeted rules."
    )
