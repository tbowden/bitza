from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetTransaction, AuditLog


class AssetRepository:
    """Data-access layer for assets, transactions, and audit log."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Asset reads
    # ------------------------------------------------------------------

    def get(self, asset_id: str) -> Optional[Asset]:
        return self._db.get(Asset, asset_id)

    def list_all(self) -> list[Asset]:
        stmt = select(Asset).order_by(Asset.name)
        return list(self._db.scalars(stmt).all())

    def list_by_location_detail(self, detail_id: str) -> list[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.location_detail_id == detail_id)
            .order_by(Asset.name)
        )
        return list(self._db.scalars(stmt).all())

    def list_by_category(self, category_id: str) -> list[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.category_id == category_id)
            .order_by(Asset.name)
        )
        return list(self._db.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Asset writes
    # ------------------------------------------------------------------

    def create(self, asset: Asset) -> Asset:
        self._db.add(asset)
        self._db.flush()
        self._db.refresh(asset)
        return asset

    def update(self, asset: Asset) -> Asset:
        self._db.flush()
        self._db.refresh(asset)
        return asset

    def delete(self, asset: Asset) -> None:
        self._db.delete(asset)
        self._db.flush()

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def get_transaction(self, txn_id: str) -> Optional[AssetTransaction]:
        return self._db.get(AssetTransaction, txn_id)

    def list_transactions(self, asset_id: str) -> list[AssetTransaction]:
        stmt = (
            select(AssetTransaction)
            .where(AssetTransaction.asset_id == asset_id)
            .order_by(AssetTransaction.created_at.desc())
        )
        return list(self._db.scalars(stmt).all())

    def create_transaction(self, txn: AssetTransaction) -> AssetTransaction:
        self._db.add(txn)
        self._db.flush()
        self._db.refresh(txn)
        return txn

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def create_audit(self, entry: AuditLog) -> AuditLog:
        self._db.add(entry)
        self._db.flush()
        return entry

    def list_audit(
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
