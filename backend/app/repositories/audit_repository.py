from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditRepository:
    """
    Data-access layer for the audit_logs table.

    Split out into its own repository because AuditLog moved out of the
    old (now-deleted) app/models/asset.py into app/models/audit.py as
    part of the Bitza redesign — previously this lived embedded inside
    AssetRepository. Behaviour is otherwise unchanged.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, entry: AuditLog) -> AuditLog:
        self._db.add(entry)
        self._db.flush()
        return entry

    def list_all(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 200,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        return list(self._db.scalars(stmt).all())
