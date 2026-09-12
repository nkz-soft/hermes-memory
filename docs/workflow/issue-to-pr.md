# Configuration: taking an issue into work automatically

A GitHub issue becomes a pull request through one command, `/issue-to-pr
<number>`, with a single human gate after planning. Spec Kit produces the
specification, the plan and the task list; the Superpowers skills govern how the
implementation is written and verified; `gh` moves the labels and opens the pull
request.

ADR-005 in [`ARCHITECTURE.md`](../../ARCHITECTURE.md) records why the loop runs
locally and why the gate sits where it does. This document records how it is
configured, so the same setup can be reproduced in another repository.

## The loop

```
/issue-to-pr 42
  │
  ├─ Phase 0   gh issue view 42 → fields of the feature-request template
  │            git worktree add --detach ../<repo>-42 origin/main
  │            gh issue edit 42 --add-label in-progress
  │
  ├─ Phase 1   /speckit-specify   → specs/<NNN>-<slug>/spec.md, reports BRANCH_NAME
  │            git switch -c <BRANCH_NAME>
  │            /speckit-clarify   → only what no assumption can settle
  │            /speckit-plan      → plan.md, checked against the constitution
  │            commit, push, comment on the issue
  │            ⏸  STOP — waits for a person
  │
  └─ Phase 2   /speckit-tasks → tasks.md
               test-driven-development per task
               verification-before-completion — commands and their output
               requesting-code-review before a reviewer sees it
               gh pr create, body composed from the PR template, Closes #42
               gh issue edit 42 --remove-label in-progress --add-label in-review
```

The command carries no state of its own. It infers the phase from the
repository: no worktree means Phase 0, a worktree without a committed `plan.md`
means Phase 1 resuming, a worktree with one means Phase 2 is due. Re-running the
command is therefore how the work is resumed after the gate, in the same session
or a later one.

## What the gate is for

Phase 1 stops unconditionally. A specification and a plan cost minutes to
redirect and exist before any code does; an implementation built on a
misunderstanding costs a review cycle and a rewrite. The stop also produces the
issue comment, which is what lets a new session — one that never saw Phase 1 —
resume without re-deriving anything.

## Prerequisites

| Requirement | Why |
|---|---|
| `gh` authenticated against the repository, with write access | reads issues, moves labels, opens the pull request |
| Spec Kit initialised in the repository | supplies `/speckit-*` and `.specify/` |
| Knowing whether Spec Kit's `before_specify` hook is installed | with the hook, `/speckit-specify` creates the feature branch; without it — the case here — the skill creates it from the reported `BRANCH_NAME` |
| The Superpowers plugin enabled | supplies the test-first, verification, review and worktree skills |
| A `main` branch that pull requests target | every branch starts from an up-to-date `origin/main` |
| The labels `in-progress` and `in-review` | mark where an issue stands |

Create the labels once:

```bash
gh label create in-progress --color FBCA04 --description "Claude is working on this" && gh label create in-review --color 0E8A16 --description "A pull request is open for this"
```

## Files that make it up

| File | Role |
|---|---|
| [`.claude/skills/issue-to-pr/SKILL.md`](../../.claude/skills/issue-to-pr/SKILL.md) | the command: phase detection, the two phases, the gate, the mistakes to avoid |
| [`.claude/settings.json`](../../.claude/settings.json) | pre-approved `gh` and `git worktree` calls, so the loop does not stall on prompts |
| [`.github/ISSUE_TEMPLATE/feature_request.yml`](../../.github/ISSUE_TEMPLATE/feature_request.yml) | the structured input Phase 0 reads |
| [`.github/pull_request_template.md`](../../.github/pull_request_template.md) | the body Phase 2 composes by hand |
| [`.claude/skills/creating-branches/SKILL.md`](../../.claude/skills/creating-branches/SKILL.md) | the branch convention both phases obey |
| [`CLAUDE.md`](../../CLAUDE.md) | points at this document from the working agreements |

`.claude/settings.json` is the shared, committed settings file. The permissions
belong there rather than in `settings.local.json`, which `.gitignore` excludes
as `*.local.json` and which therefore cannot travel with the repository.

`git worktree remove` is deliberately **not** pre-approved. Removing a worktree
can discard unmerged work, so it asks every time.

## Deliberately absent

* **No GitHub Actions workflow.** The loop runs on the developer's machine, so
  there is no API key in repository secrets, no plugin installation inside a
  runner, and no Actions minutes spent.
* **No wrapper scripts.** Spec Kit already owns the scripts under
  `.specify/scripts/`; a second layer would be code to maintain for no gain.
* **No state file.** The worktree and the committed plan already say where the
  work stands.

## Porting this to another repository

Four of the files are generic and three carry project-specific content.

**Copy as they are:**

* `.claude/skills/issue-to-pr/SKILL.md` — adjust the field-mapping table if the
  target's feature-request template differs, the constitution reference if the
  target has no constitution, and the branch step if the target has Spec Kit's
  `before_specify` hook installed (then `/speckit-specify` creates the branch and
  the explicit `git switch -c` must go, or it will fail on an existing branch).
* `.claude/settings.json` — merge the `permissions.allow` entries into whatever
  the target already has.
* `.claude/skills/creating-branches/SKILL.md` — the two branch shapes are not
  specific to this project.

**Adapt:**

* `.github/ISSUE_TEMPLATE/feature_request.yml` — Phase 0 reads its fields by
  name. Keep a problem field, a proposal field and an acceptance field, or
  update the mapping table in the skill to match what you keep.
* `.github/pull_request_template.md` — its checklists encode this project's
  failure modes. Replace them with the target's.
* `CLAUDE.md` — the pointer, and whatever the target's working agreements say
  about issues and pull requests.

**Also required in the target:** Spec Kit initialised, the Superpowers plugin
enabled, the two labels created, and `gh` authenticated. Without Spec Kit the
`/speckit-*` steps have nothing to call; without Superpowers the implementation
loses its test-first and verification gates and becomes ordinary unguarded
coding.

**Not transferable:** the references to `ARCHITECTURE.md` §21–22 and to the
constitution's principles. In a project without those documents, Phase 0's scope
check and Phase 1's compliance statement have nothing to check against — either
point them at the target's equivalents or drop both steps from the skill.
