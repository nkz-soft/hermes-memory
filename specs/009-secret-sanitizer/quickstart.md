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

Expected: 9 passed, 0 skipped — the eight rules SS-1 to SS-8 plus the check that no hook would skip
one. SS-8 runs because the failing sanitizer is the real class handed a pattern that cannot be
applied, which is the defect the error translation exists for.

## 2. Thirteen categories, thirteen fixtures (SC-001)

```bash
uv run pytest tests/unit/test_redaction_patterns.py -v
```

Expected: 70 passed. Three assertions per §13 category — the value is gone, the words around it
survive, and the report names that category — across all thirteen: API key, bearer token, JWT,
GitHub, GitLab, Anthropic, OpenAI, AWS, private key, password, connection string, `.env` value,
Kubernetes secret. Plus the table-level checks: every declared category has at least one pattern,
every sample is matched by a pattern of its own category, and the credential-shaped canary of #6's
logging redaction is redacted here too.

## 3. Ordinary code and prose are untouched (SC-002)

```bash
uv run pytest tests/unit/test_redaction_false_positives.py -v
```

Expected: 23 passed — zero redactions over commit SHAs, UUIDs, hex digests, base64 fragments,
`Authorization: Bearer $TOKEN`, `<your-api-key>`, `password` as a word, `PASSWORD=$DB_PASSWORD`, a
ConfigMap `data:` block, an ARN, a dotted version string and the rest, each asserted to come back
**equal** to the input rather than merely secret-free.

## 4. Overlaps, repeats, idempotence and the report (SC-004, SC-005)

```bash
uv run pytest tests/unit/test_redaction_scanner.py tests/unit/test_redaction_report.py -v
```

Expected: a value repeated twice is counted twice; a placeholder is left where it stands;
`[REDACTED]` is not itself a secret, so sanitizing twice changes nothing and reports nothing; and
the report's counts sum to the replacements made while quoting no value. The overlap that matters in
practice — a JWT inside a bearer header, counted once as a JWT — is asserted in
`tests/unit/test_redaction_patterns.py`.

```bash
uv run pytest tests/unit/test_redaction_cost.py -v
```

Expected: each pattern finishes within its bound on a long adversarial string, a manifest of a few
hundred kilobytes is sanitized promptly, and ten times the text costs far less than a hundred times
the work.

## 5. Nothing reaches the memory store unsanitized (SC-006)

```bash
uv run pytest tests/integration/test_pipeline_from_fakes.py -v -k "secret or sanitiz"
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

The token is assembled rather than written out, so that no line of this repository carries a
credential-shaped literal for a scanner — or a reader — to mistake for one.

```bash
uv run python -c "from hermes_memory.sanitization import PatternSecretSanitizer as S; t='glpat-'+'0'*19+'A'; print(S().redact_text(f'GitLab request using token {t} returned HTTP 401 Unauthorized')[0])"
```

Expected: `GitLab request using token [REDACTED] returned HTTP 401 Unauthorized` — §13's example,
which is the whole point of the feature in one line. Never paste a real credential into this
command; it is a shell history entry.
