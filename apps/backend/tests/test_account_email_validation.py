"""Account emails: private-network domains work, and a rejection says why (#477)."""

from __future__ import annotations

import pytest

from app.schemas.email import validate_account_email


@pytest.mark.parametrize(
    "address",
    ["alice@corp.local", "bob@team.internal", "carol@lab.test", "Dave.Smith+tag@Company.COM", "eve@a-b.example.co.uk"],
)
def test_private_and_ordinary_domains_are_accepted(address):
    assert validate_account_email(address).lower() == address.lower()


def test_the_domain_is_lowercased_and_the_local_part_kept():
    assert validate_account_email("Dave.Smith@Company.COM") == "Dave.Smith@company.com"


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("no-at-sign", "name@company.com"),
        ("@company.com", "name@company.com"),
        ("alice@", "name@company.com"),
        ("alice@intranet", "domain name"),
        ("alice@-bad.com", "domain name"),
        ("alice@bad_domain.com", "domain name"),
        ("a b@company.com", "SPACE"),
    ],
)
def test_malformed_addresses_are_rejected_with_a_reason(address, reason):
    with pytest.raises(ValueError, match=reason):
        validate_account_email(address)


def test_registration_accepts_a_corp_local_address(client):
    response = client.post("/auth/register", json={"email": "alice@corp.local", "password": "correct-horse-battery-9"})

    assert response.status_code == 201, response.text
    assert response.json()["user"]["email"] == "alice@corp.local"


def test_registration_says_what_is_wrong_with_the_email(client):
    response = client.post("/auth/register", json={"email": "alice@intranet", "password": "correct-horse-battery-9"})

    assert response.status_code == 422
    errors = response.json()["details"]["errors"]
    assert errors[0]["loc"] == ["body", "email"]
    assert errors[0]["msg"].startswith("The part after the @ must be a domain name")
    assert "Value error" not in errors[0]["msg"]


def test_login_accepts_the_same_private_domains(client):
    client.post("/auth/register", json={"email": "alice@corp.local", "password": "correct-horse-battery-9"})

    response = client.post("/auth/login", json={"email": "alice@corp.local", "password": "correct-horse-battery-9"})

    assert response.status_code == 200, response.text
