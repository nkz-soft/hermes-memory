# Research: Secret sanitizer

**Feature**: 009-secret-sanitizer (issue #11) | **Date**: 2026-09-18

Every decision here is settled from ARCHITECTURE.md §§8, 13, 14, the constitution's Principles
I–V, the boundary #9 already declares, and the model #8 already declares. Nothing is left as
NEEDS CLARIFICATION.

## R1 — How the conversation is rewritten: named fields, not a generic walk

**Decision**: rewrite the text-bearing fields of #8's model by name — `Conversation.title`, each
`Message.text`, each `ToolActivity.name`, `.request` and `.result`, each `NonTextPart.name` — and
stand a structure test beside it that enumerates the model's fields and fails when one is added
that the rewriter does not visit.

**Rationale**: the tempting alternative is a recursive walk that redacts every string it meets, so
that a field added later is covered for free. It is wrong here for one specific reason: it would
also redact `source_id`. A native identifier is an opaque token of exactly the shape several
patterns look for, and redacting it changes `document_id` — which is Principle II's stable identity
and SS-2's assertion. The generic walk trades a guaranteed identity for a hypothetical field.

The guard test buys back what the generic walk offered: the failure mode "someone added a field and
forgot the sanitizer" becomes a red test rather than a silent leak, and the person adding the field
is told, in the commit that adds it, which side of the line it falls on.

**Alternatives considered**: redact the serialized JSON and re-validate — rejected: it exposes
structural keys and enum values to the patterns, it cannot tell a value from an identifier, and a
redaction that breaks the JSON breaks the conversation. Recursive walk over all strings — rejected
above. Marking fields on the model itself (`Annotated[..., Sanitize]`) — rejected: it puts the
sanitizer's concern inside #8's model, which every stage depends on, for one consumer.

## R2 — The pattern engine: the standard library `re`, compiled once

**Decision**: patterns are `re` regular expressions, compiled at import into one ordered table.
No new dependency.

**Rationale**: the stack table fixes the dependencies and adding one needs a decision record
(constitution, Additional Constraints). Nothing here needs `regex`'s extras: the patterns are
anchored on literal prefixes, keyword keys or delimiters, which `re` expresses directly.

**Cost to manage**: `re` backtracks, and a pattern with nested unbounded quantifiers over attacker-
shaped text is a way to make an import hang on a conversation. Every quantifier in the table is
bounded, and none is nested inside another; a test feeds each pattern a long adversarial string and
bounds the time.

**Alternatives considered**: `regex` with a timeout — rejected, a dependency for a problem bounded
quantifiers already solve. An entropy scorer over tokens — rejected, see R5. A model-based
detector — rejected outright: it sends the content out of the process, which Principle V forbids,
and it makes sanitization non-deterministic (FR-011).

## R3 — Three shapes of pattern, and why the keyed shape is the interesting one

**Decision**: every category is expressed as one of three shapes.

| Shape | What it matches | What is replaced | Categories |
|---|---|---|---|
| **Value-shaped** | a credential recognizable by itself, from its prefix and alphabet | the whole match | GitHub, GitLab, Anthropic, OpenAI, AWS access key id, JWT |
| **Keyed** | a key that names a secret, plus its value | the **value group only** | API key, bearer token, password, connection string, `.env` value, Kubernetes secret, AWS secret access key |
| **Delimited block** | a `BEGIN`/`END` envelope | the body between the markers | private key |

**Rationale**: this is §13's requirement made mechanical. `DATABASE_PASSWORD=[REDACTED]` keeps the
key, which is the knowledge; `password=[REDACTED]` on its own would be an unhelpful line. The same
is true of a PEM block: `-----BEGIN RSA PRIVATE KEY-----\n[REDACTED]\n-----END RSA PRIVATE KEY-----`
still tells a reader what was there, which is often the whole point of the message.

A keyed pattern is also the only honest way to catch the categories that have no shape of their own.
A password is any string; an AWS secret access key is forty characters of base64 alphabet, which is
also what a hash, an id and a chunk of base64 payload look like. Matching those by shape alone is
the false-positive machine of R5.

**Alternatives considered**: replacing the whole match everywhere — rejected, it destroys the key
and with it the context §13 exists to protect. Replacing with a per-category marker
(`[REDACTED:aws]`) — rejected: the marker names the category and the category is in the report; a
value-shaped marker in the text is a hint about the secret that the report deliberately does not
carry, and the issue fixes the literal `[REDACTED]`.

## R4 — Overlapping matches: collect spans, resolve by specificity, rewrite once

**Decision**: scanning a string is one pass per pattern collecting `(start, end, category,
precedence)` spans, then a resolution step that sorts by start and drops any span overlapping one
already kept with higher precedence, then a single rebuild of the string from the surviving spans.
Precedence is the table's order, most specific first.

**Rationale**: the cases are real. A JWT arrives as `Authorization: Bearer eyJ...`, which the bearer
pattern and the JWT pattern both match; a connection string carries a password that the password
pattern also sees. Rewriting pattern by pattern would redact the region twice, count it twice
(FR-013 counts occurrences replaced, so a double count is a lie), and in the worst case rewrite
`[REDACTED]` itself. Resolving spans first makes "redacted once, counted once, under the more
specific category" (FR-014) a property of the algorithm rather than of the pattern order's luck.

**How resolution stays linear.** Spans are grouped by pattern and merged into the kept list in
table order, one walk per pattern: within a pattern `finditer` yields non-overlapping matches in
order, and the kept list is disjoint and in order by construction, so a single merge settles every
overlap between them. The obvious version — asking `any(...)` over the kept list per span — is
quadratic; it survived review of the first implementation because the cost suite's large fixture
contained no matches at all, and it cost 11.6 seconds on one field of a 20 000-entry manifest.

The precedence order, most specific first: private key block → vendor-prefixed keys (Anthropic
before OpenAI, since `sk-ant-` is a prefix of the `sk-` family) → GitHub → GitLab → AWS access key
id → JWT → Kubernetes secret → connection string → bearer token → API key → AWS secret access key →
password → `.env` value.

**Alternatives considered**: iterative `re.sub` per pattern — rejected above. One giant alternation
with named groups — rejected: it makes precedence implicit in the alternation order, and a pattern
becomes unreadable and untestable on its own.

## R5 — Precision: recall wins, but placeholders and references are never redacted

**Decision**: a keyed pattern's value group is rejected — matched, then not redacted — when it is a
variable reference (`$TOKEN`, `${TOKEN}`, `%TOKEN%`, `{{ token }}`), a documentation placeholder
(`<your-api-key>`, `xxx`, `***`, `changeme`, `...`), already `[REDACTED]`, or shorter than a
category minimum. Value-shaped patterns carry their own minimum length and alphabet.

**Rationale**: these are the shapes the corpus is full of — a README line, an example `curl`, a
docker-compose file quoted into a chat — and redacting them replaces knowledge with noise while
protecting nothing, which is the quiet version of the failure §13 rejects. They are also the exact
shapes a false-positive suite can enumerate (SC-002), unlike a tolerance.

Rejecting `[REDACTED]` is also what makes FR-012 true: sanitizing twice finds nothing the second
time, so a conversation replayed from the archive and re-sanitized reports nothing.

**Alternatives considered**: entropy thresholds over every token — rejected: it redacts commit
SHAs, UUIDs and base64 fragments, it cannot be pinned by a fixture, and it moves as the corpus
moves. A tolerance expressed as a false-positive rate — rejected: untestable as a fixture, so the
spec bounds precision by named shapes instead.

## R6 — AWS: the id by shape, the secret by key

**Decision**: the access key **id** is matched by shape (`AKIA`, `ASIA`, `AGPA`, `AIDA`, `AROA`,
`ANPA`, `ANVA`, `AIPA` followed by sixteen uppercase alphanumerics). The **secret access key** is
matched only when keyed — `aws_secret_access_key = ...`, `AWS_SECRET_ACCESS_KEY=...`,
`--secret-access-key ...` — and both report under `aws-access-key`.

**Rationale**: an AWS secret access key is forty characters of `[A-Za-z0-9/+=]`. So is a base64
line, a hash rendering and half the payloads an engineering conversation quotes. Matching it by
shape would make the false-positive suite unsatisfiable. Keyed matching catches it where it
actually appears in history — in a `.env`, an `aws configure` transcript, a CI variable dump —
which is next to its name.

Both report under one category because §13 names one, and #9 fixed the vocabulary.

## R7 — Kubernetes secrets: scoped to the Secret's own data block, not to the text

**Decision**: for each `data:` or `stringData:` key, ask whether the mapping *it belongs to* declares
`kind: Secret` — its siblings at the same indent, bounded by a `---`, by a list item's start and by
any line indented less — and if so redact the values in its block. Additionally, redact the value of `--from-literal=<key>=<value>` in a
`kubectl create secret` command line. Everything else in the manifest — the kind, the metadata, the
keys — is kept.

**Revised twice during implementation, both times because review probed a shape the fixtures did
not have.** It is worth recording the two wrong answers, because each looked right:

1. **"The text contains `kind: Secret`"**, with the pattern matching any indented `key: value` line.
   It redacted the Secret's own `metadata:` values and, in a multi-document YAML, the ConfigMap in
   the document beside it — what RC-13's "Kept" and "Must not match" clauses forbid in as many
   words.
2. **"`kind: Secret` at column 0, in the same `---` document."** It missed the shape most likely to
   reach a conversation at all: `kubectl get secrets -o yaml` wraps every Secret in a `v1/List` and
   indents its `kind` by two columns, so a `token:` in a real listing went through unredacted —
   strictly worse than the version it replaced. It also missed every CRLF manifest, because the
   anchors ended `[ \t]*$` and `\r` is in neither class.

The third answer asks the question of the enclosing mapping, which is what YAML actually means by
"this Secret's data". It is computed in code, line by line, because neither relation — *my* mapping,
*my* document — fits in a lookbehind, and because a line-by-line parse is where `\r`, a `- ` list
marker, a quoted `kind` and a trailing comment can each be handled in one place. Scoping it this way
also let the value alphabet widen, which is what made `stringData:` values with hyphens work, and it
makes the regions disjoint: a `data:` nested under another key has different siblings, so it is not a
Secret's block and cannot produce a second region inside the first.

**Rationale**: the thing that makes a base64 line a secret is the manifest around it, so the
manifest is what the pattern anchors on. Redacting `data:` values in any YAML would empty
ConfigMaps and every other manifest quoted in a conversation; redacting base64 anywhere is R5's
mistake.

**Known limit, recorded rather than hidden**: a `data:` block quoted without its `kind: Secret`
line — the middle of a manifest pasted alone — is not recognized by this pattern. Where it carries
a keyed name (`*_TOKEN`, `*_PASSWORD`) the `.env`-value pattern still catches it. The residue is a
bare base64 value with a neutral key and no context, which no pattern can tell from a ConfigMap.

## R8 — The sanitizer logs nothing; the report is the audit trail

**Decision**: the sanitizer emits no log event. It returns the report, and the caller — #19's
pipeline, which already carries the run's logging (§18) — decides what to record.

**Rationale**: Principle V forbids logging conversation content, and the surest way to keep a
sanitizer from logging content is for it not to log. The report already carries what an audit needs
(FR-008), the pipeline harness of #9 already merges reports across a run, and a boundary that logs
on its own makes every test of it a test of logging too.

**Alternatives considered**: one content-free event per conversation — rejected: it duplicates what
the report carries, at the boundary least able to afford a mistake about what is in scope.

## R9 — Where the code lives

**Decision**: inside `hermes_memory.sanitization`, beside the boundary it implements:

* `patterns.py` — the table: one entry per pattern with its category, compiled expression, value
  group and precedence, plus the placeholder rejection of R5.
* `scanner.py` — spans over one string: find, resolve overlaps (R4), rebuild, count.
* `sanitizer.py` — **unchanged**; it holds #9's protocol, report and error.
* `pattern_sanitizer.py` — `PatternSecretSanitizer`, the conversation traversal of R1, exported from
  the package's `__init__`.

**Rationale**: the constitution's module tree fixes `sanitization` as the module; the split inside
it is along the two things that are separately testable — does this string match, and is the
conversation rewritten correctly. Leaving `sanitizer.py` alone keeps #9's declaration readable as a
declaration; an implementation appended to it would blur the boundary with its first implementation,
which is the thing Principle IV is written against.

## R10 — The pipeline guard already has a home

**Decision**: FR-017's guard is added to `tests/integration/test_pipeline_from_fakes.py`, composing
the existing harness `tests/integration/pipeline.py` with the **real** sanitizer in place of the
fake, and asserting the recording memory store never saw the secret. A second test removes
sanitization from the composition and asserts the guard fails.

**Rationale**: #9 already built the harness and the recording fakes, and the spec's assumption was
that the guard would be written against them. Using the real sanitizer there is what makes the
guard about this feature rather than about the fake, and the "guard bites" test is the repository's
existing habit (`test_pl5_the_guard_itself_bites`).

When #19 writes the real pipeline, it inherits an executable statement of the ordering constraint
rather than a sentence in a document.

## R11 — Fixtures are synthesized, and proved to be of the right shape

**Decision**: every fixture credential is generated by the test suite from the category's documented
shape — a fixed alphabet and length, with a literal marker inside it where the shape allows — and a
test asserts each sample matches its category's pattern and that no sample is a real-looking key
from a real service.

**Rationale**: CLAUDE.md forbids real credentials in the repository, and this is a public one.
Gitleaks runs in CI (#7) and will fail the build on a committed key-shaped literal, so a synthesized
sample that still matches the pattern is both the safe and the only workable choice. The
"samples match their patterns" test is what keeps a fixture from drifting into something the
pattern no longer recognizes, which would make a green suite meaningless.

## R12 — Cost is linear in the text, and bounded per conversation

**Decision**: patterns compile once at import; each string is scanned once per pattern; the rebuild
is a single join. No per-conversation compilation, no quadratic re-scan of a rewritten string.

**Rationale**: the sanitizer runs over every message of a decade of history, and it runs on the
critical path of an import that also pays for extraction. A test sanitizes a large tool result —
a dumped manifest, hundreds of kilobytes — and bounds the time, which is the shape of a regression
that a unit test over three-line fixtures would never show.
