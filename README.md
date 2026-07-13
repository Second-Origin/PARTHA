<p align="center">
  <img src="docs/assets/partha-hero.svg" alt="PARTHA — Repository Intelligence Platform" width="100%">
</p>

<p align="center">
  <a href="#getting-started">Getting started</a>
  ·
  <a href="#what-currently-works">What works</a>
  ·
  <a href="#how-the-system-works">How it works</a>
  ·
  <a href="#limitations">Limitations</a>
  ·
  <a href="docs/README.md">Docs</a>
  ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/github/license/Second-Origin/PARTHA">
  <img alt="Python 3.12-3.13" src="https://img.shields.io/badge/Python-3.12--3.13-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white">
  <img alt="React 18" src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111">
  <img alt="TypeScript 5" src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white">
</p>

---

## What PARTHA is

**A self-hosted Repository Intelligence Platform for private and evolving codebases.**

PARTHA parses a repository once into a shared layer of repository facts, and has every surface — architecture, dependencies, reviews, documentation, exports, and optional AI — read from that one layer rather than deriving its own.

> **Repository Intelligence is the shared repository-understanding layer. AI is an optional downstream consumer of it, never an independent interpreter of the repository.**

The purpose, stated at the level it is actually being pursued: build *persistent* understanding of a repository as it evolves, reuse that understanding across every surface, and make repository claims progressively more checkable. PARTHA is early. What follows describes what exists, not what is intended.

> **Status: early development.** PARTHA runs locally and is useful for exploring a repository. It is **not production-ready**. Multi-user authentication and owner isolation are not consistently enforced across every backend surface — PARTHA should currently be used only in a trusted local environment.

## The problem

- **Architecture is implicit.** Module boundaries, layering, and entry points live in folder conventions and framework idioms, not in anything you can read.
- **Dependencies are scattered** across manifests, imports, config, and container files.
- **Documentation goes stale**, and nobody can tell which parts still hold.
- **AI explanations are hard to trust** when the assistant reads raw files and guesses, giving you no way to check its answer.

The common failure is that each tool re-derives its own private understanding of the repository, and they quietly disagree. PARTHA's answer is to derive it once, in one place, and make everything else a consumer.

---

## What currently works

Statuses below were checked against the implementation, not against prior documentation.

| Capability | Status | Notes |
| --- | --- | --- |
| Archive upload (`.zip`, `.tar.gz`) | **Implemented** | Size caps; path-traversal and symlink escape rejected; empty and invalid archives rejected. |
| Public GitHub import | **Implemented** | Shallow clone of public HTTPS GitHub URLs, with clone timeout and size cap. Records the HEAD commit. Private repositories and other hosts are not supported. |
| Repository explorer and file preview | **Implemented** | File tree, text and image preview, binary detection, truncation of large files. |
| Documentation and report export | **Implemented** | JSON, Markdown, HTML, and PDF through a shared report pipeline. |
| Authentication and frontend session flow | **Implemented** | Email/password with Argon2, short-lived access tokens, rotating refresh tokens with reuse detection. All frontend routes are behind an auth guard. |
| Repository Intelligence | **Implemented but limited** | Extracts discovery facts, file roles, imports/exports, routes, symbols, modules, and dependencies, then persists and reuses them. Extraction is regex- and path-convention-based, not language-aware. |
| Architecture output | **Implemented but limited** | Modules, layers, relationships, and an interactive graph — with heuristic module and layer assignment. |
| Dependency inventory | **Implemented but limited** | Reads `package.json`, `requirements.txt`, and `pyproject.toml`. Other ecosystems and lockfiles are not parsed. |
| Engineering review | **Implemented but limited** | A fixed set of heuristic checks with derived category scores. Scores are arithmetic over finding severities, not a measured quality metric. |
| AI provider integration | **Implemented but limited** | Several providers behind one abstraction. Provider configuration is global rather than per-user. |
| Authorization and owner isolation | **Partially implemented** | Repository routes are owner-scoped. Analysis, AI, documentation, and export routes are not, and the backend still accepts unauthenticated requests. |
| Citations and grounded AI answers | **Not implemented** | No source content or line numbers are sent to providers, and no citations are returned. |
| Asynchronous / incremental processing | **Not implemented** | Ingestion and analysis run synchronously in the request; there is no background job system and no incremental re-analysis. |
| Change-impact analysis | **Not implemented** | — |
| Vulnerability and outdated-dependency scanning | **Not implemented** | The API exposes these fields, but they are constants. No scanning is performed. |
| Persistent semantic knowledge graph | **Not implemented** | The graph is serialized as JSON onto the repository row; there is no queryable graph store. |

A capability is listed as implemented only where the behaviour exists in code — not because a model, an API field, a class name, or an issue describes it.

---

## Evidence and provenance

Two terms PARTHA uses precisely, because the difference decides how far a claim can be trusted.

- **Evidence** is the source artifact supporting a repository fact: a file, declaration, import, route, or configuration entry.
- **Provenance** identifies where the fact came from: repository revision, path, symbol, line span, and extraction method.

**PARTHA currently provides only partial evidence and provenance.** Facts carry the *file* they came from. They do not carry line spans, they do not record which extraction method produced them, and they are not addressed to a specific revision — the commit is recorded on the repository, not on the fact.

So PARTHA can tell you *which file* a fact came from. It cannot yet tell you which line, from which revision, or how the fact was derived. It does not provide exact file-symbol-line-commit traceability, complete citations, fully evidence-backed AI answers, a persistent semantic knowledge graph, or language-aware extraction. Treat heuristic output as a lead to verify, not a guarantee.

---

## How the system works

A repository is parsed once at ingestion. Repository Intelligence is built from that parse, persisted, and read back by every surface.

```mermaid
flowchart LR
    Input["Repository input<br/>archive · public GitHub clone"]
    Ingest["Ingestion and parsing<br/>storage · repository parser"]
    RI["Repository Intelligence<br/>shared repository-understanding layer"]
    Consumers["Architecture · Dependencies<br/>Reviews · Documentation · Exports"]
    AI["AI<br/>optional consumer"]

    Input --> Ingest --> RI --> Consumers
    RI -.-> AI
```

Consumers transform Repository Intelligence into their own response shapes. None of them opens repository files or re-parses the tree, and the export pipeline is a second-order consumer that renders analysis output that already exists.

> **The rule.** If a feature needs a repository fact, add reusable extraction to `app/intelligence/`. Do not build a second parser inside a consumer.

### Runtime shape

```mermaid
flowchart LR
    UI["Frontend<br/>React · Vite · TypeScript"]
    API["REST API<br/>FastAPI"]
    RI["Repository Intelligence"]
    DB[("SQLite local<br/>PostgreSQL via Compose")]
    Disk[("Local filesystem")]

    UI --> API --> RI
    RI --> DB
    RI --> Disk
```

Deeper detail lives in [System Overview](docs/architecture/SYSTEM_OVERVIEW.md) and [Repository Intelligence](docs/architecture/REPOSITORY_INTELLIGENCE.md).

---

## Repository structure

```text
PARTHA/
├── apps/
│   ├── backend/              FastAPI backend
│   │   ├── app/
│   │   │   ├── api/          Routes and dependency wiring
│   │   │   ├── intelligence/ Repository Intelligence engine and models
│   │   │   ├── parsers/      File-tree parser
│   │   │   ├── analysis/     Architecture modelling (consumer)
│   │   │   ├── graph/        Dependency graph construction (consumer)
│   │   │   ├── review/       Engineering review (consumer)
│   │   │   ├── ai/           Orchestration, context, prompts, providers (consumer)
│   │   │   ├── reports/      Report model, renderers, export service
│   │   │   ├── auth/         Password hashing, tokens, auth service
│   │   │   ├── core/         Config, database, logging, rate limiting, security headers
│   │   │   ├── models/       SQLAlchemy models
│   │   │   └── storage/      Local repository and upload storage
│   │   ├── alembic/          Database migrations
│   │   └── tests/            Backend tests
│   └── frontend/             React frontend
│       └── src/
│           ├── app/          Shell, router, pages, stores
│           ├── features/     Domain features
│           └── shared/       API clients, UI, config, types, utilities
├── docs/                     Public documentation
├── packages/                 Reserved for future shared packages
├── scripts/                  Local workflow helpers
└── docker-compose.yml        Local development stack
```

---

## Getting started

| Tool | Version |
| --- | --- |
| Python | 3.12 or 3.13 |
| Node.js | 22 |
| Git | Required for GitHub repository import |
| Docker | Optional, for the local Compose stack |

### Backend

The backend defaults to SQLite and local filesystem storage, so it starts with no PostgreSQL and no Redis.

```bash
git clone https://github.com/Second-Origin/PARTHA.git
cd PARTHA

cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..

npm run dev:backend
```

The API is then on `http://localhost:8000` — OpenAPI docs at `/docs`, readiness at `/ready`.

No `.env` file is required for local development: every setting has a working default. Copy `apps/backend/.env.example` only when you want to change one.

### Frontend

```bash
npm ci --prefix apps/frontend
npm run dev:frontend
```

The app is then on `http://localhost:5173` and expects the backend on `http://localhost:8000`. Register an account through the UI, then sign in.

### Docker Compose (local development only)

Compose runs the API against PostgreSQL and Redis for local development. It is not deployment guidance.

```bash
npm run docker:config     # validate the Compose file
npm run docker:up         # start the local stack
npm run docker:validate   # start, wait for /ready, tear down
```

Run the frontend separately with `npm run dev:frontend`.

---

## Testing

```bash
npm run test:backend                  # backend tests (pytest)
npm --prefix apps/frontend run test   # frontend tests (vitest)
npm run lint:frontend                 # eslint
npm run build:frontend                # tsc -b && vite build
```

`npm run build` runs the frontend build and the backend tests; it does not run frontend lint or frontend tests, so run those separately. CI runs all of the above plus a Docker Compose check.

Backend coverage is the stronger of the two. Frontend coverage is thin and there is no end-to-end suite, so passing tests indicate the covered paths work rather than overall maturity.

---

## Limitations

- **Use only in a trusted local environment.** Multi-user authentication and owner isolation are not consistently enforced across every backend surface. PARTHA is not production-ready and should not be exposed to untrusted users or the public internet.
- **Extraction is heuristic.** File roles, modules, and layers are inferred from paths and filenames; symbols come from regular expressions. Expect wrong answers on projects that do not follow common conventions, and do not treat heuristic output as guaranteed fact.
- **Evidence and provenance are partial.** File-level only — no line spans, no per-fact extraction method, no revision-addressed facts.
- **No persistent semantic graph.** Repository facts are serialized as JSON onto the repository row rather than into a queryable graph store.
- **Analysis is synchronous and whole-repository.** No background jobs, no incremental re-analysis.
- **No change-impact analysis, and no vulnerability or outdated-dependency scanning.**
- **AI answers are not evidence-backed.** They are grounded in repository structure and file paths only, with no citations. Treat them as a hypothesis to verify.

---

## Contributing and security

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — the contribution rules: fork-first workflow, claiming an issue, branch naming, rebasing, pull requests, and the Definition of Ready and Done. Read it before opening a PR.
- **[SECURITY.md](SECURITY.md)** — report a vulnerability privately. Never open a public issue for one.
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** — expected conduct.
- **[docs/README.md](docs/README.md)** — documentation index.

Before changing analysis behaviour, read [Repository Intelligence](docs/architecture/REPOSITORY_INTELLIGENCE.md). That boundary is the one architectural rule this project will not bend on.

Current behaviour belongs in documentation. Future work belongs in GitHub issues.

---

## License

PARTHA is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the full text.
