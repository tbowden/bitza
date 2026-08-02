from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, get_project_service
from app.models.user import User
from app.schemas.project import (
    MyProjectMembershipRead,
    ProjectCreate,
    ProjectListRead,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectMemberSetPrimary,
    ProjectRead,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Project CRUD — any authenticated user may create/edit/delete
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[ProjectListRead],
    summary="List projects",
)
def list_projects(
    user_id: Optional[str] = Query(
        None, description="If set, only projects this user belongs to"
    ),
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> list[ProjectListRead]:
    """
    No privacy filtering — every project is visible to every authenticated
    user, by design (see bitza_project_context.md). ``user_id`` is a
    convenience filter for the frontend's checkout project_context picker,
    not an access-control boundary.
    """
    return svc.list_projects(user_id=user_id)


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    """Any authenticated user may create a project — this covers both the
    club's dozen-project structure and a home user's one-off project."""
    return svc.create_project(data=body)


# Registered before GET /{project_id} — a static path segment must come
# before a path-parameter route matching the same position, or FastAPI
# would treat "mine" as a project_id here and 404 in get_project instead (same
# reasoning as GET /users/directory vs GET /users/{user_id}).
@router.get(
    "/mine",
    response_model=list[MyProjectMembershipRead],
    summary="Projects you're on, with your primary-project flag",
)
def list_my_memberships(
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> list[MyProjectMembershipRead]:
    """Powers the '/me' landing page. Unlike GET /projects/?user_id=, which
    returns full ProjectListRead rows (id/name/member_count) for any user,
    this is always scoped to the caller and includes is_primary."""
    return svc.list_my_memberships(user_id=current_user.id)


@router.get("/{project_id}", response_model=ProjectRead, summary="Get a project")
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return svc.get_project(project_id=project_id)


@router.patch("/{project_id}", response_model=ProjectRead, summary="Rename/describe a project")
def update_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return svc.update_project(project_id=project_id, data=body)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    responses={409: {"description": "Blocked — bitzas still reference this project"}},
)
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> None:
    """Blocked only if a Bitza still has this project as responsible_project_id —
    reassign those first. Not gated by role; any authenticated user may
    delete a project once it's unreferenced."""
    svc.delete_project(project_id=project_id)


# ---------------------------------------------------------------------------
# Membership — freely add/remove, including removing OTHERS. This is a
# deliberate trust decision (see project context doc): transient club
# membership means "can't remove others" would be actively unhelpful.
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberRead],
    summary="List a project's members",
)
def list_members(
    project_id: str,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> list[ProjectMemberRead]:
    return svc.list_members(project_id=project_id)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to a project",
)
def add_member(
    project_id: str,
    body: ProjectMemberCreate,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectMemberRead:
    """Any authenticated user may add any other user to any project —
    including themselves, including onto a project they're not on. There is
    no invite/approval step."""
    return svc.add_member(project_id=project_id, data=body)


@router.patch(
    "/{project_id}/members/{user_id}",
    response_model=ProjectMemberRead,
    summary="Set/unset a member's primary-project flag",
)
def set_primary_member(
    project_id: str,
    user_id: str,
    body: ProjectMemberSetPrimary,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectMemberRead:
    """
    is_primary carries no permission meaning — it only pre-fills the
    checkout project_context picker on the frontend. Setting True unsets any
    other primary this user has (same rotation pattern as refresh tokens).
    """
    return svc.set_primary(project_id=project_id, user_id=user_id, is_primary=body.is_primary)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a project",
)
def remove_member(
    project_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> None:
    """Any authenticated user may remove any other user from any project —
    no self-only restriction. See project context doc for why."""
    svc.remove_member(project_id=project_id, user_id=user_id)
