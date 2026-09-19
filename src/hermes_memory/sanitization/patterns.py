"""What a secret looks like, and what only looks like one.

One ordered table, three shapes (specs/009-secret-sanitizer/research.md R3):

* **value-shaped** — a credential recognizable from its own prefix and alphabet. The match *is* the
  value, so `value_group` stays 0.
* **keyed** — the categories with no shape of their own: a password is any string, and an AWS secret
  access key is forty characters of an alphabet that a hash and half the quoted payloads in an
  engineering conversation also use. These are found by the name beside them, and only the named
  `value` group is replaced — `DATABASE_PASSWORD=[REDACTED]` keeps the key, which is usually the
  knowledge worth keeping (§13).
* **delimited block** — a PEM envelope. The body goes, both markers stay.

Order is precedence: a pattern earlier in the table wins an overlap (RR-6), which is why
`sk-ant-` sits above `sk-` and the JWT sits above the bearer header it arrives in.

Every quantifier here is bounded and none is nested, so no input makes the scanner backtrack
indefinitely (research R2). A pattern's `minimum_length` and `is_placeholder` together are the
precision half of the feature: without them the corpus fills with `[REDACTED]` where knowledge used
to be, which is a quieter version of the failure §13 rejects.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from hermes_memory.sanitization.sanitizer import RedactionCategory

__all__ = ["PATTERNS", "Pattern", "is_placeholder", "secret_manifest_blocks"]


@dataclass(frozen=True, slots=True)
class Pattern:
    """One entry in the table.

    `precedence` is not a field: it is the entry's position in the sequence handed to the scanner,
    so the table cannot disagree with itself about which of two patterns is more specific.
    """

    category: RedactionCategory
    expression: re.Pattern[str]
    value_group: int | str = 0
    """Which group holds the value to replace. 0 — the whole match — is the value-shaped case."""

    minimum_length: int = 1
    """Below this, a matched value is treated as a placeholder rather than a credential."""

    within: Callable[[str], list[tuple[int, int]]] | None = None
    """The regions of a text this pattern may match in. `None` means the whole of it.

    It exists for one category. What makes a line a Kubernetes secret is the `kind: Secret` above
    it and the `data:` key it sits under, and a regular expression cannot look arbitrarily far
    behind its own match. A guard that merely required `kind: Secret` *somewhere* would redact the
    manifest's own metadata and, in a multi-document YAML, the ConfigMap beside it — which RC-13
    forbids in as many words (research R7).
    """


_PLACEHOLDERS = frozenset(
    {
        "",
        '""',
        "''",
        "...",
        "changeme",
        "change-me",
        "changeit",
        "example",
        "null",
        "none",
        "password",
        "redacted",
        "secret",
        "todo",
        "value",
        "your-key",
        "yourkey",
        # Type names, because `password: string;` appears in every type declaration an engineering
        # history quotes, and `password` there is a field name rather than a credential.
        "any",
        "bool",
        "boolean",
        "bytes",
        "char",
        "float",
        "int",
        "integer",
        "nullable",
        "number",
        "object",
        "optional",
        "required",
        "str",
        "string",
        "text",
        "true",
        "false",
        "uuid",
        "varchar",
    }
)
"""Values that are the *name* of a secret, or the type of one, rather than a secret.

Compared case-insensitively, after quotes and a trailing `;` or `,` are stripped.
"""

_REFERENCE = re.compile(
    r"""
    \A(?:
        \$\{?[A-Za-z_][A-Za-z0-9_]{0,63}\}?      # $TOKEN, ${TOKEN}
      | %[A-Za-z_][A-Za-z0-9_]{0,63}%            # %TOKEN%
      | \{\{\s*[^{}]{1,64}\s*\}\}                # {{ token }}, a template
      | <[^<>]{1,64}>                            # <your-api-key>, a documentation placeholder
      | \[REDACTED\]                             # already sanitized — RR-8 falls out of this
      | [xX*.…-]{1,64}                      # xxx, ***, ..., ---
    )\Z
    """,
    re.VERBOSE,
)


def is_placeholder(value: str) -> bool:
    """Whether a matched value is a stand-in rather than a credential (RR-7).

    These shapes are what a README line, an example `curl` and a quoted docker-compose file are made
    of, and the corpus is full of them. Redacting one protects nothing and costs a sentence.

    Quotes are stripped first, because a `.env` line writes its placeholder as `"<your-token>"`,
    and a trailing `;` or `,` because a type declaration writes `password: string;`.
    """
    stripped = value.strip().strip("\"'").rstrip(";,")
    return (
        not stripped or stripped.lower() in _PLACEHOLDERS or _REFERENCE.match(stripped) is not None
    )


_VALUE = "value"
"""The group name every keyed and block pattern puts the credential in."""

_DOCUMENT_SEPARATOR = re.compile(r"\A---(?:[ \t].*)?\Z")
_KEY = re.compile(r"\A(?P<key>[A-Za-z_][A-Za-z0-9._-]{0,64})[ \t]*:(?P<rest>.*)\Z")
_SECRET_VALUE = re.compile(r"\A[ \t]*[\"']?Secret[\"']?[ \t]*(?:#.*)?\Z")
_EMPTY_VALUE = re.compile(r"\A[ \t]*(?:#.*)?\Z")
_DATA_KEYS = frozenset({"data", "stringData"})


@dataclass(frozen=True, slots=True)
class _Line:
    """One line of a manifest, parsed just enough to answer the two questions that matter."""

    start: int
    end: int
    """Offsets into the whole text, `end` excluding the line break."""

    indent: int
    """Where the line's content begins, counting a `- ` list marker as two columns of indent."""

    key: str | None
    value: str
    is_item_start: bool
    """Whether this line opens a list item, which is where one mapping ends and the next begins."""

    is_separator: bool
    is_blank: bool


def secret_manifest_blocks(text: str) -> list[tuple[int, int]]:
    """The `data:` and `stringData:` blocks of the Kubernetes Secrets in a text, as offsets.

    Written as code rather than as a regular expression because the condition is not local: a value
    is a secret when the mapping *it* belongs to declares `kind: Secret`. Neither relation fits in a
    lookbehind, and the cheap approximations are both wrong in ways a review caught:

    * "the text contains `kind: Secret`" takes the manifest's own metadata with it, and in a
      multi-document YAML the ConfigMap in the document beside it.
    * "`kind: Secret` at column 0, in the same `---` document" misses the shape most likely to
      reach a conversation at all — `kubectl get secrets -o yaml`, which wraps every Secret in a
      `v1/List` and indents its `kind` by two columns.

    So the question is asked of the enclosing mapping: for a `data:` key, look at the lines that are
    its siblings — same indent, same mapping, bounded by a `---`, by a list item's start and by any
    line indented less — and see whether one of them is `kind: Secret`. A `data:` nested under
    another key has different siblings and is therefore not a Secret's data block, which is also
    what keeps the blocks disjoint.
    """
    lines = _parse(text)
    blocks: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if line.key not in _DATA_KEYS or not _EMPTY_VALUE.match(line.value):
            continue
        if not _enclosing_mapping_is_a_secret(lines, index):
            continue
        blocks.append((line.end, _block_end(lines, index)))
    return blocks


def _parse(text: str) -> list[_Line]:
    parsed: list[_Line] = []
    position = 0
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        stripped = content.lstrip(" \t")
        indent = len(content[: len(content) - len(stripped)].expandtabs(8))
        is_item_start = stripped.startswith("- ") or stripped == "-"
        if is_item_start:
            # `- kind: Secret` is a mapping whose first key sits two columns in, and the dash is
            # where the previous item's mapping ends.
            indent += 2
            stripped = stripped[2:].lstrip(" \t")
        key_match = _KEY.match(stripped)
        parsed.append(
            _Line(
                start=position,
                end=position + len(content),
                indent=indent,
                key=key_match.group("key") if key_match else None,
                value=key_match.group("rest") if key_match else stripped,
                is_item_start=is_item_start,
                is_separator=_DOCUMENT_SEPARATOR.match(stripped) is not None,
                is_blank=not stripped,
            )
        )
        position += len(raw)
    return parsed


def _enclosing_mapping_is_a_secret(lines: list[_Line], index: int) -> bool:
    """Whether a sibling of `lines[index]` says `kind: Secret`."""
    indent = lines[index].indent
    return any(
        line.key == "kind" and _SECRET_VALUE.match(line.value)
        for line in _siblings(lines, index, indent)
    )


def _siblings(lines: list[_Line], index: int, indent: int) -> list[_Line]:
    """The lines of the same mapping as `lines[index]`, above and below it."""
    siblings: list[_Line] = []
    for line in reversed(lines[:index]):
        if line.is_blank:
            continue
        if line.is_separator or line.indent < indent:
            break
        if line.indent == indent:
            siblings.append(line)
        if line.is_item_start:
            break
    for line in lines[index + 1 :]:
        if line.is_blank:
            continue
        if line.is_separator or line.indent < indent or line.is_item_start:
            break
        if line.indent == indent:
            siblings.append(line)
    return siblings


def _block_end(lines: list[_Line], index: int) -> int:
    """Where the mapping under a `data:` key stops: the first line no more indented than the key."""
    indent = lines[index].indent
    end = lines[index].end
    for line in lines[index + 1 :]:
        if line.is_blank:
            continue
        if line.is_separator or line.indent <= indent:
            break
        end = line.end
    return end


PATTERNS: tuple[Pattern, ...] = (
    # --- delimited block ---------------------------------------------------------------------
    Pattern(
        category=RedactionCategory.PRIVATE_KEY,
        expression=re.compile(
            r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----\r?\n"
            r"(?P<value>[A-Za-z0-9+/=\s:.,@-]{1,20000}?)"
            r"\r?\n-----END [A-Z0-9 ]{0,40}PRIVATE KEY-----"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    # --- value-shaped ------------------------------------------------------------------------
    # Anthropic before OpenAI: `sk-ant-` is a prefix of the `sk-` family, and an overlap goes to
    # whichever pattern comes first (RR-6).
    Pattern(
        category=RedactionCategory.ANTHROPIC_KEY,
        expression=re.compile(r"sk-ant-[A-Za-z0-9_-]{16,200}"),
    ),
    Pattern(
        category=RedactionCategory.OPENAI_KEY,
        expression=re.compile(r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,200}"),
    ),
    Pattern(
        category=RedactionCategory.GITHUB_TOKEN,
        expression=re.compile(r"gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255}"),
    ),
    Pattern(
        category=RedactionCategory.GITLAB_TOKEN,
        expression=re.compile(
            r"gl(?:pat|dt|rt|ptt|soat|cbt|ft|agent|imt|oas)-[A-Za-z0-9_-]{20,64}"
        ),
    ),
    Pattern(
        category=RedactionCategory.AWS_ACCESS_KEY,
        expression=re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[A-Z0-9]{16}\b"),
    ),
    # A JWT sits above the bearer header it usually arrives in, so the report names the more
    # specific of the two (RR-6).
    Pattern(
        category=RedactionCategory.JWT,
        expression=re.compile(
            r"eyJ[A-Za-z0-9_-]{5,2000}\.[A-Za-z0-9_-]{5,4000}\.[A-Za-z0-9_-]{5,2000}"
        ),
    ),
    # --- keyed ---------------------------------------------------------------------------------
    # Confined to the `data:` and `stringData:` blocks of an actual Secret, so the manifest's own
    # metadata and the ConfigMap in the document beside it are untouched (RC-13). Inside that block
    # every value is a credential, which is what lets the alphabet be permissive enough for a
    # `stringData:` value with hyphens in it.
    Pattern(
        category=RedactionCategory.KUBERNETES_SECRET,
        expression=re.compile(
            r"^[ \t]{1,16}[A-Za-z0-9._-]{1,64}:[ \t]{0,8}(?P<value>[^\s\"']{4,4096})[ \t]*\r?$",
            re.MULTILINE,
        ),
        value_group=_VALUE,
        minimum_length=4,
        within=secret_manifest_blocks,
    ),
    Pattern(
        category=RedactionCategory.KUBERNETES_SECRET,
        expression=re.compile(
            r"--from-literal=[A-Za-z0-9._-]{1,64}=(?P<value>[^\s'\"]{4,512})",
        ),
        value_group=_VALUE,
        minimum_length=4,
    ),
    # Only the password component goes: a connection string without it still says which database
    # was involved, which is the knowledge (RC-11).
    Pattern(
        category=RedactionCategory.CONNECTION_STRING,
        expression=re.compile(
            r"[a-z][a-z0-9+.-]{1,31}://[^\s:/@]{1,64}:(?P<value>[^\s:/@]{1,256})@",
        ),
        value_group=_VALUE,
        minimum_length=3,
    ),
    Pattern(
        category=RedactionCategory.BEARER_TOKEN,
        expression=re.compile(
            r"(?i:authorization)[ \t]*:[ \t]*(?i:bearer)[ \t]+(?P<value>[A-Za-z0-9._~+/=-]{8,4096})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    Pattern(
        category=RedactionCategory.BEARER_TOKEN,
        expression=re.compile(
            r"(?i:private-token)[ \t]*:[ \t]*(?P<value>[A-Za-z0-9._~+/=-]{8,4096})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    # `access_token` and `refresh_token` are bearer tokens by another spelling, and they are the
    # spelling a real history carries: an OAuth response, a `gcloud` dump, a Docker config.
    Pattern(
        category=RedactionCategory.BEARER_TOKEN,
        expression=re.compile(
            r"(?i:access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token)[\"']?"
            r"[ \t]*[:=][ \t]*[\"']?(?P<value>[^\s\"',;&]{8,4096})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    Pattern(
        category=RedactionCategory.API_KEY,
        expression=re.compile(
            r"(?i:api[_-]?key|apikey|api[_-]?secret|client[_-]?secret)[\"']?[ \t]*[:=][ \t]*"
            r"[\"']?(?P<value>[^\s\"',;&]{8,512})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    # The id has a shape; the secret does not, so it is found beside its name or not at all
    # (research R6). Both report under the one category §13 names.
    Pattern(
        category=RedactionCategory.AWS_ACCESS_KEY,
        expression=re.compile(
            r"(?i:aws[_-]?secret[_-]?access[_-]?key|--secret-access-key)[\"']?"
            r"(?:[ \t]*[:=][ \t]*|[ \t]+)[\"']?(?P<value>[A-Za-z0-9+/=]{16,128})"
        ),
        value_group=_VALUE,
        minimum_length=16,
    ),
    Pattern(
        category=RedactionCategory.PASSWORD,
        expression=re.compile(
            r"(?i:password|passwd|pwd)[\"']?[ \t]*[:=][ \t]*"
            r"[\"']?(?P<value>[^\s\"',;]{4,256})"
        ),
        value_group=_VALUE,
        minimum_length=4,
    ),
    Pattern(
        category=RedactionCategory.PASSWORD,
        expression=re.compile(r"--password(?:[ \t]+|=)[\"']?(?P<value>[^\s\"',;]{4,256})"),
        value_group=_VALUE,
        minimum_length=4,
    ),
    # Last, because a key named `DATABASE_PASSWORD` is a password first and a `.env` line second.
    Pattern(
        category=RedactionCategory.DOTENV_VALUE,
        expression=re.compile(
            r"^[ \t]{0,8}(?:export[ \t]+)?"
            r"(?:[A-Z][A-Z0-9_]{0,63}(?:_TOKEN|_SECRET|_KEY|_PASSWORD|_PASS|_CREDENTIALS)"
            r"|TOKEN|SECRET|PASSWORD)"
            r"[ \t]*=[ \t]*[\"']?(?P<value>[^\s\"']{6,512})",
            re.MULTILINE,
        ),
        value_group=_VALUE,
        minimum_length=6,
    ),
)
"""The table, most specific first. Order is precedence (RR-6)."""
