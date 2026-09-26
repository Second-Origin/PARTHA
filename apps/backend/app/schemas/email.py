"""Email address validation for account requests.

``pydantic.EmailStr`` rejects every special-use domain (``.local``, ``.test``,
``.localhost``...) because it assumes the address must be deliverable on the
public internet. PARTHA is a self-hosted tool: a team on a private network
legitimately uses addresses such as ``alice@corp.local``, and access is
controlled by the operator's approved-email list rather than by whether a
domain is publicly routable. Only the shape is validated here.
"""

from __future__ import annotations

import re
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field

_MAX_ADDRESS_LENGTH = 254
# One or more dot-separated hostname labels (letters, digits, hyphens), no
# label starting or ending with a hyphen. Internal single-label hosts
# (``user@intranet``) are not accepted: mail systems need a dot, and the
# frontend's own check does too.
_DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def validate_account_email(value: str) -> str:
    value = value.strip()
    local, at, domain = value.rpartition("@")
    if not at or not local or not domain:
        raise ValueError("Enter an email address like name@company.com.")
    if len(value) > _MAX_ADDRESS_LENGTH:
        raise ValueError("That email address is too long.")
    try:
        # The local part gets the library's full syntax check; the domain is
        # checked below so that private-network names are not refused.
        checked_local = validate_email(f"{local}@example.com", check_deliverability=False).local_part
    except EmailNotValidError as error:
        raise ValueError(str(error)) from error
    domain = domain.lower()
    if not _DOMAIN.match(domain):
        raise ValueError("The part after the @ must be a domain name such as company.com or corp.local.")
    return f"{checked_local}@{domain}"


#: A syntactically valid email address, private-network domains included.
#: ``format: email`` is kept in the schema so the API contract is unchanged.
EmailAddress = Annotated[
    str,
    AfterValidator(validate_account_email),
    Field(json_schema_extra={"format": "email"}),
]
