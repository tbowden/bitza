from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bitza import StockLog


class StockLogRepository:
    """Data-access layer for the stock_logs table — structurally the same
    role the old AssetTransaction repository played."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_bitza(self, bitza_id: str) -> list[StockLog]:
        stmt = (
            select(StockLog)
            .where(StockLog.bitza_id == bitza_id)
            .order_by(StockLog.created_at.desc())
        )
        return list(self._db.scalars(stmt).all())

    def create(self, log: StockLog) -> StockLog:
        self._db.add(log)
        self._db.flush()
        self._db.refresh(log)
        return log
