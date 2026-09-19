# Contract: redaction rules

**Feature**: 009-secret-sanitizer (issue #11)

What `PatternSecretSanitizer` must do, stated as rules a test can be written against. Rules RR-1 to
RR-9 hold for the sanitizer as a whole; rules RC-1 to RC-13 hold per §13 category, one per fixture
required by SC-001. The boundary's own rules SS-1 to SS-8 — from
`specs/007-boundary-interfaces/contracts/contract-suites.md` — continue to apply unchanged and are
not restated here.

Placeholders in examples are written as `‹…›` and stand for a synthesized sample of the shape;
no example in this repository contains a real credential.

## Rules for the sanitizer

**RR-1 — The replacement is the literal `[REDACTED]`.** Not a per-category marker, not a mask of the
original length, not an elision. The length of the original must not be inferable from the result.

**RR-2 — Only the value is replaced.** For a keyed pattern, the key and the separator survive:
`DATABASE_PASSWORD=‹value›` becomes `DATABASE_PASSWORD=[REDACTED]`. For a delimited block, the
markers survive. For a value-shaped pattern, the text before and after the value survives.

**RR-3 — Every text-bearing field is scanned.** `Conversation.title`; for each `Message`, `.text`;
for each `ToolActivity`, `.name`, `.request`, `.result`; for each `NonTextPart`, `.name`. Adding a
text-bearing field to the model of #8 without adding it here must fail a test.

**RR-4 — Identity fields are never scanned.** `source`, `source_id`, `started_at`,
`last_activity_at`, `Message.role`, `Message.sent_at`, `NonTextPart.kind` are copied unchanged, so
`document_id` is the input's (research R1).

**RR-5 — Every occurrence is replaced.** The same value twice in one string is redacted twice and
counted twice; two different values in one string are both redacted.

**RR-6 — An overlapping region is redacted once, under the higher-precedence category.** The
precedence order is the table's: private key → Anthropic → OpenAI → GitHub → GitLab → AWS access key
id → JWT → Kubernetes secret → connection string → bearer token → API key → AWS secret access key →
password → `.env` value.

**RR-7 — A placeholder is not a secret.** A keyed value is left alone when it is a variable
reference (`$VAR`, `${VAR}`, `%VAR%`, `{{ var }}`), a documentation placeholder (`<your-api-key>`,
`xxx`, `***`, `changeme`, `...`), empty, already `[REDACTED]`, or below the category's minimum
length.

**RR-8 — Sanitization is idempotent.** Sanitizing a sanitized conversation returns an equal
conversation and an empty report.

**RR-9 — Sanitization is deterministic and offline.** No clock, no network, no model, no dependence
on processing order. The same conversation sanitizes to the same result on every run and on every
machine.

## Rules per category

Each rule names what must be redacted and, where the shape invites a false positive, what must
survive. The "kept" column is the assertion that distinguishes this feature from deleting content.

**RC-1 — `api-key`.** Keyed: `api_key`, `apikey`, `api-key`, `x-api-key` as an assignment, a header
or a query parameter. Redacted: the value. Kept: the key, the header name, and the rest of the URL.

**RC-2 — `bearer-token`.** Keyed: `Authorization: Bearer ‹token›`, and `PRIVATE-TOKEN: ‹token›`
where the value is not already matched as a GitLab token. Redacted: the token. Kept:
`Authorization: Bearer [REDACTED]` — the scheme is the knowledge.

**RC-3 — `jwt`.** Value-shaped: three base64url segments separated by dots, the first beginning
`eyJ`. Redacted: the whole token, including the signature. Kept: everything around it. Must not
match: a dotted version string, a file path, or two base64 words separated by a period.

**RC-4 — `github-token`.** Value-shaped: `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` followed by the
documented length, and `github_pat_` followed by its longer body. Must not match: the bare prefix,
or a word beginning `gh` in prose.

**RC-5 — `gitlab-token`.** Value-shaped: `glpat-` and its sibling prefixes followed by the
documented length. Kept: §13's own example — `GitLab request using token [REDACTED] returned HTTP
401 Unauthorized`.

**RC-6 — `anthropic-key`.** Value-shaped: `sk-ant-` followed by its body. Precedence above
`openai-key`, whose `sk-` is a prefix of it.

**RC-7 — `openai-key`.** Value-shaped: `sk-` and `sk-proj-` followed by the documented body length
and alphabet. Must not match: `sk-ant-…` (RC-6 owns it), or `sk-` followed by a short word.

**RC-8 — `aws-access-key`.** Value-shaped for the id: `AKIA`, `ASIA`, `AGPA`, `AIDA`, `AROA`,
`ANPA`, `ANVA`, `AIPA` plus sixteen uppercase alphanumerics. Keyed for the secret:
`aws_secret_access_key`, `AWS_SECRET_ACCESS_KEY`, `--secret-access-key`. Both report under this one
category (research R6). Must not match: forty characters of base64 with no key beside them.

**RC-9 — `private-key`.** Delimited block: from `-----BEGIN ‹…›PRIVATE KEY-----` to
`-----END ‹…›PRIVATE KEY-----`, including an `OPENSSH`, `RSA`, `EC`, `DSA` or `PGP` variant.
Redacted: the body, in one span across its line breaks. Kept: both markers, so the reader still
learns a private key was there.

**RC-10 — `password`.** Keyed: `password`, `passwd`, `pwd` as an assignment (`=`, `:`, `: ` in
YAML/JSON) or as a command-line flag (`--password ‹v›`, `-p‹v›` is out of scope). Kept: the key.
Must not match: the word `password` in a sentence, or a key whose value is a placeholder (RR-7).

**RC-11 — `connection-string`.** Keyed by structure: a URI of the form
`‹scheme›://‹user›:‹secret›@‹host›`, for at least `postgres`, `postgresql`, `mysql`, `mongodb`,
`mongodb+srv`, `redis`, `rediss`, `amqp`, `amqps`, `http` and `https`. Redacted: the password
component only. Kept: scheme, user, host, port, path — a connection string with the password gone
is still the knowledge of which database was involved.

**RC-12 — `dotenv-value`.** Keyed by name shape: an assignment whose key ends in `_TOKEN`, `_SECRET`,
`_KEY`, `_PASSWORD`, `_PASS`, `_CREDENTIALS` or equals `TOKEN`/`SECRET`, in a `.env`-style line or
its quoted form. Kept: the key name, which is usually what makes the line worth keeping. Must not
match: a key ending in `_KEY` whose value is a placeholder or a variable reference, or a
non-assignment mention of the name in prose.

**RC-13 — `kubernetes-secret`.** Keyed by manifest: within a text containing `kind: Secret`, the
values under `data:` and `stringData:`; and the value in
`kubectl create secret ‹…› --from-literal=‹key›=‹value›`. Kept: the kind, the metadata, the keys.
Must not match: a `data:` block in a manifest that is not a Secret — a ConfigMap keeps its values.

## What a conforming implementation must ship with

- One fixture per RC rule, asserting both the redaction and the "kept" clause (SC-001).
- A false-positive suite covering, at minimum: a commit SHA, a UUID, a base64 image fragment, a hex
  digest, `Authorization: Bearer $TOKEN`, `<your-api-key>`, `password` as a word,
  `PASSWORD=$DB_PASSWORD`, a ConfigMap `data:` block, and a dotted version string (SC-002).
- A test that each synthesized sample matches the pattern it is a sample of (research R11).
- An adversarial-input test bounding the time each pattern takes on a long hostile string
  (research R2).
