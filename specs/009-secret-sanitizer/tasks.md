# Tasks: Secret sanitizer

**Input**: Design documents from `/specs/009-secret-sanitizer/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/redaction-rules.md](./contracts/redaction-rules.md)

**Tests**: Required. Principle III is non-negotiable and names "unit tests for … the secret
sanitizer against realistic fixtures" specifically. Every task that adds behaviour is preceded by a
task that writes its test. That test must be run and **observed failing** before the implementation
task starts.

**Organization**: by user story, in the priority order of [spec.md](./spec.md). The span scanner is
foundational: every category's pattern is found and replaced through it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1–US5 from [spec.md](./spec.md)

## Path Conventions

Single project: `src/hermes_memory/sanitization/`, `tests/` at repository root, per
[plan.md](./plan.md#source-code-repository-root).

**Every credential in every fixture is synthesized** (research R11). CLAUDE.md forbids real
credentials in this repository, and Gitleaks in CI (#7) rejects them.

---

## Phase 1: Setup

**Purpose**: the static guard for the module, before anything is written into it.

- [ ] T001 [P] Write `tests/structure/test_sanitization_imports.py`: every `.py` under
      `src/hermes_memory/sanitization/` imports only the standard library, `pydantic`,
      `hermes_memory.errors`, `hermes_memory.normalization` and `hermes_memory.sanitization.*`.
      Nothing on `FORBIDDEN_AT_RUNTIME` of `tests/structure/test_boundary_interfaces.py` is allowed;
      reuse that list by import rather than copying it. Include a "still bites" test against a
      `tmp_path` package holding `import httpx`, so the guard is proved able to fail

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `Pattern` and `Span` types and the scanner that finds, resolves and rewrites.
No category can be added until a span can be found and replaced.

- [ ] T002 Write `tests/unit/test_redaction_scanner.py` first and observe it fail. It uses a small
      table **defined in the test**, not the real one, so the scanner is tested as a mechanism:
      a single match is replaced with the literal `[REDACTED]` and the text either side survives
      (RR-1, RR-2); the same value twice is replaced twice and counted twice (RR-5); two different
      values in one string are both replaced; a value group is replaced while its key survives
      (RR-2); an overlapping pair is replaced once and counted once, under the category of the
      pattern earlier in the table (RR-6); a match whose value is `$VAR`, `${VAR}`, `%VAR%`,
      `{{ var }}`, `<your-api-key>`, `xxx`, `***`, `changeme`, `...`, empty, `[REDACTED]`, or
      shorter than the pattern's `minimum_length` is left alone (RR-7); and a string with no match
      comes back identical with an empty report
- [ ] T003 Implement `src/hermes_memory/sanitization/patterns.py`: the frozen `Pattern` record with
      `category`, `expression`, `value_group`, `precedence` and `minimum_length` per
      [data-model.md](./data-model.md), and `is_placeholder(value)` holding RR-7's rejection list.
      The real table is declared empty here and filled per category in Phase 3, so that T002's
      mechanism tests do not depend on it
- [ ] T004 Implement `src/hermes_memory/sanitization/scanner.py`: `Span` (half-open bounds,
      category, precedence — internal, never exported from the package, per
      [data-model.md](./data-model.md)); `find_spans(text, patterns)`; `resolve(spans)`, which sorts
      by start and drops a span overlapping one already kept (RR-6); and
      `redact(text, patterns) -> tuple[str, dict[RedactionCategory, int]]`, which rebuilds the
      string in one pass over the surviving spans and counts replacements actually made, not matches
      found (RR-5)

**Checkpoint**: a string can be scanned and rewritten. The table is still empty, so nothing is
redacted yet — and the scanner's own tests pass.

---

## Phase 3: User Story 1 — a credential in the history never reaches the memory engine (Priority: P1) 🎯 MVP

**Goal**: the thirteen categories of §13 are recognized, and redaction reaches every text-bearing
field of a conversation.

**Independent Test**: a conversation carrying a synthesized secret of each category in its title,
message text, tool request, tool result and attachment name comes back with none of them present.

### Tests for User Story 1

- [ ] T005 [US1] Create `tests/synthetic/secrets.py`: one synthesized sample per §13 category, each
      as a record of the bare value, a sentence it sits in, and the text that must survive
      redaction. Values are generated from the documented shape with a literal marker inside them —
      never a real key, never a plausible one. Include GitLab's `glpat-` sample as §13's own
      example, `GitLab request using token ‹sample› returned HTTP 401 Unauthorized`
- [ ] T006 [P] [US1] Write `tests/unit/test_redaction_patterns.py` first and observe it fail: one
      test per rule RC-1 to RC-13 of [contracts/redaction-rules.md](./contracts/redaction-rules.md),
      each asserting the value is gone, the "kept" clause of its rule holds, and the report names
      that rule's category. Plus two table-level tests: every member of `RedactionCategory` has at
      least one pattern, and every sample in `tests/synthetic/secrets.py` is matched by the pattern
      it is a sample of (research R11)
- [ ] T007 [P] [US1] Write `tests/unit/test_pattern_sanitizer.py` first and observe it fail: the
      secret is gone from `title`, from `Message.text`, from `ToolActivity.name`, `.request` and
      `.result`, and from `NonTextPart.name` (RR-3); `source`, `source_id`, `started_at`,
      `last_activity_at`, `Message.role`, `Message.sent_at` and `NonTextPart.kind` come back
      unchanged and `document_id` is the input's (RR-4); the input object is not mutated; a `None`
      field stays `None` rather than becoming `""`; a message whose whole text was a secret becomes
      `[REDACTED]` and keeps its position
- [ ] T008 [P] [US1] Write `tests/structure/test_sanitizer_covers_the_model.py` first and observe it
      fail: enumerate the fields of `Conversation`, `Message`, `ToolActivity` and `NonTextPart`,
      partition them into scanned and copied by the lists the rewriter declares, and fail when a
      field belongs to neither — so a text-bearing field added to #8's model later cannot be
      forgotten (RR-3, research R1)
- [ ] T009 [P] [US1] Write `tests/contracts/test_pattern_sanitizer_passes_the_contract.py` first and
      observe it fail: subclass `SecretSanitizerContract` from `tests/contracts/sanitizer.py`,
      supplying `make_sanitizer`, `secret_sample` from `tests/synthetic/secrets.py`, and a
      `make_failing_sanitizer` that returns a sanitizer which raises `SanitizationError` — so SS-8
      runs rather than skips (SC-007)

### Implementation for User Story 1

- [ ] T010 [US1] Fill the value-shaped patterns in `src/hermes_memory/sanitization/patterns.py`:
      Anthropic `sk-ant-` before OpenAI `sk-`/`sk-proj-` (RC-6, RC-7); GitHub `ghp_`, `gho_`,
      `ghu_`, `ghs_`, `ghr_`, `github_pat_` (RC-4); GitLab `glpat-` and siblings (RC-5); the AWS
      access key id prefixes `AKIA`, `ASIA`, `AGPA`, `AIDA`, `AROA`, `ANPA`, `ANVA`, `AIPA` plus
      sixteen uppercase alphanumerics (RC-8); and the JWT triple, first segment beginning `eyJ`
      (RC-3). Every quantifier bounded, none nested (research R2)
- [ ] T011 [US1] Fill the keyed patterns: API key as assignment, header and query parameter (RC-1);
      `Authorization: Bearer` and `PRIVATE-TOKEN` (RC-2); `aws_secret_access_key` and
      `--secret-access-key`, reported as `aws-access-key` (RC-8); `password`/`passwd`/`pwd` as
      assignment or `--password` flag (RC-10); the `‹scheme›://‹user›:‹secret›@‹host›` connection
      string, replacing the password component only (RC-11); the `.env` key-name shapes `_TOKEN`,
      `_SECRET`, `_KEY`, `_PASSWORD`, `_PASS`, `_CREDENTIALS`, `TOKEN`, `SECRET` (RC-12); and the
      Kubernetes forms — `data:`/`stringData:` values within a text containing `kind: Secret`, and
      `--from-literal=‹key›=‹value›` (RC-13, research R7)
- [ ] T012 [US1] Fill the delimited-block pattern: the PEM envelope from `-----BEGIN … PRIVATE
      KEY-----` to `-----END … PRIVATE KEY-----`, including the `OPENSSH`, `RSA`, `EC`, `DSA` and
      `PGP` variants, replacing the body in one span across its line breaks and keeping both
      markers (RC-9). Set the table's precedence order to research R4's, most specific first
- [ ] T013 [US1] Implement `src/hermes_memory/sanitization/pattern_sanitizer.py`:
      `PatternSecretSanitizer` with `sanitize(conversation)` walking the scanned fields of RR-3 in
      order and rebuilding with the model's own copy semantics, summing the per-string counts into
      one `RedactionReport`; plus `redact_text(text)` for the one-string case, documented as a
      convenience on the implementation and not part of the boundary
      ([data-model.md](./data-model.md))
- [ ] T014 [US1] Export `PatternSecretSanitizer` from
      `src/hermes_memory/sanitization/__init__.py` and extend that module's docstring from "the
      patterns arrive with #11" to what now lives there. `sanitizer.py` is **not** edited

**Checkpoint**: US1 complete. `pytest tests/unit/test_redaction_patterns.py
tests/unit/test_pattern_sanitizer.py tests/contracts/test_pattern_sanitizer_passes_the_contract.py`
is green, with SS-8 running rather than skipped.

---

## Phase 4: User Story 2 — the knowledge around the secret survives (Priority: P1)

**Goal**: §13's standard, asserted rather than assumed — the value goes, the sentence stays.

**Independent Test**: sanitize §13's own example and read the result:
`GitLab request using token [REDACTED] returned HTTP 401 Unauthorized`.

- [ ] T015 [US2] Write `tests/unit/test_redaction_context.py` first and observe it fail: §13's
      example renders exactly, character for character; `DATABASE_PASSWORD=‹v›` keeps its key;
      a PEM block keeps both markers and loses its body; a connection string keeps scheme, user,
      host, port and path and loses only the password; an `Authorization: Bearer` header keeps the
      scheme; a Kubernetes manifest keeps `kind`, `metadata` and its `data:` keys; and every message
      that carried text still carries text (FR-003, FR-004, RR-2)
- [ ] T016 [US2] Fix whatever T015 finds in the value groups of `patterns.py` — a group that
      swallowed its key, a block pattern that ate its markers, a connection-string group that took
      the host. No new module: this story is the assertion that Phase 3's groups are cut in the
      right place

**Checkpoint**: US1 and US2 hold together — nothing leaks, and nothing readable was destroyed.

---

## Phase 5: User Story 3 — a run can be audited without logging its content (Priority: P2)

**Goal**: the report is truthful about counts and incapable of carrying a value.

**Independent Test**: a conversation with two secrets of one category and one of another reports 2
and 1, and neither value appears in the report rendered in full.

- [ ] T017 [US3] Write `tests/unit/test_redaction_report.py` first and observe it fail: counts per
      category sum to the number of replacements made (FR-008, SC-004); a category with nothing
      redacted is absent rather than zero; an empty conversation and a clean conversation both give
      `is_empty`; the report rendered with `repr(model_dump())` contains no sample value; and
      sanitizing an already sanitized conversation returns an equal conversation with an empty
      report (RR-8, SC-005)
- [ ] T018 [US3] Write `tests/unit/test_sanitizer_is_quiet.py` first and observe it fail: sanitizing
      a conversation full of secrets emits **no** log event at all, asserted with the capturing
      fixture of `tests/unit/conftest.py` (research R8, FR-016)
- [ ] T019 [US3] Make T017 and T018 pass. Expected to be assertions about existing behaviour rather
      than new code; where it is not — a count taken from matches instead of replacements, a log
      statement added while debugging — fix it in `scanner.py` or `pattern_sanitizer.py`

**Checkpoint**: a run can be audited from counts alone, and the boundary says nothing else.

---

## Phase 6: User Story 4 — ordinary code and prose are left alone (Priority: P2)

**Goal**: the corpus is not replaced with `[REDACTED]` where there was knowledge.

**Independent Test**: the false-positive suite runs over ordinary engineering content and reports
zero redactions.

- [ ] T020 [US4] Write `tests/unit/test_redaction_false_positives.py` first and observe it fail:
      zero redactions over a git commit SHA, a UUID, a hex digest, a base64 image fragment, a dotted
      version string, a file path with dots, `Authorization: Bearer $TOKEN`, `<your-api-key>`,
      `api_key=***`, `PASSWORD=$DB_PASSWORD`, `password` used as a word in prose, a ConfigMap
      `data:` block, an `sk-` followed by a short English word, and a line reading
      `TOKEN=[REDACTED]`. Assert the conversation comes back **equal** to the input, not merely
      secret-free (SC-002, FR-015)
- [ ] T021 [US4] Tighten `patterns.py` until T020 passes without regressing T006 or T015: minimum
      lengths and alphabets on the value-shaped patterns, `kind: Secret` anchoring on the Kubernetes
      pattern, and RR-7's rejection applied to every keyed value group. Where a shape cannot be told
      apart, prefer the miss to the false positive **only** where research R5 allows it, and record
      the choice in a comment naming the rule

**Checkpoint**: recall from US1 and precision from US4 coexist, with both suites green.

---

## Phase 7: User Story 5 — nothing reaches the memory store without passing through first (Priority: P3)

**Goal**: the ordering constraint of §7 is executable, and #19 inherits it.

**Independent Test**: the composed harness with the real sanitizer never lets the secret reach the
recording memory store, and the same test fails when sanitization is removed.

- [ ] T022 [US5] Extend `tests/integration/test_pipeline_from_fakes.py`: compose
      `tests/integration/pipeline.py` with the **real** `PatternSecretSanitizer` in place of
      `InMemorySecretSanitizer`, feed a conversation carrying a synthesized secret from
      `tests/synthetic/secrets.py`, and assert what the recording store received carries the secret
      nowhere — neither in the conversation, nor in its provenance, nor in its tags (FR-017)
- [ ] T023 [US5] In the same file, add the twin that proves the guard bites: the same composition
      with sanitization taken out must fail the assertion, following the existing habit of
      `test_pl5_the_guard_itself_bites` (SC-006)

**Checkpoint**: all five stories hold. The pipeline #19 will write is now constrained by a test.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Write `tests/unit/test_redaction_cost.py`: each pattern finishes within a time bound
      on a long adversarial string built to provoke backtracking, and a several-hundred-kilobyte
      tool result — a dumped manifest — is sanitized within a bound (research R2, R12)
- [ ] T025 [P] Add a canary test to `tests/unit/test_redaction_patterns.py`: the credential-shaped
      canary of `tests/unit/test_redaction_canary.py` is redacted by this sanitizer too, so the
      logging redaction of #6 and the content redaction of #11 agree on what a credential looks like
- [ ] T026 Run [quickstart.md](./quickstart.md) end to end and correct any step whose command,
      count or expected output does not match what the code does
- [ ] T027 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` — all green, with
      no test skipped that this feature was supposed to run
- [ ] T028 Re-read [plan.md](./plan.md)'s Constitution Check against the code as written, and amend
      the plan if the implementation made an honest liar of any line in it

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001)**: none; the guard passes vacuously on the module as it stands.
- **Foundational (T002–T004)**: blocks every story. The scanner is how a pattern becomes a
  redaction.
- **US1 (T005–T014)**: after Foundational. Every later story asserts something about what US1
  produced.
- **US2 (T015–T016)**: after US1 — it sharpens the value groups US1 declared.
- **US3 (T017–T019)**: after US1; independent of US2 and US4.
- **US4 (T020–T021)**: after US1. Must be re-run against US2's suite, since tightening a pattern can
  drop a redaction US1 required.
- **US5 (T022–T023)**: after US1; independent of US2, US3 and US4.
- **Polish (T024–T028)**: last.

### Within each story

Tests are written and observed failing before the implementation that satisfies them. No exception
for "obvious" patterns: a regular expression that looks right and matches nothing is the failure
mode Principle III exists for here.

### Parallel opportunities

- T006, T007, T008, T009 are four different files and can be written in parallel, after T005.
- T010, T011, T012 all edit `patterns.py` and must be sequential.
- T017/T018 (US3), T020 (US4) and T022 (US5) are different files and can proceed in parallel once
  US1 is green.
- T024 and T025 are independent of each other.

---

## Implementation Strategy

### MVP

Phases 1–3 plus Phase 4. US1 without US2 is a sanitizer that satisfies Principle V by wrecking the
corpus, and §13 rejects it explicitly — so the two P1 stories are one increment, and the first
honest stopping point is the end of Phase 4.

### Incremental delivery

1. Setup + Foundational → a string can be scanned and rewritten.
2. US1 + US2 → the thirteen categories, redacted in place, context intact. **Stop and validate.**
3. US3 → the run is auditable.
4. US4 → the corpus is not collateral damage.
5. US5 → the ordering constraint is executable, and #19 inherits it.

### Notes

- Commit after each task or logical group; the repository's habit is a commit per green test plus
  its implementation.
- Every fixture value is synthesized. If Gitleaks fails the build, the fixture is the defect, not
  the scanner.
- Do not edit `src/hermes_memory/sanitization/sanitizer.py`. It is #9's declaration, and this feature
  is one implementation of it.
