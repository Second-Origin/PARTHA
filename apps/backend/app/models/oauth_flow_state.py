from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OAuthFlowState(Base):
    """One in-flight OAuth authorization request (#288).

    ``state_hash`` is the sha256 of the actual ``state`` value sent to the
    provider and returned on callback -- the raw value is a bearer secret
    (the CSRF protection), so only its hash is stored, the same convention
    as refresh tokens and invite codes. Single-use by construction: the
    service deletes this row the moment a callback consumes it, success or
    failure, so a replayed callback can never reuse a state value. A row
    that outlives its ``expires_at`` (a few minutes) without a matching
    callback is simply an abandoned flow -- a real callback happens within
    seconds of the redirect.
    """

    __tablename__ = "oauth_flow_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32))
    # PKCE code verifier (Google only -- GitHub OAuth Apps do not support
    # PKCE, only the state CSRF check applies there).
    code_verifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # OIDC nonce (Google only), echoed back inside the returned id_token and
    # checked there to bind this specific flow to that specific token.
    nonce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # "login": create-or-authenticate a session for whichever user this
    # identity resolves to. "link": attach this provider identity to the
    # already-authenticated `link_user_id` instead.
    intent: Mapped[str] = mapped_column(String(16))
    link_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    # The frontend origin to send the browser back to once the callback
    # finishes, success or error -- captured from the request that started
    # this flow rather than recomputed at callback time, so the two ends of
    # one flow always agree even if a deployment ever serves the start and
    # callback routes through more than one entry origin.
    frontend_redirect_base: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("intent IN ('login', 'link')", name="ck_oauth_flow_states_intent"),)
