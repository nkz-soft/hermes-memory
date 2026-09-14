---
name: issue-to-pr
description: Use when taking a GitHub issue into work end to end — "implement issue 42", "take #42", `/issue-to-pr <number>` — driving it through Spec Kit to a pull request with one human gate after planning.
---

# Taking an issue from GitHub to a pull request

One command, `/issue-to-pr <number>`, carries a feature request from an issue to
a pull request. It runs in two phases separated by a gate: the first produces a
specification and a plan and then **stops** for a human, the second implements
and opens the pull request.

The command is idempotent. Run it again with the same number and it resumes
from wherever the repository says the work stands — there is no state file.

## Detect the phase first, before anything else

| What exists | Phase to run |
|---|---|
| No worktree at `.claude/worktrees/<number>` | Phase 0, then Phase 1 |
| Worktree exists, no `plan.md` in its feature directory | Phase 1, resuming |
| Worktree exists and `plan.md` is committed | Phase 2 — but only with the human's go-ahead |

```bash
git worktree list
```

Never guess from the conversation. A session that began after the gate has no
memory of Phase 1, which is exactly why the gate leaves its record in the issue.

## Phase 0 — read the issue, then isolate the work

```bash
gh issue view <number> --json number,title,body,labels,state
```

The issue body follows `.github/ISSUE_TEMPLATE/feature_request.yml`. Map its
fields, and stop rather than improvise if the shape is unrecognizable:

| Field in the issue | Where it goes |
|---|---|
| Problem, Proposal | the description handed to `/speckit-specify` |
| How we would know it works | the acceptance criteria in `spec.md` |
| Alternatives considered | the alternatives section of `plan.md` |
| Scope | checked against ARCHITECTURE.md §21–22 |
| Governance impact | any tick but "None of the above" obliges `plan.md` to carry a decision record |

**Stop and ask the human** when the issue is closed, already carries
`in-progress`, is labelled `bug` or `task` rather than `enhancement` (those are
not this command's shape of work), or when Scope reads "Currently out of scope"
— changing scope is a decision for a person, not a side effect of
implementation.

Then isolate the workspace, per superpowers:using-git-worktrees:

```bash
git fetch origin
git worktree add --detach .claude/worktrees/<number> origin/main
gh issue edit <number> --add-label in-progress
```

`--detach` matters, because the feature branch's name is not known yet: Spec Kit
derives it in the next phase. Everything from here on runs **inside the
worktree**, never in the primary checkout.

The worktree sits inside the primary checkout, under a path `.gitignore`
excludes, so that it is part of the session's working directory and the file
tools reach it without a permission prompt for every read and write. Being
ignored, it is invisible to `git status`, to `ruff`, and to any other tool that
honours `.gitignore`; `pytest` is confined to `testpaths` and never descends
into it either.

## Phase 1 — specify and plan, then stop

Run inside the worktree, in order:

1. `/speckit-specify` with the description built in Phase 0. It creates
   `specs/<NNN>-<kebab-description>/spec.md` and reports `BRANCH_NAME` and
   `FEATURE_NUM`. It does **not** create a git branch: in this repository Spec
   Kit's `before_specify` hook is not installed, so the branch is yours to
   create, immediately and with exactly the reported name:

   ```bash
   git switch -c <BRANCH_NAME>
   ```

   The name mirrors the feature directory and is never renamed — see the
   `creating-branches` skill. Do not invent the number; it comes from Spec Kit.
2. `/speckit-clarify` for whatever genuinely cannot be settled by assumption.
   Anything that can be is recorded as an assumption in `spec.md` instead of
   spent as a question.
3. `/speckit-plan`. The plan must state how the change complies with the
   constitution's five principles and justify every deviation in writing.
4. Commit and push the specification and the plan.
5. Comment on the issue, then stop.

The comment is the gate's record, and a later session reads it to pick the work
back up. It holds: the feature directory and branch, what the issue was
understood to ask for, every assumption taken, anything still open, and the
commit the specification landed in.

```bash
gh issue comment <number> --body-file <path>
```

**Then stop and report to the human.** Do not run `/speckit-tasks`, do not write
implementation code, and do not open a pull request. Phase 2 begins only when a
person says so — waiting is the point of the gate, not an obstacle to it.

## Phase 2 — implement and open the pull request

Only after the human's go-ahead, inside the same worktree:

1. `/speckit-tasks` to generate `tasks.md`.
2. Implement it. `/speckit-implement` drives the task list;
   superpowers:test-driven-development governs each task — the test is written
   first and observed to fail before the implementation exists. Principle III of
   the constitution is non-negotiable, so a task that skips it is not done.
3. superpowers:verification-before-completion before any claim of completeness.
   Run the commands, read the output, and quote it. "Tests pass" without the
   command is not verification.
4. superpowers:requesting-code-review on the finished branch, and fix what it
   finds before a reviewer sees it.
5. Open the pull request. `gh pr create` does not apply
   `.github/pull_request_template.md` when `--body` is passed, so compose the
   body from that template by hand: keep its checklists, tick only what is
   actually true, say why under any box left unticked, and put the commands that
   were actually run in the verification section. Reference the issue with
   `Closes #<number>`.
6. Move the labels:

```bash
gh issue edit <number> --remove-label in-progress --add-label in-review
```

Leave the worktree in place. It is the reviewer's and yours until the pull
request merges; superpowers:finishing-a-development-branch covers removing it
afterwards.

## Common mistakes

| Mistake | What happens |
|---|---|
| Implementing straight through the gate | The human loses the one cheap chance to correct course, before code exists |
| Working in the primary checkout | The user's workspace is occupied for the whole run, and two issues cannot proceed at once |
| Assuming `/speckit-specify` created the branch | Work accumulates on a detached HEAD and there is nothing to push |
| Naming the branch yourself instead of using `BRANCH_NAME` | The branch stops matching its `specs/` directory |
| Inferring the phase from the conversation | A resumed session redoes Phase 1 and orphans the first specification |
| Branching the feature off the current branch | Squash-merged history replays as a duplicated diff |
| `gh pr create --body` with a hand-written body | The template's checklists vanish and the review gates go unanswered |
| Answering a Governance tick with no decision record | A principle changes silently, which the constitution's Governance section forbids |
