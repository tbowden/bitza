from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Category


class CategoryRepository:
    """Data-access layer for the categories table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, category_id: str) -> Optional[Category]:
        return self._db.get(Category, category_id)

    def get_by_name(self, name: str) -> Optional[Category]:
        stmt = select(Category).where(Category.name == name)
        return self._db.scalar(stmt)

    def list_all(self) -> list[Category]:
        stmt = select(Category).order_by(Category.name)
        return list(self._db.scalars(stmt).all())

    def count_assets(self, category_id: str) -> int:
        stmt = select(func.count()).select_from(Asset).where(
            Asset.category_id == category_id
        )
        return self._db.scalar(stmt) or 0

    def create(self, category: Category) -> Category:
        self._db.add(category)
        self._db.flush()
        self._db.refresh(category)
        return category

    def update(self, category: Category) -> Category:
        self._db.flush()
        self._db.refresh(category)
        return category

    def delete(self, category: Category) -> None:
        self._db.delete(category)
        self._db.flush()
