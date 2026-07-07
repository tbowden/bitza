import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """
    Append-only event log — never updated or deleted. entity_type is a
    free string ("bitza", "team", ...), so this table needed zero changes
    for the Bitza/Team redesign; only its old home (app/models/asset.py)
    moved.

    This is deliberately NOT the same thing as StockLog/Checkout — those
    are domain-specific movement/usage logs that answer "who used the last
    one" / "is this always checked out". AuditLog is generic record-level
    accountability (create/update/delete of any entity), orthogonal to
    the stock/checkout minimalism discussed in the project context doc.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )
