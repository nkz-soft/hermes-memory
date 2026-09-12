---
name: creating-branches
description: Use when creating a git branch in this repository — before `git checkout -b`, `git switch -c`, or starting work that will become a pull request.
---

# Creating branches

Branch names are data here, not decoration: Spec Kit resolves a feature's
directory from its branch name, and reviewers find a change's specification
through it. The convention is part of the constitution's Development Workflow
section.

## Two shapes, no others

| Kind of work | Shape | Example |
|---|---|---|
| Spec Kit feature | `<NNN>-<kebab-description>` | `001-chatgpt-import` |
| Anything else | `<type>/<kebab-description>` | `fix/sanitizer-jwt-pattern` |

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

A feature branch's name is not invented: `/speckit-specify` reports it as
`BRANCH_NAME`, mirroring the `specs/<NNN>-<kebab-description>/` directory it
creates. Spec Kit creates the branch itself only when its `before_specify` hook
is installed, which it is not here — so create it with that exact name
immediately after running `/speckit-specify`:

```bash
git switch -c 001-chatgpt-import
```

Feature branches are **never renamed**: the name is how the branch, its
specification directory and the workflow scripts find each other.

Names are lowercase ASCII, hyphen-separated, describe the change and not the
person, and stay under GitHub's 244-byte limit. One branch carries one pull
request.

## Branch from origin/main, and verify it

```bash
git fetch origin && git switch -c docs/retain-mission origin/main
```

Branching from whatever happens to be checked out is the failure that actually
occurs here. This repository squash-merges pull requests, so a merged branch's
commits never become ancestors of `main` even though their content is in it.
Branch off such a branch and the new pull request replays commits whose changes
`main` already has: the diff balloons with files that look re-added.

Before pushing, confirm the branch contains only your own work:

```bash
git log --oneline origin/main..HEAD
```

If commits appear that belong to an already-merged pull request, rebase onto the
current main and keep only yours:

```bash
git rebase --onto origin/main <the merged branch's remote ref> <your branch>
```

Use the branch's **remote** ref (`origin/docs/architecture`), not the local one —
a local branch may sit ahead of its remote, and the rebase would silently drop
the commits in between.

## Common mistakes

| Mistake | What happens |
|---|---|
| `feature/…`, `bugfix/…`, `hotfix/…` | Not in the type list; use `feat`, `fix` |
| Renaming a Spec Kit branch | Branch no longer matches its `specs/` directory |
| Hand-creating `002-something` | Feature numbering and directory come from `/speckit-specify`; only the `git switch -c` is yours |
| `nkz/import-fix`, `my-changes` | Names the author or nothing; name the change |
| Branching from the last branch you were on | Squashed history replays as a duplicated diff |
| Two unrelated changes on one branch | They cannot be reviewed or reverted separately |
