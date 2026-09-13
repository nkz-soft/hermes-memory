"""The single place this project reads configuration from.

Values come from `HERMES_`-prefixed environment variables and, optionally, from an untracked
`.env` — never from a file in the repository. Principle V of the constitution allows "environment
variables or a secret store"; the environment is the mechanism for the MVP, and this module is the
seam another source would attach to.

Nothing else may read the environment. `tests/structure/test_environment_files.py` enforces that
over the committed tree rather than trusting the convention.

This is a top-level module rather than a package on purpose. The constitution's module tree records
the boundaries of ARCHITECTURE.md §8; configuration is consumed by every one of them and owned by
none, so giving it a peer package would misrepresent it as a sixteenth boundary — see
`specs/002-environment-configuration/research.md` R1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, get_args

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    SecretStr,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "HindsightSettings",
    "LlmSettings",
    "Settings",
    "SettingsError",
    "environment_variable_names",
    "load_settings",
    "secret_variable_names",
]

ENV_PREFIX = "HERMES_"
ENV_NESTED_DELIMITER = "__"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
"""The repository root, derived from this file rather than from the working directory.

FR-013: a relative `data/archive` must mean the same directory whether a command is run from the
repository root or from a subdirectory. Resolving against `Path.cwd()` would scatter archives.

This holds for a source checkout and for the editable install `uv sync` produces. A non-editable
deployment has no repository, and there the relative defaults are meaningless — such a deployment
sets absolute paths, which `.env.example` says.
"""

DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SettingsError(RuntimeError):
    """Configuration could not be loaded.

    Raised instead of letting a `ValidationError` escape, and that is not cosmetic. Pydantic
    renders the offending input into its message — `input_value='...'` — so a credential of the
    wrong shape would be echoed into whatever caught it. This error is built from the field
    location, the message and the error type only. The input never reaches it (FR-007, SC-003).
    """


class _Frozen(BaseModel):
    """Base for the nested groups: validated once, immutable afterwards."""

    model_config = ConfigDict(frozen=True)


class HindsightSettings(_Frozen):
    """Where the memory engine is, and what it is called.

    A group of its own so that the memory store can be handed these settings without also being
    handed the LLM credential (Principle IV, Principle V).
    """

    base_url: AnyHttpUrl
    token: SecretStr | None = None
    bank_id: NonEmptyString = "engineering-global"
    """The single shared bank fixed by ADR-002. A recorded decision, not an operator's choice —
    defaulted rather than required, and overridable so tests can use a scratch bank."""

    @field_validator("token", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        return _blank_is_unset(value)


class LlmSettings(_Frozen):
    """The OpenAI-compatible endpoint extraction is routed through.

    No model name: ARCHITECTURE.md §19.4 records that the model is proxy configuration rather than
    anything hardcoded here.
    """

    base_url: AnyHttpUrl
    api_key: SecretStr | None = None

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        return _blank_is_unset(value)


class Settings(BaseSettings):
    """Every value this project reads from its environment, validated as a whole.

    Construct it through `load_settings`. Building one field by field bypasses precedence and the
    error handling that keeps credentials out of failure messages; tests may do it, which is what
    makes them tests.
    """

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    hindsight: HindsightSettings
    llm: LlmSettings
    archive_root: Path = Path("data/archive")
    import_state_path: Path = Path("data/import-state.db")

    @model_validator(mode="before")
    @classmethod
    def _always_descend_into_the_groups(cls, values: Any) -> Any:
        """Report `hindsight.base_url` as missing, not `hindsight`.

        With no `HERMES_HINDSIGHT__*` variable set at all, the group itself is absent and Pydantic
        reports the group as the missing field — which translates to `HERMES_HINDSIGHT`, a
        variable that does not exist. Supplying an empty mapping makes validation descend and name
        the leaf the operator actually has to set (FR-005).
        """
        if isinstance(values, dict):
            for group in ("hindsight", "llm"):
                values.setdefault(group, {})
        return values

    @field_validator("archive_root", "import_state_path")
    @classmethod
    def _resolve_against_the_project_root(cls, value: Path) -> Path:
        """Absolute in, absolute out; relative in, resolved against the repository (FR-013).

        Nothing is created and nothing is checked for existence: loading has no side effects
        (FR-012), and the feature that stores something decides what an absent directory means.
        """
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()


def _blank_is_unset(value: Any) -> Any:
    """An empty or whitespace-only credential is an absent one, not an empty one."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def load_settings(*, env_file: Path | str | None = DEFAULT_ENV_FILE) -> Settings:
    """Load and validate the settings, or raise `SettingsError` naming every fault.

    Performs no network call and creates no file or directory (FR-012), so it is safe to call in a
    test, in a dry run and behind `--help`.

    `env_file=None` disables the file entirely — which is what a test wants, so that whether a
    developer happens to have a `.env` in their checkout cannot decide whether the suite passes.
    """
    if env_file is not None:
        _reject_malformed(Path(env_file))

    try:
        return Settings(_env_file=env_file)  # type: ignore[call-arg]
    except ValidationError as error:
        description = _describe(error)

    # Raised *after* the except block, not inside it. `raise ... from None` would clear
    # `__cause__` but leave the ValidationError — and the inputs it echoes — hanging off
    # `__context__`, where a logger rendering the exception chain would find it. Once the handler
    # has exited there is no context to attach (FR-007, SC-003).
    raise SettingsError(description)


def _describe(error: ValidationError) -> str:
    """Render a validation failure as environment variable names and reasons.

    Built from `loc`, `msg` and `type` only. The `input` each entry also carries is deliberately
    dropped: it is the operator's value, and for a credential it is the credential.
    """
    faults = sorted(
        f"  {_variable_name(entry['loc'])}: {entry['msg']} [{entry['type']}]"
        for entry in error.errors()
    )
    plural = "s" if len(faults) != 1 else ""
    return (
        f"Configuration could not be loaded. {len(faults)} problem{plural} "
        f"with the environment:\n" + "\n".join(faults)
    )


def _variable_name(location: tuple[Any, ...]) -> str:
    """The environment variable an error location refers to."""
    return ENV_PREFIX + ENV_NESTED_DELIMITER.join(str(part) for part in location).upper()


def _reject_malformed(path: Path) -> None:
    """A typo in `.env` must not be indistinguishable from `.env` being absent.

    A missing file is normal and silent. A file that exists but holds a line the dotenv parser
    would skip is not: `HERMES_HINDSIGHT__BANK_ID scratch` would silently do nothing, and the
    operator would spend the afternoon wondering why.
    """
    if not path.exists():
        return

    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped.removeprefix("export "):
            raise SettingsError(
                f"{path} line {number} is not a NAME=value assignment: {stripped!r}. "
                "The dotenv parser would skip it silently, so the setting would go unset."
            )


def _declared_variables() -> dict[str, bool]:
    """Every environment variable the settings declare, mapped to whether it is a credential.

    Derived by walking the models, so nothing re-types the roster. `.env.example` is checked
    against this rather than against a hand-maintained list
    (specs/002-environment-configuration/research.md R5).
    """
    variables: dict[str, bool] = {}

    def walk(model: type[BaseModel], prefix: str) -> None:
        for name, field in model.model_fields.items():
            annotation = field.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                walk(annotation, f"{prefix}{name.upper()}{ENV_NESTED_DELIMITER}")
            else:
                variables[f"{prefix}{name.upper()}"] = _is_secret(annotation)

    walk(Settings, ENV_PREFIX)
    return variables


def _is_secret(annotation: Any) -> bool:
    """Whether an annotation carries a secret type, including inside `SecretStr | None`."""
    return SecretStr in (annotation, *get_args(annotation))


def environment_variable_names() -> frozenset[str]:
    """Every environment variable the settings read."""
    return frozenset(_declared_variables())


def secret_variable_names() -> frozenset[str]:
    """The subset of those that carry a credential."""
    return frozenset(name for name, is_secret in _declared_variables().items() if is_secret)
