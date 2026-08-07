# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git build-essential \
  && rm -rf /var/lib/apt/lists/*

# Dependency manifests are copied and installed before the application source,
# so editing app/ (which happens on nearly every build) invalidates only the
# fast steps below, not this one -- only a real requirements.txt/pyproject.toml
# change does. A BuildKit cache mount keeps pip's own download cache across
# rebuilds too, so even a genuine dependency change does not re-fetch wheels
# already on disk.
COPY pyproject.toml requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install --upgrade pip \
  && pip install -r requirements.txt

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# The app itself, without re-resolving dependencies, so the image matches
# requirements.txt exactly. Cheap: editable install with --no-deps does no
# wheel building or network fetch, so re-running this on every source change
# costs nothing.
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install -e . --no-deps

EXPOSE 8000

# Run database migrations before serving so Alembic is authoritative for schema
# (AUTO_CREATE_TABLES should be false in non-dev; see docker-compose.yml).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
