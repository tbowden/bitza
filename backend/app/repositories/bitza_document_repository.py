from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bitza import BitzaDocument


class BitzaDocumentRepository:
    """Data-access layer for the bitza_documents table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, document_id: str) -> Optional[BitzaDocument]:
        return self._db.get(BitzaDocument, document_id)

    def list_for_bitza(self, bitza_id: str) -> list[BitzaDocument]:
        stmt = (
            select(BitzaDocument)
            .where(BitzaDocument.bitza_id == bitza_id)
            .order_by(BitzaDocument.uploaded_at, BitzaDocument.id)
        )
        return list(self._db.scalars(stmt).all())

    def create(self, document: BitzaDocument) -> BitzaDocument:
        self._db.add(document)
        self._db.flush()
        self._db.refresh(document)
        return document

    def update(self, document: BitzaDocument) -> BitzaDocument:
        self._db.flush()
        self._db.refresh(document)
        return document

    def delete(self, document: BitzaDocument) -> None:
        self._db.delete(document)
        self._db.flush()
