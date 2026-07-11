FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY requirements.txt ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Install the pinned lockfile first, then the app itself without re-resolving
# dependencies, so the image matches requirements.txt exactly.
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir -e . --no-deps

EXPOSE 8000

# Run database migrations before serving so Alembic is authoritative for schema
# (AUTO_CREATE_TABLES should be false in non-dev; see docker-compose.yml).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
