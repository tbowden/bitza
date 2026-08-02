from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember


class ProjectRepository:
    """Data-access layer for projects and project_members. No business logic,
    no permission checks — see project context doc: any authenticated
    user may create/join/add/remove freely, enforced (or rather, not
    enforced) at the service layer."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Project reads
    # ------------------------------------------------------------------

    def get(self, project_id: str) -> Optional[Project]:
        return self._db.get(Project, project_id)

    def get_by_name(self, name: str) -> Optional[Project]:
        stmt = select(Project).where(Project.name == name)
        return self._db.scalar(stmt)

    def list_all(self) -> list[Project]:
        stmt = select(Project).order_by(Project.name)
        return list(self._db.scalars(stmt).all())

    def count_members(self, project_id: str) -> int:
        stmt = select(func.count()).select_from(ProjectMember).where(
            ProjectMember.project_id == project_id
        )
        return self._db.scalar(stmt) or 0

    # ------------------------------------------------------------------
    # Project writes
    # ------------------------------------------------------------------

    def create(self, project: Project) -> Project:
        self._db.add(project)
        self._db.flush()
        self._db.refresh(project)
        return project

    def update(self, project: Project) -> Project:
        self._db.flush()
        self._db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self._db.delete(project)
        self._db.flush()

    # ------------------------------------------------------------------
    # ProjectMember reads
    # ------------------------------------------------------------------

    def get_member(self, project_id: str, user_id: str) -> Optional[ProjectMember]:
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
        return self._db.scalar(stmt)

    def get_member_by_id(self, member_id: str) -> Optional[ProjectMember]:
        return self._db.get(ProjectMember, member_id)

    def list_members(self, project_id: str) -> list[ProjectMember]:
        stmt = (
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at)
        )
        return list(self._db.scalars(stmt).all())

    def list_projects_for_user(self, user_id: str) -> list[ProjectMember]:
        """Returns ProjectMember rows (not Project rows) so callers can see
        is_primary alongside the project."""
        stmt = (
            select(ProjectMember)
            .where(ProjectMember.user_id == user_id)
            .order_by(ProjectMember.created_at)
        )
        return list(self._db.scalars(stmt).all())

    def get_primary_membership(self, user_id: str) -> Optional[ProjectMember]:
        stmt = select(ProjectMember).where(
            ProjectMember.user_id == user_id, ProjectMember.is_primary.is_(True)
        )
        return self._db.scalar(stmt)

    # ------------------------------------------------------------------
    # ProjectMember writes
    # ------------------------------------------------------------------

    def create_member(self, member: ProjectMember) -> ProjectMember:
        self._db.add(member)
        self._db.flush()
        self._db.refresh(member)
        return member

    def update_member(self, member: ProjectMember) -> ProjectMember:
        self._db.flush()
        self._db.refresh(member)
        return member

    def delete_member(self, member: ProjectMember) -> None:
        self._db.delete(member)
        self._db.flush()

    def unset_all_primary_for_user(self, user_id: str) -> None:
        """Used before setting a new primary — same rotation pattern as
        refresh tokens: unset the old one(s), then the caller sets the
        new one, all inside one transaction."""
        stmt = select(ProjectMember).where(
            ProjectMember.user_id == user_id, ProjectMember.is_primary.is_(True)
        )
        for member in self._db.scalars(stmt).all():
            member.is_primary = False
        self._db.flush()
