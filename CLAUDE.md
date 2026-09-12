# hermes-memory — working agreements

Read [`.specify/memory/constitution.md`](.specify/memory/constitution.md) before planning or
implementing. It is binding: five principles, the fixed technology stack, and the review gates.
[`ARCHITECTURE.md`](ARCHITECTURE.md) holds the design and the decision records.

## Workflow

Work is spec-driven: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`. Specs and plans are committed with the code they produce. Every plan states
how it complies with the principles, and justifies deviations in writing.

All repository content — code, comments, documentation, commit messages, issue and PR text — is
written in English.

## Taking an issue into work

`/issue-to-pr <number>` carries a feature-request issue to a pull request: Spec Kit for the
specification and plan, a stop for a human, then implementation and the pull request. Work happens
in a git worktree at `../hermes-memory-<number>`, outside this checkout. Re-running the same command
is how the work resumes after the gate — the phase comes from the worktree and the committed plan,
not from the conversation. [`docs/workflow/issue-to-pr.md`](docs/workflow/issue-to-pr.md) describes
the configuration; ADR-005 records why it works this way.

## Creating issues

GitHub applies `.github/ISSUE_TEMPLATE/` only to issues opened through the web form. Issues created
through the API or `gh` — including those from `/speckit-taskstoissues` — bypass the templates, so
the body must be composed to match them by hand.

When creating an issue programmatically, reproduce the matching template's structure as Markdown
headings, one per template field, in the template's order:

| Situation | Template to mirror | Labels |
|---|---|---|
| A task from `tasks.md` | `.github/ISSUE_TEMPLATE/speckit_task.yml` | `task` |
| A defect | `.github/ISSUE_TEMPLATE/bug_report.yml` | `bug` |
| A proposed change | `.github/ISSUE_TEMPLATE/feature_request.yml` | `enhancement` |

For tasks, the title must be exactly `T<id>: <description>` (for example `T001: Create project
structure`). `/speckit-taskstoissues` deduplicates by matching that id in existing titles, so any
other shape produces duplicates on the next run.

Leave a template field out only when it genuinely does not apply, and say so in one line rather
than emitting an empty heading.

## Creating pull requests

Compose the PR body from [`.github/pull_request_template.md`](.github/pull_request_template.md):
`gh pr create` does not apply the template when `--body` is passed. Keep its checklists, tick only
what is actually true, and state why under any box left unticked. The verification section holds
the commands that were run and their outcome — never a claim without a command.

## Handling history data

Conversation exports and archives live under `data/`, which is ignored and never committed. Do not
paste conversation content, credentials or tokens into issues, PRs, commit messages or fixtures;
test fixtures use synthesized conversations. This repository is public, and the data it processes
is private engineering history.
