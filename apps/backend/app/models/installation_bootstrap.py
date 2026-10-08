"""Permanent installation claim; deliberately unrelated to user deletion."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InstallationBootstrap(Base):
    __tablename__ = "installation_bootstrap"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)


BOOTSTRAP_ID = "installation"
