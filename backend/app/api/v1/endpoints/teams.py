from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, get_team_service
from app.models.user import User
from app.schemas.team import (
    TeamCreate,
    TeamListRead,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberSetPrimary,
    TeamRead,
    TeamUpdate,
)
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


# ---------------------------------------------------------------------------
# Team CRUD — any authenticated user may create/edit/delete
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[TeamListRead],
    summary="List teams",
)
def list_teams(
    user_id: Optional[str] = Query(
        None, description="If set, only teams this user belongs to"
    ),
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> list[TeamListRead]:
    """
    No privacy filtering — every team is visible to every authenticated
    user, by design (see bitza_project_context.md). ``user_id`` is a
    convenience filter for the frontend's checkout team_context picker,
    not an access-control boundary.
    """
    return svc.list_teams(user_id=user_id)


@router.post(
    "/",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a team",
)
def create_team(
    body: TeamCreate,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> TeamRead:
    """Any authenticated user may create a team — this covers both the
    club's dozen-team structure and a home user's one-off project team."""
    return svc.create_team(data=body)


@router.get("/{team_id}", response_model=TeamRead, summary="Get a team")
def get_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> TeamRead:
    return svc.get_team(team_id=team_id)


@router.patch("/{team_id}", response_model=TeamRead, summary="Rename/describe a team")
def update_team(
    team_id: str,
    body: TeamUpdate,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> TeamRead:
    return svc.update_team(team_id=team_id, data=body)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a team",
    responses={409: {"description": "Blocked — bitzas still reference this team"}},
)
def delete_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> None:
    """Blocked only if a Bitza still has this team as responsible_team_id —
    reassign those first. Not gated by role; any authenticated user may
    delete a team once it's unreferenced."""
    svc.delete_team(team_id=team_id)


# ---------------------------------------------------------------------------
# Membership — freely add/remove, including removing OTHERS. This is a
# deliberate trust decision (see project context doc): transient club
# membership means "can't remove others" would be actively unhelpful.
# ---------------------------------------------------------------------------

@router.get(
    "/{team_id}/members",
    response_model=list[TeamMemberRead],
    summary="List a team's members",
)
def list_members(
    team_id: str,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> list[TeamMemberRead]:
    return svc.list_members(team_id=team_id)


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to a team",
)
def add_member(
    team_id: str,
    body: TeamMemberCreate,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> TeamMemberRead:
    """Any authenticated user may add any other user to any team —
    including themselves, including onto a team they're not on. There is
    no invite/approval step."""
    return svc.add_member(team_id=team_id, data=body)


@router.patch(
    "/{team_id}/members/{user_id}",
    response_model=TeamMemberRead,
    summary="Set/unset a member's primary-team flag",
)
def set_primary_member(
    team_id: str,
    user_id: str,
    body: TeamMemberSetPrimary,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> TeamMemberRead:
    """
    is_primary carries no permission meaning — it only pre-fills the
    checkout team_context picker on the frontend. Setting True unsets any
    other primary this user has (same rotation pattern as refresh tokens).
    """
    return svc.set_primary(team_id=team_id, user_id=user_id, is_primary=body.is_primary)


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a team",
)
def remove_member(
    team_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    svc: TeamService = Depends(get_team_service),
) -> None:
    """Any authenticated user may remove any other user from any team —
    no self-only restriction. See project context doc for why."""
    svc.remove_member(team_id=team_id, user_id=user_id)
