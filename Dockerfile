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

FROM python:3.13-slim AS backend-build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# build-essential compiles any dependency without a prebuilt wheel; it is
# only ever needed at install time, so it is confined to this stage and
# never reaches the runtime image below.
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY apps/backend/requirements.txt ./
COPY apps/backend/pyproject.toml ./
COPY apps/backend/app ./app
COPY apps/backend/alembic.ini ./
COPY apps/backend/alembic ./alembic

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir --no-deps -e .
COPY apps/backend/scripts/check_runtime_dependencies.py ./scripts/check_runtime_dependencies.py
RUN python scripts/check_runtime_dependencies.py requirements.txt \
  && pip check \
  && python -c "import app.main, uvicorn, sqlalchemy, cryptography"

FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# git is a genuine runtime dependency -- app/github/client.py shells out to
# it to clone and inspect repositories being analyzed -- so it stays in the
# runtime image. The compiler toolchain above does not.
RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/* \
  && useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
  && mkdir /data \
  && chown appuser:appuser /data

# /data is where docker-compose.yml mounts its volume. Creating it here, owned
# by appuser, means a fresh named volume inherits that ownership instead of
# coming up root-owned and unwritable. Render mounts its own disk elsewhere
# (/var/data, render.yaml) and never touches this path.

COPY --from=backend-build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/backend/pyproject.toml ./
COPY apps/backend/app ./app
COPY apps/backend/alembic.ini ./
COPY apps/backend/alembic ./alembic
# Operator scripts (approve_email.py and friends), so a containerised install
# can run them with `docker compose exec` instead of needing a host checkout.
COPY apps/backend/scripts ./scripts

COPY --from=frontend-build /repo/apps/frontend/dist /app/frontend-dist
ENV FRONTEND_DIST_PATH=/app/frontend-dist

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
# $PORT is set by Render (and most PaaS hosts) at runtime; 8000 is only the
# local-Docker fallback. Migrations run here rather than as a separate,
# easy-to-forget manual step -- AUTO_CREATE_TABLES defaults to false outside
# development/test, so without this the app would boot against an unmigrated
# schema. Exec-form CMD wrapping an explicit shell (rather than bare shell
# form) so signals still reach the process directly.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
