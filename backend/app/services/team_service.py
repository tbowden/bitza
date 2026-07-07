import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UserNotFoundError
from app.models.team import Team, TeamMember
from app.models.user import User
from app.repositories.bitza_repository import BitzaRepository
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.team import (
    TeamCreate,
    TeamListRead,
    TeamMemberCreate,
    TeamMemberRead,
    TeamRead,
    TeamUpdate,
)


def _not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


class TeamService:
    """
    Business logic for Teams and TeamMembers.

    Deliberately has almost no permission checks. Per the project's
    "record reality, don't gate it" philosophy: any authenticated user
    may create a team, join one, add another user to one, or remove
    another user from one. There is a large trust element here by
    design — see bitza_project_context.md. The only floor anywhere in
    this service is the structural block on deleting a Team that Bitzas
    still depend on.

    "Workshop manager" is not modelled here at all — it is just a Team
    named "Workshop" like any other; TeamMember rows are how someone
    becomes (assistant) workshop manager, indistinguishable in the schema
    from any other membership.
    """

    def __init__(
        self,
        db: Session,
        team_repo: TeamRepository,
        user_repo: UserRepository,
        bitza_repo: BitzaRepository,
    ) -> None:
        self._db = db
        self._teams = team_repo
        self._users = user_repo
        self._bitzas = bitza_repo

    # ------------------------------------------------------------------
    # Team CRUD
    # ------------------------------------------------------------------

    def create_team(self, data: TeamCreate) -> TeamRead:
        if self._teams.get_by_name(data.name):
            raise ConflictError(f"A team named '{data.name}' already exists")
        team = Team(id=str(uuid.uuid4()), name=data.name, description=data.description)
        created = self._teams.create(team)
        self._db.commit()
        return self._enrich_team(created)

    def get_team(self, team_id: str) -> TeamRead:
        team = self._teams.get(team_id)
        if not team:
            raise _not_found("Team not found")
        return self._enrich_team(team)

    def list_teams(self, user_id: str | None = None) -> list[TeamListRead]:
        """If user_id is supplied, returns only teams that user belongs
        to (used by the frontend to populate a checkout team_context
        picker) — otherwise returns every team."""
        if user_id is not None:
            memberships = self._teams.list_teams_for_user(user_id)
            resolved = [self._teams.get(m.team_id) for m in memberships]
            teams = [t for t in resolved if t is not None]
        else:
            teams = self._teams.list_all()
        return [self._enrich_team_list(t) for t in teams]

    def update_team(self, team_id: str, data: TeamUpdate) -> TeamRead:
        team = self._teams.get(team_id)
        if not team:
            raise _not_found("Team not found")
        if data.name is not None:
            existing = self._teams.get_by_name(data.name)
            if existing and existing.id != team_id:
                raise ConflictError(f"A team named '{data.name}' already exists")
            team.name = data.name
        if data.description is not None:
            team.description = data.description
        updated = self._teams.update(team)
        self._db.commit()
        return self._enrich_team(updated)

    def delete_team(self, team_id: str) -> None:
        team = self._teams.get(team_id)
        if not team:
            raise _not_found("Team not found")
        bitza_count = self._bitzas.count_by_responsible_team(team_id)
        if bitza_count > 0:
            raise ConflictError(
                f"Cannot delete team — {bitza_count} bitza(s) still have it as their "
                "responsible team. Reassign them first."
            )
        self._teams.delete(team)
        self._db.commit()

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def add_member(self, team_id: str, data: TeamMemberCreate) -> TeamMemberRead:
        team = self._teams.get(team_id)
        if not team:
            raise _not_found("Team not found")
        user = self._users.get_by_id(data.user_id)
        if not user:
            raise UserNotFoundError("User not found")
        if self._teams.get_member(team_id, data.user_id):
            raise ConflictError("User is already a member of this team")

        if data.is_primary:
            self._teams.unset_all_primary_for_user(data.user_id)

        member = TeamMember(
            id=str(uuid.uuid4()),
            team_id=team_id,
            user_id=data.user_id,
            is_primary=data.is_primary,
        )
        created = self._teams.create_member(member)
        self._db.commit()
        return self._enrich_member(created)

    def list_members(self, team_id: str) -> list[TeamMemberRead]:
        team = self._teams.get(team_id)
        if not team:
            raise _not_found("Team not found")
        return [self._enrich_member(m) for m in self._teams.list_members(team_id)]

    def remove_member(self, team_id: str, user_id: str) -> None:
        member = self._teams.get_member(team_id, user_id)
        if not member:
            raise _not_found("This user is not a member of this team")
        self._teams.delete_member(member)
        self._db.commit()

    def set_primary(self, team_id: str, user_id: str, is_primary: bool) -> TeamMemberRead:
        member = self._teams.get_member(team_id, user_id)
        if not member:
            raise _not_found("This user is not a member of this team")
        if is_primary:
            self._teams.unset_all_primary_for_user(user_id)
        member.is_primary = is_primary
        updated = self._teams.update_member(member)
        self._db.commit()
        return self._enrich_member(updated)

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    def _enrich_team(self, team: Team) -> TeamRead:
        r = TeamRead.model_validate(team)
        r.member_count = self._teams.count_members(team.id)
        return r

    def _enrich_team_list(self, team: Team) -> TeamListRead:
        r = TeamListRead.model_validate(team)
        r.member_count = self._teams.count_members(team.id)
        return r

    def _user_display_name(self, user_id: str) -> str:
        user = self._users.get_by_id(user_id)
        return user.display_name if user else user_id

    def _enrich_member(self, member: TeamMember) -> TeamMemberRead:
        r = TeamMemberRead.model_validate(member)
        r.user_display_name = self._user_display_name(member.user_id)
        return r
