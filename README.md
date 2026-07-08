# PARTHA

> **AI Software Architecture Intelligence Platform**
>
> Analyze, understand and explore any codebase through architecture visualization, dependency analysis, engineering reviews and AI-assisted repository intelligence.

---

## Overview

PARTHA is a full-stack developer platform that helps engineers quickly understand unfamiliar repositories.

Instead of manually exploring hundreds of files, PARTHA analyzes a repository and generates:

- Architecture diagrams
- Dependency graphs
- Engineering reviews
- Repository documentation
- AI-assisted codebase exploration
- Repository insights and metrics

The platform is designed for onboarding developers, technical due diligence, architecture reviews and large-scale codebase understanding.

---

## Features

### Repository Management

- Import public GitHub repositories
- Upload local repositories as ZIP archives
- Repository dashboard
- Repository explorer
- Repository persistence

### Architecture Intelligence

- Interactive architecture graph
- Request flow visualization
- Module explorer
- Dependency analysis
- Architecture metrics

### Engineering Review

- Code quality analysis
- Technical debt overview
- Risk assessment
- Improvement recommendations

### Documentation

Generate:

- Project overview
- Folder structure
- API summary
- Environment configuration
- Deployment guide
- Contribution guide

Export as Markdown or HTML.

### AI Workspace

Repository-aware AI assistant supporting configurable providers:

- OpenAI
- Anthropic
- Google Gemini
- OpenRouter
- Ollama

---

## Architecture

```text
partha
│
├── apps
│   ├── frontend
│   └── backend
│
├── docs
├── packages
└── scripts
```

### Frontend

- React
- TypeScript
- Vite
- React Router
- Tailwind CSS

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis

---

## Technology Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- React Flow

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- GitPython
- Pydantic v2

### Infrastructure

- Docker
- PostgreSQL
- Redis

---

## Getting Started

### Frontend

```bash
cd apps/frontend
npm install
npm run dev
```

### Backend

```bash
cd apps/backend

python3.13 -m venv .venv
source .venv/bin/activate

pip install -e .

uvicorn app.main:app --reload
```

---

## Project Status

PARTHA is under active development.

Current focus:

- Improve repository parsing
- Expand architecture intelligence
- Enhance AI-assisted repository understanding
- Improve engineering review accuracy

---

## License

MIT