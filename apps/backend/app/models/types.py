"""Column types shared by the ORM models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp that is stored as UTC and always read back timezone-aware.

    SQLite has no timezone-aware column type: ``DateTime(timezone=True)`` keeps
    the wall-clock text and returns a *naive* value, which the API then
    serialized without a ``Z`` and a browser read as local time (#473).
    PostgreSQL's ``timestamptz`` returns aware values in the session's zone.
    This type normalises both: writes are converted to UTC (a naive value is
    taken to already be UTC -- every writer in this codebase uses
    ``datetime.now(UTC)``), and reads are UTC-aware. Rows already stored by
    SQLite hold UTC wall-clock text, so they read back correctly unchanged.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
