# Single-service hosting (#339, #340): build the frontend, then serve it
# from the same FastAPI process that serves the API. Two stages so the
# runtime image never needs Node.js -- only the built static output crosses
# the stage boundary.

FROM node:22-slim AS frontend-build
WORKDIR /repo
COPY apps/frontend/package.json apps/frontend/package-lock.json apps/frontend/
RUN npm ci --prefix apps/frontend
COPY apps/frontend apps/frontend
# BrandLogo.tsx reaches outside apps/frontend to ../../docs/assets for the
# product logo -- a real, pre-existing cross-boundary reference in the
# source, not something this Dockerfile introduced. The build context has to
# include it at the same relative position or the build fails.
COPY docs docs
RUN npm run build --prefix apps/frontend

FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY apps/backend/pyproject.toml ./
COPY apps/backend/app ./app
COPY apps/backend/alembic.ini ./
COPY apps/backend/alembic ./alembic

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -e .

COPY --from=frontend-build /repo/apps/frontend/dist /app/frontend-dist
ENV FRONTEND_DIST_PATH=/app/frontend-dist

EXPOSE 8000
# $PORT is set by Render (and most PaaS hosts) at runtime; 8000 is only the
# local-Docker fallback. Migrations run here rather than as a separate,
# easy-to-forget manual step -- AUTO_CREATE_TABLES defaults to false outside
# development/test, so without this the app would boot against an unmigrated
# schema. Exec-form CMD wrapping an explicit shell (rather than bare shell
# form) so signals still reach the process directly.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
