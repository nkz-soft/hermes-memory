# Quickstart: validating Environment Configuration

Phase 1 output for [plan.md](plan.md). How to confirm the deliverable by hand, beyond the automated
suite. Every command below is run from the repository root.

## 1. Configure from the example file

```bash
cp .env.example .env
```

Open `.env` and fill in the two required values — the Hindsight base URL and the LLM base URL. Add
the tokens if the instances need them. Nothing else has to be set.

## 2. The settings load

```bash
uv run python -c "from hermes_memory.settings import load_settings; s = load_settings(); print(s)"
```

Expected: the settings print with resolved absolute paths and the bank id `engineering-global`, and
**neither token appears in the output** — that is US3 and SC-003 in one look.

## 3. A missing required value fails at startup

```bash
uv run python -c "from hermes_memory.settings import load_settings; load_settings(_env_file=None)"
```

Expected: a failure naming `HERMES_HINDSIGHT__BASE_URL` and `HERMES_LLM__BASE_URL` — both, not the
first one only. That is US2 and SC-002.

## 4. The environment beats the file

```bash
HERMES_HINDSIGHT__BANK_ID=scratch uv run python -c "from hermes_memory.settings import load_settings; print(load_settings().hindsight.bank_id)"
```

Expected: `scratch`, whatever `.env` says. That is FR-004.

## 5. Nothing local is tracked

```bash
git status --short
```

Expected: `.env` does not appear. `.env.example` is committed and unchanged.

## 6. The whole check set

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Expected: all four succeed on the committed tree. The suite includes the `.env.example` agreement
check, so a setting added without its line in the example file fails here.

## 7. Prove the agreement check bites

Add a field to the settings class without touching `.env.example`, then:

```bash
uv run pytest tests/unit/test_settings_example.py
```

Expected: failure naming the setting missing from the file. Remove the scratch change afterwards.
That is SC-005, and it is the step worth actually doing — a check nobody has seen fail is a check
nobody knows works.
