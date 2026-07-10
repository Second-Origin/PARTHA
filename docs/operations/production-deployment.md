# Production Deployment

This guide describes the production deployment baseline for PARTHA. It is intentionally platform-neutral: the current repository ships a backend container and Docker Compose development stack, while production hosting can be Docker, a VM, or a managed container platform.

## Deployment Model

PARTHA currently supports a controlled single-operator deployment model:

- FastAPI backend served by the backend Docker image.
- PostgreSQL database managed outside the application container.
- Redis endpoint configured for workflows that need it.
- Writable persistent storage mounted at `STORAGE_PATH`.
- Frontend built with Vite and served by a static host or reverse proxy.
- TLS, domain routing, and network policy handled by the hosting platform or reverse proxy.

PARTHA does not yet include authentication, authorization, tenant isolation, or multi-user account management. Do not expose a deployment as a public multi-user SaaS until those controls are implemented.

## Required Environment

| Variable | Production guidance |
| --- | --- |
| `APP_ENV` | Set to `production`. |
| `LOG_LEVEL` | Use `INFO` by default; use `WARNING` for quieter environments. |
| `LOG_FORMAT` | Use `json` for hosted/container logs. |
| `DATABASE_URL` | Use a managed PostgreSQL URL with TLS where available. |
| `REDIS_URL` | Use a managed Redis URL if Redis-backed workflows are enabled. |
| `STORAGE_PATH` | Mount persistent storage; the app writes uploaded and cloned repository artifacts here. |
| `CORS_ORIGINS` | Set explicit HTTPS frontend origins. Do not use wildcards. |
| `AUTO_CREATE_TABLES` | Set `false`; run migrations explicitly. |
| `CLONE_TIMEOUT_SECONDS` | Tune for repository size and hosting limits. |
| `MAX_UPLOAD_SIZE_BYTES` | Keep aligned with reverse proxy and platform upload limits. |
| `MAX_CLONE_SIZE_BYTES` | Maximum on-disk size of a cloned GitHub repository (default 500 MiB). Over-limit clones are aborted and cleaned up. |

Secrets such as database credentials, Redis credentials, and future provider credentials must be supplied through the hosting platform secret manager. Do not bake secrets into images, Compose files, or committed env files.

## Startup Procedure

1. Build and publish the backend image from `apps/backend/Dockerfile`.
2. Build the frontend with `npm run build:frontend`.
3. Provision PostgreSQL and Redis.
4. Mount persistent storage for `STORAGE_PATH`.
5. Run database migrations:

   ```bash
   cd apps/backend
   alembic upgrade head
   ```

6. Start the backend with:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

7. Serve frontend static assets from `apps/frontend/dist`.
8. Configure the frontend `VITE_API_URL` at build time to point at the backend origin.

## Health and Readiness

Use:

- `GET /health` for lightweight liveness.
- `GET /ready` for database and writable-storage readiness.
- `GET /metrics` for basic plain-text runtime counters.

Production load balancers should use `/ready` for traffic routing and `/health` for basic process liveness. Alert when `/ready` fails or 5xx metrics increase.

## Rollback

Rollback should be image/tag based:

1. Keep the previous backend image available.
2. Keep the previous frontend artifact available.
3. Roll back application containers first.
4. Roll back database migrations only when a migration explicitly documents a safe downgrade.
5. Verify `/ready` and smoke-test repository list/import flows after rollback.

## Operational Limits

Before a public multi-user deployment, complete:

- authentication and authorization;
- source retention and deletion policy;
- provider secret management;
- request and data retention policy;
- abuse controls for repository import and upload size;
- external monitoring and alerting.
