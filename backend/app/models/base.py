from datetime import datetime, timezone

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class UTCDateTime(TypeDecorator):
    """
    A DateTime column type that always returns timezone-aware UTC datetimes.

    SQLite has no native datetime type and returns naive datetime objects on
    read-back, even when the column is declared DateTime(timezone=True).
    This TypeDecorator transparently re-attaches UTC tzinfo on every read so
    that datetime objects are always timezone-aware throughout the stack.

    Write:  accepts both aware and naive datetimes; naive are assumed UTC.
    Read:   always returns datetime with tzinfo=timezone.utc.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # Treat naive datetimes as UTC rather than silently losing info.
            return value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # SQLite strips tzinfo on read — re-attach UTC.
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass
