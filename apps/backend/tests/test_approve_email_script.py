"""scripts/approve_email.py (#374): the v1 admin mechanism for adding to the
registration allowlist that replaced invite codes (#341). Exercises `main()`
in-process against the same test database the `client` fixture configures,
the same idiom test_list_waitlist_script.py uses for its own script.
"""

import sys

import pytest

from scripts.approve_email import main


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["approve_email.py", *args])
    return main()


def test_approves_a_new_email_with_note_and_added_by(client, monkeypatch, capsys):
    exit_code = _run(monkeypatch, "--email", "jane@example.com", "--note", "waitlist: 2026", "--added-by", "parth")
    assert exit_code == 0
    assert "Approved jane@example.com" in capsys.readouterr().out

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail

    with SessionLocal() as session:
        approval = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == "jane@example.com")).one()
        assert approval.note == "waitlist: 2026"
        assert approval.added_by == "parth"
        assert approval.used_at is None


def test_normalizes_email_case_and_whitespace(client, monkeypatch):
    _run(monkeypatch, "--email", "  Jane@Example.COM  ")

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail

    with SessionLocal() as session:
        approval = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == "jane@example.com")).first()
        assert approval is not None


def test_defaults_added_by_to_the_current_os_user(client, monkeypatch):
    monkeypatch.setattr("scripts.approve_email.getpass.getuser", lambda: "fake-os-user")
    _run(monkeypatch, "--email", "nodefault@example.com")

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail

    with SessionLocal() as session:
        approval = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == "nodefault@example.com")).one()
        assert approval.added_by == "fake-os-user"


def test_approving_the_same_email_twice_is_a_harmless_no_op(client, monkeypatch, capsys):
    assert _run(monkeypatch, "--email", "twice@example.com") == 0
    capsys.readouterr()

    exit_code = _run(monkeypatch, "--email", "TWICE@example.com")  # same address, different case
    assert exit_code == 0
    assert "already approved" in capsys.readouterr().out

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail

    with SessionLocal() as session:
        count = session.scalar(
            select(func.count()).select_from(ApprovedEmail).where(ApprovedEmail.email == "twice@example.com")
        )
        assert count == 1


def test_a_freshly_approved_email_actually_satisfies_registration(client, monkeypatch):
    """End-to-end proof the script's output is exactly what AuthService.register()
    checks -- not a parallel table nobody actually reads."""
    _run(monkeypatch, "--email", "endtoend@example.com")

    response = client.post(
        "/auth/register", json={"email": "endtoend@example.com", "password": "correct-horse-battery-staple"}
    )
    assert response.status_code == 201, response.text
