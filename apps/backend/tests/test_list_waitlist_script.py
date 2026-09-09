"""CSV/formula-injection guard for scripts/list_waitlist.py's --csv export."""

import pytest

from scripts.list_waitlist import _csv_safe


@pytest.mark.parametrize(
    "raw",
    ["=cmd|'/c calc'!A1", "+1+1", "-2+3", "@SUM(A1:A9)"],
)
def test_leading_formula_trigger_is_neutralized(raw: str) -> None:
    safe = _csv_safe(raw)

    assert safe.startswith("'")
    assert safe == f"'{raw}"


@pytest.mark.parametrize("raw", ["Jane Doe", "person@example.com", ""])
def test_ordinary_values_pass_through_unchanged(raw: str) -> None:
    assert _csv_safe(raw) == raw
