from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from threading import Lock
from uuid import uuid4

SENSITIVE_FIELD_FRAGMENTS = ("api_key", "apikey", "authorization", "password", "secret", "token")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    return uuid4().hex


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(request_id: str) -> object:
    return _request_id.set(request_id)


def reset_request_id(token: object) -> None:
    _request_id.reset(token)


def redact_mapping(values: dict[str, object]) -> dict[str, object]:
    return {key: redact_value(key, value) for key, value in values.items()}


def redact_value(key: str, value: object) -> object:
    normalized = key.lower().replace("-", "_")
    if any(fragment in normalized for fragment in SENSITIVE_FIELD_FRAGMENTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return redact_mapping(value)
    return value


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_total = 0
        self._request_duration_seconds = 0.0
        self._status_counts: Counter[str] = Counter()
        self._route_counts: Counter[tuple[str, str, str]] = Counter()

    def record_request(self, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        status_family = f"{status_code // 100}xx"
        with self._lock:
            self._request_total += 1
            self._request_duration_seconds += duration_seconds
            self._status_counts[status_family] += 1
            self._route_counts[(method, route, str(status_code))] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP partha_http_requests_total Total HTTP requests handled by the backend.",
                "# TYPE partha_http_requests_total counter",
                f"partha_http_requests_total {self._request_total}",
                "# HELP partha_http_request_duration_seconds_total Cumulative HTTP request duration in seconds.",
                "# TYPE partha_http_request_duration_seconds_total counter",
                f"partha_http_request_duration_seconds_total {self._request_duration_seconds:.6f}",
                "# HELP partha_http_requests_by_status_total HTTP requests grouped by status family.",
                "# TYPE partha_http_requests_by_status_total counter",
            ]
            for status_family, count in sorted(self._status_counts.items()):
                lines.append(f'partha_http_requests_by_status_total{{status_family="{status_family}"}} {count}')

            lines.extend(
                [
                    "# HELP partha_http_requests_by_route_total HTTP requests grouped by method, route, and status.",
                    "# TYPE partha_http_requests_by_route_total counter",
                ]
            )
            for (method, route, status_code), count in sorted(self._route_counts.items()):
                lines.append(
                    "partha_http_requests_by_route_total"
                    f'{{method="{method}",route="{route}",status_code="{status_code}"}} {count}'
                )
            return "\n".join(lines) + "\n"


runtime_metrics = RuntimeMetrics()
