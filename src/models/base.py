"""
SQLAlchemy declarative base and shared mixins.

All ORM models import Base from here. Keeping Base in its own file
prevents circular imports between model files.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Shared base for all ORM models.
    Using DeclarativeBase (SQLAlchemy 2.0 style) gives us full type safety.
    """
    pass


class TimestampMixin:
    """
    Adds created_at and updated_at columns to any model that inherits it.

    created_at: set once at INSERT, never changed.
    updated_at: updated automatically on every UPDATE via onupdate.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
