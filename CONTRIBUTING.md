# Contributing to PARTHA

Thanks for your interest in contributing to PARTHA.

PARTHA is an AI-powered Repository Intelligence Platform. The project is built around a central Repository Intelligence Engine: repositories are analyzed once, persisted as reusable intelligence, and consumed by architecture views, dependency analysis, documentation, engineering review, AI workflows, and search.

This guide explains how to contribute safely and consistently.

## Branch Strategy

PARTHA uses three branch types:

| Branch | Purpose |
| --- | --- |
| `main` | Stable production-ready branch. |
| `dev` | Active integration branch. |
| `feature/*` | Individual feature branches. |

Contributors must never push directly to `main`.

Contributors must never push directly to `dev`.

All work must happen on a feature branch and be merged through a pull request.

## Before Starting Work

Before writing code:

1. Browse GitHub Issues.
2. Choose an unassigned issue.
3. Comment that you would like to work on it.
4. Wait until the issue is assigned to you.
5. Sync the latest `dev` branch.

```bash
git checkout dev
git pull origin dev
```

Do not start large implementation work before the issue is assigned. This avoids duplicate work and keeps project direction clear.

## Creating a Feature Branch

Create all feature branches from `dev`.

```bash
git checkout dev
git pull origin dev
git checkout -b feature/repository-intelligence
```

Use short, descriptive branch names.

Examples:

```text
feature/repository-ingestion
feature/ai-workspace
feature/documentation
feature/engineering-review
bug/github-import
bug/upload-errors
refactor/parser
docs/readme
```

## Development Guidelines

Keep contributions focused and easy to review.

- Keep changes scoped to one issue.
- Do not include unrelated fixes or formatting changes.
- Follow the existing project architecture.
- Reuse shared utilities and components.
- Avoid duplicate code.
- Write clean, maintainable code.
- Keep functions focused.
- Prefer composition over duplication.
- Ensure all relevant tests pass before opening a pull request.

If you discover an unrelated bug while working, do not fix it in the same PR. Open a separate GitHub Issue and reference it if useful.

## Repository Philosophy

PARTHA is built around a Repository Intelligence Engine.

Every feature should consume repository intelligence rather than independently parsing repositories. Avoid feature-specific implementations that duplicate repository analysis logic.

When adding or changing a feature, ask:

- Does this reuse existing repository intelligence?
- Should this logic live in the shared parser, analyzer, graph, or service layer?
- Will architecture, documentation, review, AI, and search stay consistent after this change?
- Is this implementation creating a second source of truth?

If the answer is unclear, discuss the design in the issue before implementing.

## Code Style

### TypeScript

- Use TypeScript strict mode patterns.
- Avoid `any` unless there is a clear reason.
- Remove unused imports and dead code.
- Keep components focused and readable.
- Reuse shared types, API clients, hooks, and UI components.
- Keep feature-specific hooks and components colocated where appropriate.

### Python

- Use type hints for public functions and service boundaries.
- Keep route handlers thin; place business logic in services.
- Reuse schemas, repositories, storage utilities, and analyzer layers.
- Do not duplicate parsing or repository traversal logic in feature-specific services.
- Avoid broad exception handling unless it adds useful context.

### General

- Do not commit commented-out code.
- Do not commit local environment files, generated build output, local databases, or secrets.
- Keep names clear and domain-specific.
- Prefer small, reviewable changes over large mixed PRs.

## Before Opening a Pull Request

Run the relevant checks before opening a PR.

### Frontend

```bash
npm run build:frontend
npm run lint:frontend
```

### Backend

```bash
npm run test:backend
```

### Docker

If you changed Docker, Compose, environment, or infrastructure files, run:

```bash
docker build -t partha-backend:local apps/backend
docker compose config
npm run docker:validate
```

If you cannot run a required check locally, mention that clearly in the PR description and explain why.

## Pull Request Process

All pull requests must target `dev`.

Never open a feature PR directly against `main`.

Use Conventional Commits style for PR titles.

Examples:

```text
feat(core): implement repository ingestion
fix(upload): improve GitHub import validation
refactor(parser): simplify repository parser
docs(readme): improve architecture documentation
```

### Pull Request Description

Use this structure:

```markdown
## Summary

Brief description of the change.

## Related Issue

Closes #XX

## Changes

- item
- item

## Testing

Describe how the change was tested.
```

Include screenshots or recordings for UI changes. Include request/response examples for API changes.

## Review Process

Every pull request requires review before merging.

- Do not self-merge without approval.
- Address requested changes before merging.
- Keep discussions focused and respectful.
- Use Squash Merge only.
- Make sure the final PR has a clear title and useful description.

Reviewers should check correctness, scope, architecture, security, tests, and whether the change preserves the Repository Intelligence Engine as the source of truth.

## Commit Messages

Use Conventional Commits.

Examples:

```text
feat(core): implement repository intelligence engine
feat(ai): integrate Anthropic provider
fix(upload): improve archive validation
refactor(parser): simplify dependency extraction
docs(readme): improve architecture documentation
chore(ci): update GitHub Actions workflow
```

Common types:

| Type | Use for |
| --- | --- |
| `feat` | New user-facing or system capability. |
| `fix` | Bug fix. |
| `refactor` | Code change that does not alter behavior. |
| `docs` | Documentation-only change. |
| `test` | Test additions or changes. |
| `chore` | Tooling, CI, maintenance, or housekeeping. |
| `security` | Security hardening or vulnerability fixes. |

## Reporting Bugs

If you find a bug, open a GitHub Issue with:

- a clear summary;
- expected behavior;
- actual behavior;
- reproduction steps;
- screenshots, logs, or API responses when helpful;
- environment details;
- severity if known.

If you discover unrelated bugs while working on a PR, create a separate issue instead of expanding the PR scope.

## Need Help?

If requirements are unclear:

- Ask questions in the issue.
- Discuss implementation before making major architectural changes.
- Keep communication public whenever possible.
- Share tradeoffs early if a change affects API behavior, persistence, security, or repository analysis architecture.

Thanks for helping improve PARTHA and making repository intelligence easier to build, trust, and extend.
