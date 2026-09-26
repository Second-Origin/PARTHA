"""Timestamps are stored and served as explicit UTC (#473).

SQLite has no timezone-aware column type, so ``DateTime(timezone=True)`` came
back naive and the API emitted e.g. ``2026-09-25T23:47:39`` with no ``Z``. A
browser reads that as *local* time, so an account created just before
midnight UTC showed the wrong day for anyone east of Greenwich.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import Column, MetaData, Table, select

from app.core import database
from app.models.types import UTCDateTime

_EXPLICIT_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$")


def test_api_timestamps_carry_an_explicit_utc_designator(auth_client):
    response = auth_client.get("/auth/me")

    assert response.status_code == 200, response.text
    assert _EXPLICIT_UTC.match(response.json()["createdAt"]), response.json()["createdAt"]


def test_a_value_written_aware_is_read_back_aware_utc(client):
    table = Table("utc_probe", MetaData(), Column("at", UTCDateTime()))
    table.create(database.engine)
    db_session = database.SessionLocal()
    plus_one = timezone(timedelta(hours=1))
    written = datetime(2026, 9, 26, 0, 47, 39, tzinfo=plus_one)  # 23:47:39 UTC the day before
    db_session.execute(table.insert().values(at=written))

    read = db_session.execute(select(table.c.at)).scalar_one()

    db_session.close()
    assert read.tzinfo is not None
    assert read.utcoffset() == timedelta(0)
    assert read == written
    assert read == datetime(2026, 9, 25, 23, 47, 39, tzinfo=UTC)


def test_a_naive_value_is_taken_as_utc_and_none_is_preserved(client):
    table = Table("utc_probe_naive", MetaData(), Column("at", UTCDateTime(), nullable=True))
    table.create(database.engine)
    db_session = database.SessionLocal()
    db_session.execute(table.insert().values(at=datetime(2026, 1, 2, 3, 4, 5)))
    db_session.execute(table.insert().values(at=None))

    values = db_session.execute(select(table.c.at).order_by(table.c.at.is_(None))).scalars().all()

    db_session.close()
    assert values == [datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), None]
