# PARTHA Engineering Audit Report

Date: 2026-07-08

## Current Architecture

PARTHA is a Vite, React, TypeScript single-page app using React Router, Zustand, Tailwind CSS, React Flow, Monaco, Framer Motion, and a small service/API layer. The current shape is:

Presentation -> Pages/Feature Components -> Stores + Services -> API Client -> Backend

The target shape should be:

Presentation -> Feature Hooks -> Services -> API Client -> Backend

No runtime component calls `fetch` directly. Network calls are centralized in `src/services/api/client.ts`; the only other `fetch` occurrences are generated sample-code strings in `src/features/explorer/fileUtils.ts`.

## Changes Completed During Audit

- Added real linting via `eslint.config.js` and made `npm run lint` pass.
- Enabled `noUnusedLocals` and `noUnusedParameters` in `tsconfig.json`.
- Converted routes in `src/routes/router.tsx` to route-level lazy loading.
- Removed unused scaffold files: `.bolt/`, `next-env.d.ts`, `.DS_Store`, and the unused `.env`.
- Added `.env.example` with the actual supported `VITE_API_URL` key.
- Removed unused source files: `src/components/shared/FileExplorer.tsx`, `src/components/shared/Skeleton.tsx`, and `src/hooks/useAsync.ts`.
- Removed unused runtime dependencies, including Radix UI packages, React Hook Form, Zod, Class Variance Authority, and React Query.
- Upgraded Vite tooling and added a DOMPurify override to resolve `npm audit` findings.
- Fixed unused imports, unsafe `any`, stale review loading behavior, and ESM config cleanup.

## Strengths

- Feature folders exist for architecture, explorer, and review.
- API client has retries, timeout handling, auth hook points, upload progress, streaming support, and typed errors.
- Components do not directly call the backend.
- The app now passes lint, TypeScript, production build, and dependency audit.
- Route lazy loading materially reduces the initial bundle.
- TypeScript strict mode is enabled.

## Weaknesses

- Pages are too thick, especially `UploadPage`, `AnalysisPipelinePage`, `ArchitecturePage`, and `EngineeringReviewPage`.
- Upload/import and analysis are simulated locally instead of using the backend service methods already present.
- Global state mixes domain state, UI state, form state, notifications, upload state, and analysis orchestration.
- `searchOpen` is written by keyboard shortcuts but not read by UI, so Ctrl+K does not currently open or focus a search experience.
- Several product areas are shell states awaiting backend integration: AI Workspace, Documentation, Insights, Dependency Graph, and Settings.
- Backend failures in `backendService` often fall back to generated data or `null`, which can hide real integration issues.
- There is no test framework or CI configuration.

## Technical Debt

- Mock repository, architecture, review, and code-preview data are central to the current user journey.
- State updates for analysis are time-based and randomized in the client.
- Shared UI patterns repeat across pages: status variants, completed-repository guards, empty-state wrappers, and card shells.
- Architecture generator still includes aspirational nodes such as auth middleware, event queue, and cache layer that do not exist in the repo.
- Navigation metadata is duplicated between sidebar and routes instead of being one typed source of truth.

## Mock Data Generator Report

| File | Purpose | Replacement Strategy |
| --- | --- | --- |
| `src/services/repoGenerator.ts` | Generates a synthetic repository tree and metadata after analysis completes. | Replace with backend parser output: repository metadata, file tree, language/framework detection, config discovery. |
| `src/services/architectureGenerator.ts` | Generates a synthetic architecture graph, layers, modules, and request flow. | Replace with backend architecture analysis response. Keep only mapping/adaptation code in frontend. |
| `src/services/reviewGenerator.ts` | Generates engineering review findings from limited file-tree metadata. | Replace with backend review engine output. Frontend should render typed review DTOs only. |
| `src/features/explorer/fileUtils.ts` | Infers imports, exports, dependencies, related modules, and sample code for file preview. | Replace generated sample code with actual file content from backend. Keep pure display helpers only. |
| `src/pages/AnalysisPipelinePage.tsx` | Simulates analysis progress with timers and random delays. | Replace with polling/subscription to backend analysis status. Move orchestration into a hook. |
| `src/services/backend.ts` | Falls back to generators when backend calls are absent or fail. | Make fallback behavior explicit behind a development/demo flag; do not silently mask production failures. |

## Unused And Duplicate Code

- Removed unused files and dependencies listed above.
- Remaining duplicate patterns should be extracted cautiously after backend contracts stabilize:
  - Repository-empty guard components.
  - Status badge variant maps.
  - Repeated card/input/button class strings.
  - Page-level repository selection checks.

## Dependency Issues

- `npm audit` now reports zero vulnerabilities.
- Heavy dependencies still justified by current UI: Monaco, React Flow, Framer Motion, and html-to-image.
- Major package upgrades remain available but were not forced because they require migration review: React 19, React Router 7, Tailwind 4, Framer Motion 12, Zustand 5, TypeScript 6.
- `@monaco-editor/react` currently depends on Monaco's exact DOMPurify version, so `package.json` uses an npm override for `dompurify@3.4.11`.

## Performance Issues

- Before lazy routing, Vite produced one `index` chunk around 913 kB minified.
- After lazy routing, the initial app chunk is about 369 kB minified; architecture is split into its own about 266 kB chunk.
- Remaining performance work:
  - Lazy-load Monaco even deeper at code-preview interaction time if needed.
  - Consider route prefetching for common flows.
  - Avoid loading graph/export tooling until architecture routes need it.
  - Run bundle visualization before adding AI/backend SDKs.

## Type Safety Issues

- `any` usage was removed from source.
- `unknown` remains intentionally in API/error boundaries where response shape is not guaranteed.
- Missing runtime validation remains a gap: backend responses are typed but not validated.
- API DTOs and domain models are close but should be separated more clearly as backend contracts mature.

## Security Concerns

- Removed unused `.env` values from the project root and replaced them with `.env.example`.
- Dependency audit is clean.
- Backend errors are currently swallowed in multiple service methods; production should surface structured errors.
- No auth/session implementation exists despite some UI/account placeholders and generated architecture labels.
- Export/download helpers create client-side blobs; keep this path restricted to trusted app-generated content.

## Routing Audit

- Routes are centralized in `src/routes/router.tsx`.
- All sidebar navigation routes resolve to pages.
- Route-level lazy loading is now implemented.
- No explicit 404/error route exists yet.
- Several routes are product placeholders rather than complete feature implementations.

## State Management Audit

- `useAppStore` is too broad and should be split into UI state, repository state, and analysis state.
- Upload file and GitHub URL state can move local to `UploadPage` or a dedicated upload hook.
- `searchOpen` is unused and should be removed or wired to an actual command/search interaction.
- Feature stores for architecture, explorer, and review are reasonable but should avoid storing server state once backend data is live.

## Services Audit

- API direction is mostly correct: `backendService` -> domain API services -> `api/client`.
- Pages call `backendService` directly. Introduce feature hooks to own loading/error/cancellation behavior.
- API methods are present for repository upload/import/status/review/architecture/dependencies/AI/docs, but not all are wired into user flows.

## Suggested Folder Structure

```text
src/
  app/
  routes/
  components/
    shared/
    layout/
  features/
    repositories/
      components/
      hooks/
      services/
      store.ts
      types.ts
    analysis/
      hooks/
      services/
      types.ts
    architecture/
      components/
      hooks/
      services/
      store.ts
      types.ts
    review/
      components/
      hooks/
      services/
      store.ts
      types.ts
  services/
    api/
  styles/
  utils/
```

## Refactoring Recommendations

1. Create `useRepositoryImport`, `useAnalysisStatus`, `useArchitectureModel`, and `useEngineeringReview` hooks.
2. Move upload validation and repository creation out of `UploadPage`.
3. Replace client analysis simulation with backend status polling.
4. Make mock fallback opt-in via a development flag.
5. Split `useAppStore` into smaller stores or localize page-only state.
6. Add test tooling and cover services, stores, and critical page flows.
7. Add a route error boundary and 404 route.
8. Centralize navigation metadata and status variant maps.

## Priority List

- P0: Keep lint, TypeScript, build, and audit green in CI.
- P0: Make mock fallback explicit so production cannot silently render generated data.
- P1: Move page business logic into hooks and services.
- P1: Connect upload/import/analysis to backend status APIs.
- P1: Add a minimal test suite.
- P2: Split global state and centralize repeated UI/domain constants.
- P2: Add bundle analysis and deeper lazy loading for Monaco/graph tooling.

## Risk Assessment

Current engineering risk: Medium.

The project now has clean tooling gates and a smaller dependency surface. The main remaining risk is product correctness: most intelligence outputs are generated locally rather than derived from real repositories or backend analysis. The second risk is maintainability: pages and global state currently own too much orchestration.

## Estimated Remaining Refactoring Effort

- Tooling and dependency cleanup: completed.
- Page-to-hook refactor: 2-4 days.
- Store split and state cleanup: 1-3 days.
- Backend integration replacement for mocks: 1-2 weeks depending on API readiness.
- Test suite and CI baseline: 2-4 days.
- Full production hardening after backend integration: 1-2 additional weeks.

## Verification

Commands run successfully:

```bash
npm run lint
npx tsc --noEmit
npm run build
npm audit --json
```

Final audit result: zero known npm vulnerabilities.
