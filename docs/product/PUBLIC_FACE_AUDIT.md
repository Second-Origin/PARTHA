# PARTHA Public Face Audit

This audit captures the reasoning behind the README, documentation, and visual identity redesign. It is intentionally grounded in the current implementation and avoids claiming future functionality as shipped.

## 1. Repository Audit

### Current Product Surface

PARTHA currently provides:

- repository import from ZIP/TAR archives and public GitHub URLs;
- repository file tree, metadata, and real file preview;
- a Repository Intelligence Engine that derives reusable repository facts;
- architecture modelling from repository intelligence;
- dependency inventory and dependency graph response shapes;
- engineering review findings, scores, and roadmap suggestions;
- documentation generation from repository intelligence;
- export pipeline for review, architecture, dependencies, and documentation in JSON, Markdown, HTML, and PDF;
- AI Workspace backed by provider configuration and repository context;
- dedicated provider implementations for OpenAI, Anthropic, Gemini, OpenRouter, and Ollama;
- health, readiness, request IDs, metrics, Docker Compose runtime validation, and release workflow baseline.

### Current Limits

PARTHA does not currently provide:

- authentication, authorization, tenant isolation, or multi-user SaaS controls;
- vulnerability or outdated dependency scanning;
- persisted graph tables beyond serialized repository intelligence;
- deep semantic change-impact analysis;
- full OpenTelemetry tracing;
- frontend unit/e2e test coverage;
- production hardening for public multi-user deployment.

### Product Positioning Problem

The previous README positioned PARTHA as “AI-powered repository intelligence,” which was directionally correct but too close to “AI chatbot over a repo.” The stronger position is:

> PARTHA is an Engineering Intelligence Platform.

That framing makes Repository Intelligence the foundation rather than the final product. The product story becomes:

```text
Repository Intelligence
-> Architecture Intelligence
-> Engineering Intelligence
-> Software Change Intelligence
-> Engineering Decision Intelligence
```

## 2. Open-Source Documentation Benchmark

Mature open-source projects tend to do five things well:

1. **Immediate category clarity** — Supabase and LangGraph state what they are in the first sentence.
2. **Problem-before-feature framing** — Sourcegraph, Greptile, and PostHog explain the engineering pain before listing capabilities.
3. **Fast orientation** — OpenTelemetry and Supabase make installation, docs, and contribution paths easy to find.
4. **Honest boundaries** — strong projects distinguish current capability from roadmap.
5. **Documentation map** — mature repos separate README marketing/orientation from deep architecture, operations, and contribution docs.

PARTHA should adopt those patterns without imitating their voice or claiming maturity it does not yet have.

## 3. Documentation Audit

| File | Recommendation | Why |
| --- | --- | --- |
| `README.md` | Rewrite | Needs public positioning, product narrative, clear current capabilities, quick start, architecture, and roadmap. |
| `CONTRIBUTING.md` | Rewrite | Current guide is useful but should become a complete open-source contributor guide with setup, branch, PR, tests, docs, and review standards. |
| `docs/README.md` | Expand | Should become the documentation index and recommended hierarchy. |
| `docs/architecture/REPOSITORY_INTELLIGENCE_ENGINE.md` | Expand | Good boundary doc; needs richer Mermaid diagrams, data lifecycle, and consumer flow. |
| `docs/architecture/AI_ARCHITECTURE.md` | Expand | Good AI foundation doc; needs provider/context/prompt lifecycle diagrams and clearer non-goals. |
| `docs/operations/production-deployment.md` | Keep / expand later | Useful baseline; should remain operations-specific. |
| `docs/operations/release-management.md` | Keep | Clear release workflow baseline. |
| `docs/operations/dependency-management.md` | Keep | Good dependency policy baseline. |
| `docs/operations/observability.md` | Keep | Good observability baseline. |
| `docs/audit/*` | Keep | Audit evidence should stay separate from public README narrative. |
| `apps/backend/README.md` | Keep / expand later | Useful app-local quick reference. |
| `apps/frontend/README.md` | Expand later | Too thin for frontend contributors but acceptable outside this redesign. |
| `scripts/README.md` | Keep | Small and sufficient. |
| `packages/README.md` | Keep | Correctly states reserved status. |

## 4. Recommended Documentation Hierarchy

```text
docs/
  README.md
  assets/
    partha-hero.svg
    partha-logo.svg
  product/
    PUBLIC_FACE_AUDIT.md
  brand/
    VISUAL_IDENTITY.md
  architecture/
    REPOSITORY_INTELLIGENCE_ENGINE.md
    AI_ARCHITECTURE.md
  operations/
    production-deployment.md
    release-management.md
    dependency-management.md
    observability.md
  audit/
    CORE_1_INGESTION_PIPELINE_AUDIT.md
    CORE_2_REPOSITORY_INTELLIGENCE_AUDIT.md
```

Future additions should be real docs, not empty placeholders:

- `docs/architecture/SYSTEM_ARCHITECTURE.md` after subsystem boundaries stabilize further;
- `docs/development/frontend.md` after frontend testing and contribution patterns mature;
- `docs/decisions/` only when actual architecture decision records are written.

## 5. Branding Recommendations

- Public name: **PARTHA**.
- Category: **Engineering Intelligence Platform**.
- Tagline: **Transform Repositories into Actionable Engineering Intelligence**.
- Supporting sentence: **Understand systems, assess change impact, and make engineering decisions with confidence.**
- Keep the internal acronym expansion out of the hero; place it only in a project identity section.

## 6. Documentation Roadmap

### Current Milestone

- Establish public positioning.
- Clarify implemented capabilities.
- Document Repository Intelligence as the architectural source of truth.
- Provide clear local setup and contribution flow.

### Next Milestones

- Add frontend-specific development guide after tests exist.
- Add architecture decision records for major system boundaries.
- Add API examples once endpoint contracts stabilize further.
- Add screenshots when the public demo UI is ready.
- Add security/auth documentation when public multi-user controls are implemented.

## 7. Maintainer Notes

The README should stay honest about maturity. PARTHA can present a strong long-term Engineering Intelligence vision while clearly saying that current analysis remains heuristic in places and public multi-user SaaS controls are not implemented yet.
