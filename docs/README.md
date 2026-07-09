# PARTHA Documentation

This directory contains durable product, architecture, operations, audit, and brand documentation for PARTHA.

Start with the root `README.md` for public orientation. Use this index when you need deeper implementation or maintainer context.

## Documentation Map

| Area | Document | Purpose |
| --- | --- | --- |
| Product | `product/PUBLIC_FACE_AUDIT.md` | Public positioning, documentation audit, and roadmap for the public-face redesign. |
| Brand | `brand/VISUAL_IDENTITY.md` | Logo, colors, typography, diagram style, and visual language. |
| Architecture | `architecture/REPOSITORY_INTELLIGENCE_ENGINE.md` | Repository Intelligence Engine boundaries, lifecycle, outputs, and consumers. |
| Architecture | `architecture/AI_ARCHITECTURE.md` | AI workspace architecture, provider abstraction, prompt/context flow, and non-goals. |
| Operations | `operations/production-deployment.md` | Production deployment baseline, environment, health checks, rollback, and operational limits. |
| Operations | `operations/release-management.md` | Versioning, release validation workflow, and hotfix flow. |
| Operations | `operations/dependency-management.md` | Frontend/backend dependency maintenance and security update process. |
| Operations | `operations/observability.md` | Request IDs, structured logs, redaction, metrics, and readiness checks. |
| Audit | `audit/CORE_1_INGESTION_PIPELINE_AUDIT.md` | Ingestion stabilization audit evidence. |
| Audit | `audit/CORE_2_REPOSITORY_INTELLIGENCE_AUDIT.md` | Repository Intelligence audit and refactor summary. |

## Recommended Reading Paths

### New Contributor

1. `../README.md`
2. `../CONTRIBUTING.md`
3. `architecture/REPOSITORY_INTELLIGENCE_ENGINE.md`
4. `../apps/backend/README.md` or `../apps/frontend/README.md`

### Backend Contributor

1. `architecture/REPOSITORY_INTELLIGENCE_ENGINE.md`
2. `architecture/AI_ARCHITECTURE.md`
3. `operations/observability.md`
4. `operations/dependency-management.md`

### Maintainer / Release Reviewer

1. `operations/release-management.md`
2. `operations/production-deployment.md`
3. `operations/observability.md`
4. `product/PUBLIC_FACE_AUDIT.md`

### Public Documentation / Brand Work

1. `product/PUBLIC_FACE_AUDIT.md`
2. `brand/VISUAL_IDENTITY.md`
3. `../README.md`

## Documentation Rules

- Keep the root README product-oriented and implementation-honest.
- Keep durable architecture detail under `docs/architecture/`.
- Keep operational procedures under `docs/operations/`.
- Keep audit evidence under `docs/audit/`.
- Do not add empty placeholder docs.
- If a feature is not implemented, describe it as roadmap or planned work.
