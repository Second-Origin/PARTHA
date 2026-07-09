# Release Management

PARTHA uses pull requests into `dev` for integration and `main` for stable release snapshots.

## Versioning

Use SemVer-style tags:

```text
vMAJOR.MINOR.PATCH
```

Examples:

- `v0.1.0` for the first operational baseline.
- `v0.1.1` for a patch release.
- `v0.2.0` for compatible feature or platform additions.

## Release Workflow

The `.github/workflows/release.yml` workflow validates release candidates on `v*` tags. It runs:

- frontend install, lint, and build;
- backend install and tests;
- backend Docker image build;
- Docker Compose runtime readiness validation;
- GitHub Release note generation for tag pushes.

## Release Checklist

Before tagging:

- PRs are merged through review.
- CI is green on `dev`.
- The release branch or `main` contains the intended commits.
- `README.md` and docs match shipped behavior.
- New migrations have been run against a staging database.
- Rollback notes are clear for any persistence changes.

Create a release tag:

```bash
git checkout main
git pull origin main
git tag v0.1.0
git push origin v0.1.0
```

## Hotfixes

For urgent fixes:

1. Branch from `main`.
2. Apply the smallest safe fix.
3. Run the release validation workflow.
4. Merge back into `main`.
5. Forward-merge or cherry-pick into `dev`.
