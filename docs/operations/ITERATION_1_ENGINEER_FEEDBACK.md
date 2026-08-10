# Iteration 1 engineer feedback

PARTHA Iteration 1 applies the current product design to the existing authenticated workflow. It does not add new repository facts or product surfaces: Architecture, Dependencies, Engineering Review, Insights, Documentation, exports, and optional AI continue to consume the selected sealed Repository Intelligence snapshot.

## What to test

Use a repository you are authorised to inspect and complete these tasks:

1. Create an account or sign in.
2. Upload a supported archive, or import a public GitHub repository URL.
3. Wait for analysis to complete, then move between Dashboard, Architecture, Dependency Graph, Engineering Review, Documentation, and Insights.
4. Resize the browser to a narrow mobile viewport and confirm navigation and page controls remain usable without page-level horizontal scrolling.
5. In Architecture, switch among Graph, Request Flow, Heatmap, and List View. Confirm graph labels remain readable and revision-manifest controls remain reachable.
6. In Settings → AI Providers, save a provider configuration and use Test Connection. Then open AI Workspace and submit a question.

AI is optional. Provider questions receive structural context from the sealed snapshot; PARTHA does not send repository source-file contents through this workflow, and provider prose has no automatic source citations.

## What to report

Open a GitHub issue using the appropriate template and include:

- the task you were trying to complete;
- expected and actual behaviour;
- browser, operating system, and viewport size;
- the affected PARTHA page;
- a screenshot or short recording with credentials, repository secrets, email addresses, and other personal data removed;
- whether the problem blocks the workflow or has a workaround.

Do not attach private source code, provider keys, session tokens, `.env` files, or unredacted repository content.

## Local verification

Before proposing a frontend change, run:

```bash
npm --prefix apps/frontend run test
npm run lint:frontend
npm run build:frontend
```

For the full repository validation sequence, follow [CONTRIBUTING.md](../../CONTRIBUTING.md).
