"""Owner-scoped, encrypted-at-rest storage for AI provider configuration.

Every read and write is scoped to a single ``owner_id``, so one user can never
observe or spend another user's provider key (E1.5 / #65, and the credential
half of the ``ai/*`` scoping in #63). API keys are encrypted with
:class:`ProviderKeyCipher` before they touch the database and are decrypted only
in-process, at request time, to talk to the provider — they are never returned
to the client in full (the public config exposes only ``last4``).
"""

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ai_egress import DestinationPolicyError, ProviderEgressPolicy
from app.ai.types import DEFAULT_MODELS, AiProviderConfig
from app.core.crypto import InvalidToken, ProviderKeyCipher
from app.core.exceptions import ValidationServiceError
from app.models.ai_provider_config import AiProviderConfigRecord
from app.schemas.ai import AiProviderPublicConfig, AiProviderTestRequest


class ProviderConfigStore(Protocol):
    """The surface the orchestrator depends on, independent of storage."""

    def get_public_config(self) -> AiProviderPublicConfig:
        raise NotImplementedError

    def save_config(self, config: AiProviderConfig) -> AiProviderPublicConfig:
        raise NotImplementedError

    def read_config(self) -> AiProviderConfig | None:
        raise NotImplementedError

    def config_for_test(self, request: AiProviderTestRequest) -> AiProviderConfig:
        raise NotImplementedError


class EncryptedProviderConfigStore:
    """Persists one provider configuration per user, key encrypted at rest."""

    def __init__(
        self,
        db: Session,
        cipher: ProviderKeyCipher,
        owner_id: str,
        egress_policy: ProviderEgressPolicy | None = None,
    ) -> None:
        self.db = db
        self.cipher = cipher
        self.owner_id = owner_id
        if egress_policy is None:
            from app.core.config import get_settings

            egress_policy = ProviderEgressPolicy.from_settings(get_settings())
        self.egress_policy = egress_policy

    def _record(self) -> AiProviderConfigRecord | None:
        statement = select(AiProviderConfigRecord).where(AiProviderConfigRecord.owner_id == self.owner_id)
        return self.db.scalars(statement).first()

    def _decrypt_key(self, record: AiProviderConfigRecord) -> str | None:
        if not record.encrypted_api_key:
            return None
        try:
            return self.cipher.decrypt(record.encrypted_api_key)
        except InvalidToken:
            # Ciphertext that no longer decrypts (e.g. the encryption key was
            # rotated without re-encrypting) is treated as "no usable key" so
            # the caller surfaces the clear missing-key error rather than a 500.
            return None

    def get_public_config(self) -> AiProviderPublicConfig:
        record = self._record()
        if record is None:
            return AiProviderPublicConfig()
        return AiProviderPublicConfig(
            provider=record.provider,
            model=record.model,
            base_url=record.base_url,
            has_api_key=bool(record.encrypted_api_key),
            api_key_last4=record.api_key_last4,
        )

    def read_config(self) -> AiProviderConfig | None:
        record = self._record()
        if record is None:
            return None
        return AiProviderConfig(
            provider=record.provider,
            api_key=self._decrypt_key(record),
            model=record.model,
            base_url=record.base_url,
        )

    def save_config(self, config: AiProviderConfig) -> AiProviderPublicConfig:
        # Validate the complete destination policy before touching a record or
        # constructing ciphertext.  A denied save therefore cannot create or
        # partially mutate a provider configuration.
        try:
            self.egress_policy.validate_config(config)
        except DestinationPolicyError as exc:
            raise ValidationServiceError("AI provider destination is not permitted.") from exc
        record = self._record()
        encrypted, last4 = self._resolve_key(config, record)
        model = config.model or DEFAULT_MODELS[config.provider]
        now = datetime.now(UTC)

        if record is None:
            record = AiProviderConfigRecord(
                id=str(uuid4()),
                owner_id=self.owner_id,
                provider=config.provider,
                encrypted_api_key=encrypted,
                api_key_last4=last4,
                model=model,
                base_url=config.base_url,
                created_at=now,
                updated_at=now,
            )
            self.db.add(record)
        else:
            record.provider = config.provider
            record.encrypted_api_key = encrypted
            record.api_key_last4 = last4
            record.model = model
            record.base_url = config.base_url
            record.updated_at = now

        self.db.commit()
        self.db.refresh(record)
        return self.get_public_config()

    def _resolve_key(
        self, config: AiProviderConfig, record: AiProviderConfigRecord | None
    ) -> tuple[str | None, str | None]:
        """Determine the ciphertext + last-4 to persist for this save.

        A new key is encrypted fresh. An omitted key carries the previously
        stored ciphertext forward (so re-saving model/base_url does not require
        re-entering the key), and only ollama may be saved with no key at all.
        """
        if config.api_key:
            return self.cipher.encrypt(config.api_key), config.api_key[-4:]
        if (
            config.provider != "ollama"
            and record is not None
            and record.provider == config.provider
            and record.encrypted_api_key
        ):
            return record.encrypted_api_key, record.api_key_last4
        if config.provider == "ollama":
            return None, None
        raise ValidationServiceError("API key is required for this provider.")

    def config_for_test(self, request: AiProviderTestRequest) -> AiProviderConfig:
        saved = self.read_config()
        provider = request.provider or (saved.provider if saved else None)
        if not provider:
            raise ValidationServiceError("Choose an AI provider before testing.")
        same_provider = saved is not None and saved.provider == provider
        return AiProviderConfig(
            provider=provider,
            api_key=request.api_key or (saved.api_key if same_provider else None),
            model=request.model or (saved.model if same_provider else None) or DEFAULT_MODELS[provider],
            base_url=request.base_url or (saved.base_url if same_provider else None),
        )
