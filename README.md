# PARTHA

AI-powered repository intelligence for understanding large codebases in minutes instead of days.

PARTHA analyzes a repository once, builds a reusable intelligence layer from the codebase, and uses that same source of truth to power architecture visualization, dependency analysis, documentation generation, engineering reviews, AI-assisted exploration, and repository search.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](#license)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

> Hero image placeholder: add a product screenshot or architecture graph preview here when the public demo UI is ready.

---

## Why PARTHA?

Large repositories are hard to understand because the important information is distributed across files, folders, configuration, conventions, dependency manifests, framework entrypoints, and team-specific patterns.

Engineers often spend hours answering the same first-order questions:

- Where does the application start?
- What are the major architectural boundaries?
- Which modules depend on each other?
- Which routes, APIs, services, and configuration files matter?
- What dependencies are present, and why are they installed?
- What documentation exists, and what has to be inferred?
- What should be reviewed before making a safe change?
- Which files should a new contributor read first?

Existing tools solve pieces of this problem. Some draw diagrams. Some generate documentation. Some provide AI chat over files. Some scan dependencies. Those are useful, but they often parse the same repository repeatedly and produce disconnected answers.

PARTHA takes a different approach: build repository intelligence once, then let every feature consume it.

---

## Core Philosophy

PARTHA is not just an AI chat interface.

PARTHA is not just architecture diagrams.

PARTHA is not just documentation generation.

The product is built around a repository intelligence pipeline:

```mermaid
flowchart TD
    A[Repository] --> B[Repository Intelligence Engine]
    B --> C[Knowledge Graph]
    C --> D[Architecture Graph]
    C --> E[Dependency Analysis]
    C --> F[Documentation]
    C --> G[Engineering Review]
    C --> H[AI Workspace]
    C --> I[Search and Insights]
```

This matters because codebase understanding should be consistent across the product. If architecture diagrams, documentation, reviews, and AI answers each rely on different parsing logic, they drift. PARTHA is designed to prevent that drift by centralizing repository understanding.

The core engineering principles are:

| Principle | What it means |
| --- | --- |
| Single source of truth | Repository facts should be derived once and reused everywhere. |
| No duplicated parsing | Features should not each re-scan the repository from scratch. |
| Consistent analysis | Architecture, dependencies, documentation, and AI should agree on the same repository model. |
| Reusable intelligence | Parsed structure should be persisted and used by future workflows. |
| Agent-ready foundation | Future AI agents should operate on repository intelligence, not raw file guessing. |

The current implementation includes repository import, parsing, metadata extraction, architecture modeling, dependency inventory, engineering review, documentation generation, and AI provider integration. Some deeper knowledge graph capabilities are still in progress and are tracked in `docs/audit/`.

---

## Repository Intelligence Engine

The Repository Intelligence Engine is the center of PARTHA.

Its job is to turn a repository into a structured, reusable representation that the rest of the product can trust.

The intended pipeline looks like this:

```mermaid
flowchart TD
    A[Import Repository] --> B[Clone or Upload]
    B --> C[Repository Parsing]
    C --> D[AST Extraction]
    D --> E[Dependency Analysis]
    E --> F[Framework Detection]
    F --> G[Configuration Detection]
    G --> H[API Discovery]
    H --> I[Symbol Extraction]
    I --> J[Relationship Graph]
    J --> K[Knowledge Graph]
    K --> L[Persist]
    L --> M[Product Features]
```

### Current Pipeline

Today, PARTHA performs the following steps:

| Stage | Current behavior | Status |
| --- | --- | --- |
| Repository import | Upload local archives or import public GitHub repositories. | Implemented |
| Archive extraction | Safely extracts ZIP/TAR archives with path traversal checks. | Implemented |
| Repository parsing | Builds a file tree and repository metadata. | Implemented |
| Framework detection | Detects basic framework signals from files and manifests. | Implemented |
| Configuration detection | Identifies common config and environment files. | Implemented |
| Dependency analysis | Reads dependency manifests such as `package.json`, `requirements.txt`, and `pyproject.toml`. | Partial |
| Architecture modeling | Builds a heuristic architecture model for graph visualization. | Partial |
| Engineering review | Generates heuristic review findings from repository structure and metadata. | Partial |
| Documentation generation | Generates Markdown or HTML documentation from repository facts. | Partial |
| AI context | Provides repository-aware context to configured AI providers. | Partial |
| Persisted knowledge graph | Planned deeper graph model with richer relationships and artifacts. | In progress |

### Why This Architecture Scales

The repository intelligence layer creates a stable boundary between ingestion and product features.

Without that boundary, every feature has to understand raw repositories independently. That creates duplicated logic, inconsistent outputs, and expensive repeated work.

With a shared intelligence layer:

- architecture views can read module and relationship data;
- documentation can describe the same structure shown in the graph;
- engineering review can cite the same files shown in the explorer;
- AI can answer from structured repository context instead of guessing from raw paths;
- future agents can plan work against a graph of repository facts.

The engine is intentionally provider-neutral. AI providers are consumers of repository intelligence, not the source of repository intelligence.

---

## Features

| Feature | Purpose | Status | Description |
| --- | --- | --- | --- |
| Repository Import | Bring repositories into PARTHA. | Implemented | Upload ZIP/TAR archives or import public GitHub repositories. |
| Repository Explorer | Browse repository structure. | Implemented | View parsed file trees, metadata, and file-level details. Source preview currently uses generated previews rather than full file-content retrieval. |
| Architecture Graph | Understand system structure. | Partial | Interactive graph UI with layers, modules, search, heatmaps, request-flow views, inspector panels, and exports. Backend analysis is currently heuristic. |
| Dependency Graph | Understand package dependencies. | Partial | Reads dependency manifests and shows dependency inventory. Relationship edges, vulnerability scanning, and outdated checks are planned. |
| Engineering Review | Surface technical risks and improvement opportunities. | Partial | Generates review findings, scores, and roadmap suggestions from repository structure. Rule depth and evidence fidelity are being expanded. |
| Documentation Generator | Generate repository documentation. | Partial | Produces Markdown or HTML documentation from parsed repository facts. HTML rendering and artifact export are currently basic. |
| AI Workspace | Ask repository-aware questions. | Partial | Supports configurable providers and repository context. Current context is metadata/file-tree based; richer retrieval is planned. |
| Repository Search | Find repositories and files quickly. | Partial | Global search covers loaded repository names and file paths. Deep-linking directly into selected files is planned. |
| Insights Dashboard | Show higher-level repository insights. | Planned | Navigation exists, but the insights workflow is intentionally disabled until the backend endpoint exists. |
| Settings | Configure local PARTHA behavior. | Partial | AI provider settings are wired. Account, theme, notifications, and API-key settings are placeholders until auth and user settings exist. |

---

## System Architecture

```mermaid
flowchart TD
    A[Frontend<br/>React + Vite] --> B[REST API<br/>FastAPI]
    B --> C[Repository Intelligence Engine]
    C --> D[Knowledge Graph<br/>Current: repository metadata + file tree<br/>Target: persisted graph artifacts]
    D --> E[(Database<br/>SQLite local / PostgreSQL Docker)]
    C --> F[Local Storage<br/>Repositories + uploads]
    B --> G[AI Providers<br/>OpenAI / Anthropic / Gemini / OpenRouter / Ollama]
    B --> H[Exports<br/>Markdown / JSON today<br/>Richer artifacts planned]
```

### Layer Responsibilities

| Layer | Responsibility |
| --- | --- |
| Frontend | Product UI, navigation, repository explorer, graph visualization, review views, documentation workspace, AI workspace, and settings. |
| REST API | Stable interface between the UI and backend services. Exposes repository, analysis, documentation, export, health, and AI routes. |
| Repository Intelligence Engine | Imports repositories, parses structure, detects metadata, builds analysis models, and prepares feature-ready repository intelligence. |
| Knowledge Graph | The product direction for persisted repository relationships. The current implementation stores repository metadata and file trees, with deeper graph persistence planned. |
| Database | Stores repository records, metadata, file tree JSON, status, and analysis state. SQLite is used for local development; Docker Compose uses PostgreSQL. |
| Local Storage | Stores cloned or uploaded repositories and generated local artifacts. |
| AI Providers | Optional external or local model providers that consume repository intelligence. Providers do not parse repositories directly. |
| Exports | Provides downloadable product artifacts. Current export support is basic; production-grade artifact generation is on the roadmap. |

---

## Repository Structure

PARTHA is organized as a monorepo.

```text
partha/
├── apps/
│   ├── frontend/
│   └── backend/
├── docs/
│   └── audit/
├── packages/
├── scripts/
├── docker-compose.yml
├── package.json
└── README.md
```

| Path | Description |
| --- | --- |
| `apps/` | Product applications. |
| `apps/frontend/` | Vite, React, TypeScript frontend. Contains routes, feature modules, shared UI, API clients, and styles. |
| `apps/frontend/src/app/` | App shell, router, route pages, global store, and entrypoint. |
| `apps/frontend/src/features/` | Feature-specific hooks, components, and state. |
| `apps/frontend/src/shared/` | Shared components, API clients, hooks, services, types, and utilities. |
| `apps/frontend/src/assets/` | Static frontend assets. |
| `apps/frontend/src/styles/` | Global CSS and design tokens. |
| `apps/backend/` | FastAPI backend for repository ingestion, parsing, analysis, AI, documentation, and persistence. |
| `apps/backend/app/api/` | FastAPI routers and dependency wiring. |
| `apps/backend/app/services/` | Application services for repositories, analysis, documentation, and AI. |
| `apps/backend/app/repositories/` | Database access layer. |
| `apps/backend/app/models/` | SQLAlchemy models. |
| `apps/backend/app/schemas/` | Pydantic request/response schemas. |
| `apps/backend/app/parsers/` | Repository parsing and parser-related utilities. |
| `apps/backend/app/analysis/` | Architecture analysis logic. |
| `apps/backend/app/graph/` | Dependency graph construction. |
| `apps/backend/app/review/` | Engineering review generation. |
| `apps/backend/app/storage/` | Local filesystem storage for uploads and repositories. |
| `apps/backend/alembic/` | Database migration environment and versions. |
| `apps/backend/tests/` | Backend tests. |
| `docs/` | Project documentation. |
| `docs/audit/` | Engineering, security, frontend, backend, and feature-matrix audit documents. |
| `packages/` | Reserved for shared packages as the monorepo grows. |
| `scripts/` | Local helper scripts for backend checks and startup. |
| `.github/` | CI workflow, issue templates, and pull request template. |
| `docker-compose.yml` | Local API, PostgreSQL, and Redis stack. |
| `package.json` | Root workspace scripts. |

---

## Tech Stack

### Frontend

| Technology | Role |
| --- | --- |
| React | Component model and application UI. |
| TypeScript | Static typing for frontend code. |
| Vite | Development server and production build. |
| React Router | Client-side routing and lazy-loaded pages. |
| Tailwind CSS | Styling system. |
| React Flow | Interactive architecture graph visualization. |
| Monaco Editor | Code preview/editor surface. |
| Zustand | Local application state. |
| Framer Motion | UI transitions. |
| Lucide React | Icons. |

### Backend

| Technology | Role |
| --- | --- |
| FastAPI | HTTP API framework. |
| Pydantic v2 | Settings, validation, and API schemas. |
| SQLAlchemy | Database models and persistence. |
| Alembic | Database migrations. |
| GitPython | Public GitHub repository clone support. |
| NetworkX | Graph construction utilities. |
| tree-sitter | Parser foundation for deeper AST-based analysis. |
| httpx | Outbound AI provider requests. |
| pytest | Backend test runner. |

### Database

| Technology | Role |
| --- | --- |
| SQLite | Default local development database. |
| PostgreSQL | Docker Compose database and intended production relational database. |
| Redis | Docker Compose service reserved for async/job-oriented workflows. |

### AI

| Provider | Status | Notes |
| --- | --- | --- |
| OpenAI | Supported | Uses chat completions-compatible request path. |
| Anthropic | Supported | Uses Messages API. |
| Google Gemini | Supported | Uses Gemini generate content endpoint. |
| OpenRouter | Supported | Uses OpenRouter chat completions endpoint. |
| Ollama | Supported | Uses local Ollama chat endpoint. |

### Infrastructure

| Tool | Role |
| --- | --- |
| Docker | Containerized backend and service dependencies. |
| Docker Compose | Local API, PostgreSQL, and Redis orchestration. |
| Uvicorn | ASGI server for FastAPI. |

### Developer Tooling

| Tool | Role |
| --- | --- |
| npm workspaces | Frontend workspace orchestration from the root. |
| ESLint | Frontend linting. |
| TypeScript compiler | Frontend type checking. |
| pip editable installs | Backend local development. |
| Alembic CLI | Database migrations. |

### Testing

| Area | Tooling | Current coverage |
| --- | --- | --- |
| Frontend | ESLint and TypeScript build | Build/lint coverage exists; unit and e2e tests are planned. |
| Backend | pytest and FastAPI TestClient | Health, OpenAPI, repository validation, and parser tests exist. More integration coverage is planned. |
| Docker | `docker compose config` | Configuration validation is included in CI. Full runtime validation depends on Docker availability. |

### CI/CD

| Workflow | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Runs frontend install/lint/build, backend install/tests, and Docker Compose config validation. |

---

## Getting Started

### Prerequisites

Install the following locally:

| Tool | Version |
| --- | --- |
| Node.js | 22 or newer recommended. |
| npm | Bundled with Node.js. |
| Python | 3.12 or 3.13. |
| Docker | Required for Compose-based PostgreSQL/Redis workflow. |
| Git | Required for GitHub repository import. |

### Clone

```bash
git clone <your-partha-repository-url>
cd project
```

### Install Frontend Dependencies

```bash
npm ci --prefix apps/frontend
```

If this is a fresh checkout and no lockfile is available for your environment, use:

```bash
npm install --prefix apps/frontend
```

### Install Backend Dependencies

```bash
cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..
```

Python 3.12 also works with the backend project constraints.

### Configure Environment

Create local environment files from examples:

```bash
cp .env.example .env
cp apps/frontend/.env.example apps/frontend/.env
cp apps/backend/.env.example apps/backend/.env
```

For local frontend-to-backend development, the frontend should point to the backend API:

```bash
VITE_API_URL=http://localhost:8000
```

### Run the Frontend

```bash
npm run dev:frontend
```

The frontend starts at:

```text
http://localhost:5173
```

### Run the Backend

```bash
npm run dev:backend
```

The backend starts at:

```text
http://localhost:8000
```

Swagger UI is available at:

```text
http://localhost:8000/docs
```

### Run with Docker Compose

```bash
docker compose up --build
```

The Compose stack starts:

| Service | Port |
| --- | --- |
| API | `8000` |
| PostgreSQL | `5432` |
| Redis | `6379` |

The current Compose file runs backend infrastructure. Run the frontend separately with `npm run dev:frontend` for full local product usage.

---

## Environment Variables

PARTHA uses environment variables at both the root/dev level and app level.

### Frontend

| Variable | Required | Default/example | Description |
| --- | --- | --- | --- |
| `VITE_API_URL` | Yes | `http://localhost:8000` | Base URL for the FastAPI backend. Used by the frontend API client. |

### Backend

| Variable | Required | Default/example | Description |
| --- | --- | --- | --- |
| `APP_NAME` | No | `PARTHA Backend` | Display name for the backend service. |
| `APP_ENV` | No | `development` | Runtime environment label returned by health checks and used for operational context. |
| `LOG_LEVEL` | No | `INFO` | Backend logging level. |
| `DATABASE_URL` | Yes | `sqlite:///./.local/partha.db` | SQLAlchemy database URL. Local development can use SQLite. Docker Compose uses PostgreSQL. |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL reserved for async/job workflows. |
| `STORAGE_PATH` | Yes | `./.local/storage` | Filesystem path for uploaded archives, cloned repositories, and local backend artifacts. |
| `CORS_ORIGINS` | Yes | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed browser origins. |
| `AUTO_CREATE_TABLES` | No | `true` | Automatically creates database tables on startup. Useful for local development; migrations should be used for controlled environments. |
| `CLONE_TIMEOUT_SECONDS` | No | `120` | Intended timeout for clone operations. The current GitPython clone path does not fully enforce this yet. |
| `MAX_UPLOAD_SIZE_BYTES` | No | `104857600` | Maximum upload size in bytes. Default is 100 MB. |

### Docker Compose Environment

The Compose API service sets:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `development` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | `postgresql+psycopg://partha:partha@postgres:5432/partha` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `STORAGE_PATH` | `/data/partha` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `AUTO_CREATE_TABLES` | `true` |

---

## Development Workflow

### Run Frontend Development Server

```bash
npm run dev:frontend
```

### Run Backend Development Server

```bash
npm run dev:backend
```

### Build Frontend

```bash
npm run build:frontend
```

### Preview Frontend Build

```bash
npm run preview:frontend
```

### Lint Frontend

```bash
npm run lint:frontend
```

### Run Backend Tests

```bash
npm run test:backend
```

### Run Full Root Build Check

```bash
npm run build
```

This runs the frontend production build and backend tests.

### Validate Docker Compose

```bash
npm run docker:config
```

### Run Docker Compose

```bash
npm run docker:up
```

### Run Migrations

From the backend app directory:

```bash
cd apps/backend
source .venv/bin/activate
alembic upgrade head
```

To create a new migration after model changes:

```bash
cd apps/backend
source .venv/bin/activate
alembic revision --autogenerate -m "describe change"
```

### Common Local Loop

```bash
npm run dev:frontend
npm run dev:backend
npm run lint:frontend
npm run test:backend
npm run build:frontend
```

---

## API Overview

PARTHA exposes a REST API from the FastAPI backend.

This is a high-level overview. Use `/docs` locally for the interactive OpenAPI explorer.

| Area | Endpoints | Purpose |
| --- | --- | --- |
| Health | `GET /health` | Check service status and environment. |
| Repositories | `GET /repositories`, `GET /repositories/{id}`, `DELETE /repositories/{id}` | List, fetch, and delete imported repositories. |
| Repository Import | `POST /repositories/upload`, `POST /repositories/github` | Upload repository archives or import public GitHub repositories. |
| Analysis | `POST /analysis/{id}/start`, `GET /analysis/{id}/status` | Start and inspect repository analysis state. Current analysis completes synchronously. |
| Architecture | `GET /analysis/{id}/architecture` | Return architecture model used by the graph UI. |
| Dependencies | `GET /analysis/{id}/dependencies` | Return dependency inventory and graph response shape. |
| Engineering Review | `GET /analysis/{id}/review` | Return engineering review scores, findings, and roadmap. |
| Documentation | `POST /documentation/generate` | Generate Markdown or HTML documentation from repository facts. |
| Exports | `POST /export` | Export artifacts. Current implementation is basic and should be treated as a roadmap surface. |
| AI | `GET /ai/config`, `PUT /ai/config`, `POST /ai/test`, `POST /ai/query`, `POST /ai/stream` | Configure providers and ask repository-aware questions. |
| Settings | AI settings are API-backed through `/ai/config`; account/theme/API-key settings are not implemented yet. | Configure AI provider behavior. |

---

## Repository Intelligence Pipeline

The pipeline is the engineering boundary that keeps PARTHA coherent.

### 1. Discovery

PARTHA starts by acquiring a repository through one of two paths:

| Source | Mechanism |
| --- | --- |
| Upload | User uploads a ZIP/TAR archive. |
| GitHub | User provides a public GitHub HTTPS URL. |

The backend stores the repository under local storage and creates a repository record.

### 2. Parsing

The parser walks the repository and builds:

- a file tree;
- repository metadata;
- language signals;
- framework signals;
- package manager signals;
- entrypoint hints;
- README/config file detection.

This parsed representation becomes the first reusable layer of repository intelligence.

### 3. Analysis

Analysis services use the parsed repository to produce feature-specific models:

| Analyzer | Output |
| --- | --- |
| Architecture analyzer | Nodes, edges, modules, layers, request-flow summary, and architecture summary. |
| Dependency graph builder | Dependency nodes and graph response. |
| Engineering review builder | Scores, findings, summaries, and improvement roadmap. |
| Documentation service | Markdown or HTML documentation sections. |

The current analyzers are intentionally lightweight and heuristic. The roadmap moves these toward AST-backed, relationship-aware, persisted analysis artifacts.

### 4. Knowledge Graph

The target architecture is a persisted knowledge graph that models repository facts and relationships:

- files;
- modules;
- symbols;
- imports;
- exports;
- routes;
- services;
- configuration;
- dependencies;
- ownership signals;
- architectural boundaries.

This graph becomes the durable substrate for user-facing features and future AI agents.

### 5. Persistence

Current persistence stores repository records, status, metadata, and file tree JSON in the database. Repository files are stored on disk under the configured storage path.

Planned persistence improvements include:

- analysis job records;
- persisted architecture artifacts;
- persisted dependency graph artifacts;
- richer symbol and relationship tables;
- repository content indexing;
- retention and cleanup policies.

### 6. Consumers

Every product feature should consume repository intelligence rather than re-parse raw code independently.

| Consumer | Uses repository intelligence for |
| --- | --- |
| Architecture Graph | Modules, layers, relationships, and request flow. |
| Dependency Graph | Package inventory and dependency relationships. |
| Documentation | Overview, folder structure, API hints, environment, deployment, and contribution guidance. |
| Engineering Review | Findings, scores, and improvement roadmap. |
| AI Workspace | Repository-aware context, citations, and future graph-grounded answers. |
| Search | Repository and file discovery. |
| Insights | Higher-level trends and recommendations. |

---

## AI Architecture

AI is not the parser in PARTHA.

AI is a consumer of repository intelligence.

That distinction is important. If AI is responsible for directly reading and interpreting raw repositories every time a user asks a question, answers become expensive, inconsistent, and difficult to ground. PARTHA instead builds a repository intelligence layer first, then passes structured context to AI providers.

```mermaid
flowchart TD
    A[Repository] --> B[Repository Intelligence Engine]
    B --> C[Repository Context]
    C --> D[Provider Abstraction]
    D --> E[OpenAI]
    D --> F[Anthropic]
    D --> G[Gemini]
    D --> H[OpenRouter]
    D --> I[Ollama]
    E --> J[AI Workspace]
    F --> J
    G --> J
    H --> J
    I --> J
```

### Provider Abstraction

PARTHA supports multiple providers so teams can choose the model/runtime that fits their environment.

| Provider | Use case |
| --- | --- |
| OpenAI | Hosted frontier and efficient general-purpose models. |
| Anthropic | Hosted models with strong long-context and reasoning workflows. |
| Gemini | Google-hosted model workflows. |
| OpenRouter | Model routing across multiple hosted providers. |
| Ollama | Local model experimentation and offline-friendly development. |

### Current AI Behavior

The current AI implementation:

- stores provider configuration through the backend;
- does not return saved API keys from the public config endpoint;
- builds context from repository metadata and file tree information;
- sends the prompt to the selected provider;
- returns assistant text, suggestions, and basic citations;
- exposes a streaming endpoint that currently emits chunks after the provider response is complete.

### Planned AI Improvements

The AI roadmap includes:

- provider-native streaming;
- stronger SSE parsing and cancellation;
- graph-grounded retrieval;
- richer citations;
- token budgeting;
- local-only provider modes;
- agent workflows over repository intelligence;
- safer secret storage and authorization boundaries.

---

## Roadmap

PARTHA is evolving toward a SaaS platform. The roadmap is organized around the maturity of the repository intelligence layer.

| Phase | Theme | Scope | Status |
| --- | --- | --- | --- |
| Phase 1 | Repository Intelligence | Repository import, parsing, metadata extraction, file tree, architecture model, dependency inventory, review, docs, AI workspace. | In progress |
| Phase 2 | Knowledge Graph | Persisted graph model, symbols, imports, exports, routes, APIs, module relationships, artifact snapshots, job lifecycle. | Planned |
| Phase 3 | AI Engineering Assistant | Graph-grounded AI, provider-native streaming, codebase Q&A with citations, guided onboarding, review assistant, future agent workflows. | Planned |
| Phase 4 | Hosted SaaS | Authentication, teams, projects, repository sync, background workers, billing-ready deployment model, audit logs, retention policies. | Planned |

### Near-Term Engineering Priorities

The current audit backlog identifies the most important work before production exposure:

| Priority | Work |
| --- | --- |
| P0 | Authentication and authorization for repository, deletion, AI, export, and settings routes. |
| P0 | Remove tracked local environment files and generated build artifacts. |
| P1 | Real analysis job lifecycle with processing state, cancellation, retries, and persisted artifacts. |
| P1 | Harden AI secret handling and provider streaming. |
| P1 | Enforce GitHub clone timeout and repository size controls. |
| P2 | Improve dependency graph edges, documentation rendering, file-content preview, and frontend error states. |
| P3 | Add frontend unit/component/e2e coverage and broaden backend integration tests. |

---

## Documentation

Project documentation lives in `docs/`.

| Document | Purpose |
| --- | --- |
| `docs/README.md` | Documentation index. |
| `docs/audit/SYSTEM_AUDIT.md` | End-to-end engineering audit and verification evidence. |
| `docs/audit/FEATURE_MATRIX.md` | Feature-by-feature backlog matrix. |
| `docs/audit/FRONTEND_AUDIT.md` | Frontend route, hook, API-client, and UI-control audit. |
| `docs/audit/BACKEND_AUDIT.md` | Backend endpoint, service, integration, persistence, and test audit. |
| `docs/audit/SECURITY_AUDIT.md` | Security posture, risks, and prioritized remediation plan. |

Planned documentation areas:

| Area | Purpose |
| --- | --- |
| Architecture docs | Explain the repository intelligence model, graph schema, and service boundaries. |
| Contributor docs | Describe local setup, coding standards, and pull request expectations. |
| RFCs | Track major design proposals before implementation. |
| Deployment docs | Document production deployment, environment, secrets, workers, and observability. |
| API docs | Provide stable examples for common API workflows without replacing OpenAPI. |

---

## Contributing

PARTHA is being built as a serious developer platform. Contributions should preserve technical accuracy, product trust, and a clean engineering boundary between repository intelligence and feature consumers.

### Issue Workflow

Use GitHub issues for all non-trivial work.

| Issue type | Use for |
| --- | --- |
| Bug Report | Broken behavior, regressions, incorrect output, or failed workflows. |
| Feature Request | New user-facing capabilities or major enhancements. |
| Engineering Task | Refactors, tests, infrastructure, technical debt, audits, and security work. |

Good issues include:

- expected behavior;
- actual behavior;
- reproduction steps;
- severity;
- affected page, endpoint, service, or workflow;
- acceptance criteria;
- links to audit rows when relevant.

### Branch Naming

Use descriptive branch names:

| Prefix | Example |
| --- | --- |
| `feat/` | `feat/analysis-job-lifecycle` |
| `fix/` | `fix/upload-error-state` |
| `chore/` | `chore/remove-tracked-dist` |
| `docs/` | `docs/api-overview` |
| `test/` | `test/repository-upload-flow` |
| `security/` | `security/auth-route-guards` |

### Commit Convention

Use concise conventional-style commits:

```text
feat: add dependency graph edges
fix: surface repository fetch failures
docs: document environment variables
test: cover upload archive validation
security: require auth for repository deletion
```

### Pull Requests

Pull requests should include:

- a clear summary;
- linked issue or audit item;
- screenshots or recordings for UI changes;
- API examples for endpoint changes;
- migration notes for data model changes;
- verification commands and results;
- risk and rollback notes.

### Code Review Expectations

Reviewers should check:

| Area | What to verify |
| --- | --- |
| Correctness | The change satisfies the issue and does not introduce behavior drift. |
| Product honesty | UI labels and docs match actual implementation. |
| Architecture | New logic belongs in the right layer and does not duplicate repository parsing. |
| Security | Secrets, auth, filesystem access, provider calls, and destructive actions are handled safely. |
| Tests | Relevant unit, integration, or e2e coverage is added or updated. |
| Operations | Env vars, migrations, Docker, and CI behavior are documented. |

### Testing Requirements

Before opening a PR, run the relevant checks:

```bash
npm run lint:frontend
npm run build:frontend
npm run test:backend
npm run docker:config
```

For backend changes that touch persistence, also run migrations locally:

```bash
cd apps/backend
source .venv/bin/activate
alembic upgrade head
```

For UI changes, manually verify the affected route and include notes in the PR.

---

## Project Status

PARTHA is under active development.

It is suitable for local development and product iteration. It should not be exposed as a production multi-user service until the security backlog is addressed, especially authentication, authorization, secret handling, repository retention, and source-control hygiene.

The most accurate current-state documents are the audit files in `docs/audit/`.

---

## License

MIT
