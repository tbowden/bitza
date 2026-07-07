from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.bitza import Bitza, BitzaKind, BitzaStatus


class BitzaRepository:
    """
    Data-access layer for the unified Bitza tree.

    Per AI_instructions.md's hierarchical-data rule: every method here is
    a single non-recursive query targeting direct parent-child rows only,
    with exactly one exception (get_ancestors, a WITH RECURSIVE CTE for
    breadcrumb display) — full subtree traversal for bulk operations
    (BitzaService.reassign_team's all_descendants scope) is done in the
    service layer via repeated calls to list_by_parent, not here.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, bitza_id: str) -> Optional[Bitza]:
        return self._db.get(Bitza, bitza_id)

    def list_by_parent(self, parent_id: str) -> list[Bitza]:
        """Direct children only — the frontend drives any further descent."""
        stmt = select(Bitza).where(Bitza.parent_id == parent_id).order_by(Bitza.name)
        return list(self._db.scalars(stmt).all())

    def list_roots(self) -> list[Bitza]:
        stmt = select(Bitza).where(Bitza.parent_id.is_(None)).order_by(Bitza.name)
        return list(self._db.scalars(stmt).all())

    def list_filtered(
        self,
        kind: Optional[BitzaKind] = None,
        status: Optional[BitzaStatus] = None,
        responsible_team_id: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> list[Bitza]:
        """Unscoped by parent — used for cross-cutting queries like "show
        me everything retired as broken" or "what does team X have"."""
        stmt = select(Bitza)
        if kind is not None:
            stmt = stmt.where(Bitza.kind == kind)
        if status is not None:
            stmt = stmt.where(Bitza.status == status)
        if responsible_team_id is not None:
            stmt = stmt.where(Bitza.responsible_team_id == responsible_team_id)
        if category_id is not None:
            stmt = stmt.where(Bitza.category_id == category_id)
        stmt = stmt.order_by(Bitza.name)
        return list(self._db.scalars(stmt).all())

    def count_children(self, bitza_id: str) -> int:
        stmt = select(func.count()).select_from(Bitza).where(Bitza.parent_id == bitza_id)
        return self._db.scalar(stmt) or 0

    def count_by_responsible_team(self, team_id: str) -> int:
        """Used by TeamService before allowing a Team delete — mirrors
        the DB-level ondelete='RESTRICT' but lets the service raise a
        clean ConflictError with a useful message instead of surfacing a
        raw IntegrityError."""
        stmt = select(func.count()).select_from(Bitza).where(
            Bitza.responsible_team_id == team_id
        )
        return self._db.scalar(stmt) or 0

    def get_ancestors(self, bitza_id: str) -> list[Bitza]:
        """
        Walks parent_id upward via a recursive CTE — the one place this
        repository uses WITH RECURSIVE, reserved per AI_instructions.md
        for genuine ancestor-path resolution (breadcrumbs, cycle checks).
        Returns ancestors ordered from immediate parent to the root;
        excludes bitza_id itself.
        """
        cte = (
            select(Bitza.id, Bitza.parent_id)
            .where(Bitza.id == bitza_id)
            .cte("ancestors", recursive=True)
        )
        parent = select(Bitza.id, Bitza.parent_id).join(
            cte, Bitza.id == cte.c.parent_id
        )
        cte = cte.union_all(parent)

        ids_stmt = select(cte.c.id).where(cte.c.id != bitza_id)
        ancestor_ids = [row[0] for row in self._db.execute(ids_stmt).all()]
        if not ancestor_ids:
            return []

        # Re-fetch full rows, preserving no particular order guarantee from
        # SQLite on the CTE — order client-side by walking parent_id chain.
        rows = {b.id: b for b in self._db.scalars(
            select(Bitza).where(Bitza.id.in_(ancestor_ids))
        ).all()}
        ordered: list[Bitza] = []
        current = self._db.get(Bitza, bitza_id)
        while current and current.parent_id and current.parent_id in rows:
            current = rows[current.parent_id]
            ordered.append(current)
        return ordered

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create(self, bitza: Bitza) -> Bitza:
        self._db.add(bitza)
        self._db.flush()
        self._db.refresh(bitza)
        return bitza

    def update(self, bitza: Bitza) -> Bitza:
        self._db.flush()
        self._db.refresh(bitza)
        return bitza

    def delete(self, bitza: Bitza) -> None:
        self._db.delete(bitza)
        self._db.flush()
