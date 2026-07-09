# Observability

PARTHA includes a minimal built-in observability baseline for local, staging, and controlled production deployments.

## Request IDs

Every backend response includes `X-Request-ID`.

- If a request includes `X-Request-ID`, PARTHA preserves it.
- If it is absent, PARTHA generates one.
- JSON logs include `request_id` when available.
- Standard backend error responses include `request_id` for support correlation.

## Logs

Set `LOG_FORMAT=json` for structured container logs. Text logs are intended for local development.

Sensitive log fields are redacted when emitted through structured `extra` data. Keys containing these fragments are redacted:

- `api_key`
- `apikey`
- `authorization`
- `password`
- `secret`
- `token`

Do not log repository source contents, provider credentials, database URLs with credentials, or uploaded archive content.

## Metrics

`GET /metrics` exposes plain-text counters:

- total HTTP requests;
- cumulative request duration;
- requests by status family;
- requests by method, route, and status code.

These counters are intentionally small and dependency-free. A production deployment can scrape or adapt them, but external monitoring should own alerting, retention, and dashboards.

## Health Checks

Use:

- `/health` for process liveness;
- `/ready` for database and writable-storage readiness.

`/ready` returns `503` when a required dependency check fails.

## Tracing Baseline

PARTHA does not yet ship OpenTelemetry instrumentation. The request ID contract is the current trace-correlation baseline. If OpenTelemetry is added later, it should preserve `X-Request-ID` compatibility.
