# Quickstart: validating the secret sanitizer

Everything here runs on synthesized credentials. Nothing needs network access, Hindsight, a real
export or a real key — and per CLAUDE.md, no real credential may be put in this repository to try
it.

## Prerequisites

```bash
uv sync
```

## 1. The boundary contract passes, nothing skipped (SC-007)

```bash
uv run pytest tests/contracts/test_pattern_sanitizer_passes_the_contract.py -v -rs
```

Expected: the eight rules SS-1 to SS-8 pass, with SS-8 running rather than skipped — the real
sanitizer can be made to fail, so `make_failing_sanitizer` returns one.

## 2. Thirteen categories, thirteen fixtures (SC-001)

```bash
uv run pytest tests/unit/test_redaction_patterns.py -v
```

Expected: one passing test per §13 category — API key, bearer token, JWT, GitHub, GitLab,
Anthropic, OpenAI, AWS, private key, password, connection string, `.env` value, Kubernetes secret —
each asserting both that the value is gone and that the words around it survive, plus the test that
every declared category has at least one pattern.

## 3. Ordinary code and prose are untouched (SC-002)

```bash
uv run pytest tests/unit/test_redaction_false_positives.py -v
```

Expected: zero redactions over commit SHAs, UUIDs, hex digests, base64 fragments,
`Authorization: Bearer $TOKEN`, `<your-api-key>`, `password` as a word, `PASSWORD=$DB_PASSWORD`, a
ConfigMap `data:` block and a dotted version string.

## 4. Overlaps, repeats, idempotence and hostile input (SC-005)

```bash
uv run pytest tests/unit/test_redaction_scanner.py -v
```

Expected: a JWT inside a bearer header is redacted once and counted once as a JWT; a value repeated
twice is counted twice; sanitizing a sanitized conversation changes nothing and reports nothing; and
each pattern finishes within the time bound on a long adversarial string.

## 5. Nothing reaches the memory store unsanitized (SC-006)

```bash
uv run pytest tests/integration/test_pipeline_from_fakes.py -v -k sanitiz
```

Expected: with the real sanitizer composed into the harness, the recording memory store never saw
the secret; and the twin test confirms the guard fails when sanitization is taken out — a guard that
cannot fail proves nothing.

## 6. Everything, lint, and the boundary checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected: all pass. The structure tests confirm that every text-bearing field of the normalized
model is visited by the rewriter, and that `sanitization` imports no Hindsight, HTTP or storage
module.

## 7. By hand, on a string you make up (optional)

```bash
uv run python -c "from hermes_memory.sanitization import PatternSecretSanitizer as S; print(S().redact_text('GitLab request using token glpat-0000000000000000000A returned HTTP 401 Unauthorized')[0])"
```

Expected: `GitLab request using token [REDACTED] returned HTTP 401 Unauthorized` — §13's example,
which is the whole point of the feature in one line. Never paste a real credential into this
command; it is a shell history entry.
