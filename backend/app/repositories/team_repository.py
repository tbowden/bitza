from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamMember


class TeamRepository:
    """Data-access layer for teams and team_members. No business logic,
    no permission checks — see project context doc: any authenticated
    user may create/join/add/remove freely, enforced (or rather, not
    enforced) at the service layer."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Team reads
    # ------------------------------------------------------------------

    def get(self, team_id: str) -> Optional[Team]:
        return self._db.get(Team, team_id)

    def get_by_name(self, name: str) -> Optional[Team]:
        stmt = select(Team).where(Team.name == name)
        return self._db.scalar(stmt)

    def list_all(self) -> list[Team]:
        stmt = select(Team).order_by(Team.name)
        return list(self._db.scalars(stmt).all())

    def count_members(self, team_id: str) -> int:
        stmt = select(func.count()).select_from(TeamMember).where(
            TeamMember.team_id == team_id
        )
        return self._db.scalar(stmt) or 0

    # ------------------------------------------------------------------
    # Team writes
    # ------------------------------------------------------------------

    def create(self, team: Team) -> Team:
        self._db.add(team)
        self._db.flush()
        self._db.refresh(team)
        return team

    def update(self, team: Team) -> Team:
        self._db.flush()
        self._db.refresh(team)
        return team

    def delete(self, team: Team) -> None:
        self._db.delete(team)
        self._db.flush()

    # ------------------------------------------------------------------
    # TeamMember reads
    # ------------------------------------------------------------------

    def get_member(self, team_id: str, user_id: str) -> Optional[TeamMember]:
        stmt = select(TeamMember).where(
            TeamMember.team_id == team_id, TeamMember.user_id == user_id
        )
        return self._db.scalar(stmt)

    def get_member_by_id(self, member_id: str) -> Optional[TeamMember]:
        return self._db.get(TeamMember, member_id)

    def list_members(self, team_id: str) -> list[TeamMember]:
        stmt = (
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.created_at)
        )
        return list(self._db.scalars(stmt).all())

    def list_teams_for_user(self, user_id: str) -> list[TeamMember]:
        """Returns TeamMember rows (not Team rows) so callers can see
        is_primary alongside the team."""
        stmt = (
            select(TeamMember)
            .where(TeamMember.user_id == user_id)
            .order_by(TeamMember.created_at)
        )
        return list(self._db.scalars(stmt).all())

    def get_primary_membership(self, user_id: str) -> Optional[TeamMember]:
        stmt = select(TeamMember).where(
            TeamMember.user_id == user_id, TeamMember.is_primary.is_(True)
        )
        return self._db.scalar(stmt)

    # ------------------------------------------------------------------
    # TeamMember writes
    # ------------------------------------------------------------------

    def create_member(self, member: TeamMember) -> TeamMember:
        self._db.add(member)
        self._db.flush()
        self._db.refresh(member)
        return member

    def update_member(self, member: TeamMember) -> TeamMember:
        self._db.flush()
        self._db.refresh(member)
        return member

    def delete_member(self, member: TeamMember) -> None:
        self._db.delete(member)
        self._db.flush()

    def unset_all_primary_for_user(self, user_id: str) -> None:
        """Used before setting a new primary — same rotation pattern as
        refresh tokens: unset the old one(s), then the caller sets the
        new one, all inside one transaction."""
        stmt = select(TeamMember).where(
            TeamMember.user_id == user_id, TeamMember.is_primary.is_(True)
        )
        for member in self._db.scalars(stmt).all():
            member.is_primary = False
        self._db.flush()
