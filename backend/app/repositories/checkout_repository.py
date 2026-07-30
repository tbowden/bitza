from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bitza import Checkout


class CheckoutRepository:
    """Data-access layer for the checkouts table. 'Currently checked out'
    is always derived (checked_in_at IS NULL) — never a stored state."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_open_checkout(self, bitza_id: str) -> Optional[Checkout]:
        stmt = select(Checkout).where(
            Checkout.bitza_id == bitza_id, Checkout.checked_in_at.is_(None)
        )
        return self._db.scalar(stmt)

    def list_for_bitza(self, bitza_id: str) -> list[Checkout]:
        stmt = (
            select(Checkout)
            .where(Checkout.bitza_id == bitza_id)
            .order_by(Checkout.checked_out_at.desc())
        )
        return list(self._db.scalars(stmt).all())

    def list_open_for_holder(self, holder_id: str) -> list[Checkout]:
        """Every currently-open checkout held by one user, across the
        whole tree — powers the '/me' landing page. Unlike
        ``list_for_bitza``, this queries across bitza_id rather than
        scoping to one, since a user's checked-out items can live
        anywhere in the hierarchy."""
        stmt = (
            select(Checkout)
            .where(Checkout.holder_id == holder_id, Checkout.checked_in_at.is_(None))
            .order_by(Checkout.checked_out_at.desc())
        )
        return list(self._db.scalars(stmt).all())

    def create(self, checkout: Checkout) -> Checkout:
        self._db.add(checkout)
        self._db.flush()
        self._db.refresh(checkout)
        return checkout

    def update(self, checkout: Checkout) -> Checkout:
        self._db.flush()
        self._db.refresh(checkout)
        return checkout
