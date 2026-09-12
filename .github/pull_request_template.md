<!--
Keep this short. The checklists exist because the project's failure modes are silent:
an unstable document id, an unredacted token or a Hindsight import in the wrong module
does not break a build — it corrupts the memory bank or leaks a credential.
-->

## What this changes

<!-- One paragraph. What changed and why, not a list of files. -->

## Related

<!-- Closes #123, and the feature directory this implements, e.g. specs/001-chatgpt-import -->

## Constitution compliance

- [ ] **Test-first** — the tests were written first, failed, and now pass
- [ ] **Raw archive** — nothing makes the raw archive optional or derived from Hindsight
- [ ] **Identity** — `document_id` stays deterministic; original timestamps are preserved; a re-run creates no duplicates
- [ ] **Boundaries** — Hindsight is referenced only inside `memory/hindsight`
- [ ] **Secrets** — sanitization runs before anything leaves for Hindsight; no credentials in code, logs or fixtures
- [ ] **Stack** — no dependency added that displaces a choice in ADR-004 (if one is, this PR adds the decision record)

<!-- If a box cannot be ticked, say why here. An unjustified deviation is a reason to change the design, not to ignore the principle. -->

## Verification

<!--
The commands you actually ran, with their outcome. "Tests pass" without the command is not verification.
-->

```text
uv run pytest
```
