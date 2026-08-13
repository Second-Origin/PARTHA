"""Verified, cascading account deletion (#290).

Deletion is truthful: the response completes only after the account is
inaccessible and every owner-scoped database row is gone. The database
transaction is the point of no return -- once it commits, the user can no
longer authenticate, refresh, or be found by any owner-scoped query, because
every owner foreign key cascades from the ``users`` row at the database level
(0010_account_deletion). Filesystem cleanup of repository source is
deliberately a *separate*, best-effort step that runs only after that commit
succeeds: the account is already gone from the caller's perspective by then,
so a stray unremovable directory is an operational cleanup concern, not a
reason to report deletion as failed to an account that no longer exists.
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth.security import verify_password
from app.core.exceptions import UnauthorizedError, ValidationServiceError
from app.models.account_deletion_audit import AccountDeletionAuditRecord
from app.models.user import SEED_USER_ID, User
from app.repositories.repository_repository import RepositoryRepository
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

# Matches the auth module's existing "don't reveal which part was wrong"
# convention: a deletion attempt is a credential check like any other.
INVALID_PASSWORD = "Invalid password."
CONFIRMATION_MISMATCH = "Confirmation email does not match your account email."
SEED_USER_UNDELETABLE = "The system account cannot be deleted."


class AccountDeletionService:
    def __init__(self, db: Session, repository: RepositoryRepository, storage: LocalStorage) -> None:
        self.db = db
        self.repository = repository
        self.storage = storage

    def delete_account(self, user: User, password: str, confirm_email: str) -> None:
        self._authenticate_for_deletion(user, password, confirm_email)

        audit_id = str(uuid4())
        now = datetime.now(UTC)
        self.db.add(
            AccountDeletionAuditRecord(id=audit_id, deleted_user_id=user.id, status="in_progress", requested_at=now)
        )
        self.db.commit()

        # Storage paths must be collected before the cascading delete below:
        # once the user row is gone, the repository rows that named them are
        # gone too, and there is nothing left to query.
        local_paths = [record.local_path for record in self.repository.list_for_owner(user.id)]

        try:
            self.db.delete(user)
            audit = self.db.get(AccountDeletionAuditRecord, audit_id)
            assert audit is not None
            audit.status = "completed"
            audit.completed_at = datetime.now(UTC)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self._record_failure(audit_id, exc)
            raise

        for local_path in local_paths:
            try:
                self.storage.delete_repository(local_path)
            except OSError:
                logger.error(
                    "Account deletion storage cleanup failed for a repository path",
                    extra={"deleted_user_id": user.id},
                    exc_info=True,
                )

    def _authenticate_for_deletion(self, user: User, password: str, confirm_email: str) -> None:
        if user.id == SEED_USER_ID:
            raise ValidationServiceError(SEED_USER_UNDELETABLE)
        if user.password_hash is None or not verify_password(user.password_hash, password):
            raise UnauthorizedError(INVALID_PASSWORD)
        if confirm_email.strip().lower() != user.email:
            raise ValidationServiceError(CONFIRMATION_MISMATCH)

    def _record_failure(self, audit_id: str, exc: Exception) -> None:
        audit = self.db.get(AccountDeletionAuditRecord, audit_id)
        if audit is not None:
            audit.status = "failed"
            audit.failure_reason = str(exc)[:255]
            self.db.commit()
