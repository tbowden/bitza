import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UserNotFoundError
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.repositories.bitza_repository import BitzaRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.schemas.project import (
    MyProjectMembershipRead,
    ProjectCreate,
    ProjectListRead,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    ProjectUpdate,
)


def _not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


class ProjectService:
    """
    Business logic for Projects and ProjectMembers.

    Deliberately has almost no permission checks. Per the project's
    "record reality, don't gate it" philosophy: any authenticated user
    may create a project, join one, add another user to one, or remove
    another user from one. There is a large trust element here by
    design — see bitza_project_context.md. The only floor anywhere in
    this service is the structural block on deleting a Project that Bitzas
    still depend on.

    "Workshop manager" is not modelled here at all — it is just a Project
    named "Workshop" like any other; ProjectMember rows are how someone
    becomes (assistant) workshop manager, indistinguishable in the schema
    from any other membership.
    """

    def __init__(
        self,
        db: Session,
        project_repo: ProjectRepository,
        user_repo: UserRepository,
        bitza_repo: BitzaRepository,
    ) -> None:
        self._db = db
        self._projects = project_repo
        self._users = user_repo
        self._bitzas = bitza_repo

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def create_project(self, data: ProjectCreate) -> ProjectRead:
        if self._projects.get_by_name(data.name):
            raise ConflictError(f"A project named '{data.name}' already exists")
        project = Project(id=str(uuid.uuid4()), name=data.name, description=data.description)
        created = self._projects.create(project)
        self._db.commit()
        return self._enrich_project(created)

    def get_project(self, project_id: str) -> ProjectRead:
        project = self._projects.get(project_id)
        if not project:
            raise _not_found("Project not found")
        return self._enrich_project(project)

    def list_projects(self, user_id: str | None = None) -> list[ProjectListRead]:
        """If user_id is supplied, returns only projects that user belongs
        to (used by the frontend to populate a checkout project_context
        picker) — otherwise returns every project."""
        if user_id is not None:
            memberships = self._projects.list_projects_for_user(user_id)
            resolved = [self._projects.get(m.project_id) for m in memberships]
            projects = [t for t in resolved if t is not None]
        else:
            projects = self._projects.list_all()
        return [self._enrich_project_list(t) for t in projects]

    def update_project(self, project_id: str, data: ProjectUpdate) -> ProjectRead:
        project = self._projects.get(project_id)
        if not project:
            raise _not_found("Project not found")
        if data.name is not None:
            existing = self._projects.get_by_name(data.name)
            if existing and existing.id != project_id:
                raise ConflictError(f"A project named '{data.name}' already exists")
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        updated = self._projects.update(project)
        self._db.commit()
        return self._enrich_project(updated)

    def delete_project(self, project_id: str) -> None:
        project = self._projects.get(project_id)
        if not project:
            raise _not_found("Project not found")
        bitza_count = self._bitzas.count_by_responsible_project(project_id)
        if bitza_count > 0:
            raise ConflictError(
                f"Cannot delete project — {bitza_count} bitza(s) still have it as their "
                "responsible project. Reassign them first."
            )
        self._projects.delete(project)
        self._db.commit()

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def add_member(self, project_id: str, data: ProjectMemberCreate) -> ProjectMemberRead:
        project = self._projects.get(project_id)
        if not project:
            raise _not_found("Project not found")
        user = self._users.get_by_id(data.user_id)
        if not user:
            raise UserNotFoundError("User not found")
        if self._projects.get_member(project_id, data.user_id):
            raise ConflictError("User is already a member of this project")

        if data.is_primary:
            self._projects.unset_all_primary_for_user(data.user_id)

        member = ProjectMember(
            id=str(uuid.uuid4()),
            project_id=project_id,
            user_id=data.user_id,
            is_primary=data.is_primary,
        )
        created = self._projects.create_member(member)
        self._db.commit()
        return self._enrich_member(created)

    def list_members(self, project_id: str) -> list[ProjectMemberRead]:
        project = self._projects.get(project_id)
        if not project:
            raise _not_found("Project not found")
        return [self._enrich_member(m) for m in self._projects.list_members(project_id)]

    def remove_member(self, project_id: str, user_id: str) -> None:
        member = self._projects.get_member(project_id, user_id)
        if not member:
            raise _not_found("This user is not a member of this project")
        self._projects.delete_member(member)
        self._db.commit()

    def list_my_memberships(self, user_id: str) -> list[MyProjectMembershipRead]:
        """Powers the '/me' landing page's "projects you're on" section —
        project name plus is_primary in one call, rather than making the
        frontend cross-reference GET /projects/?user_id= against a separate
        primary lookup."""
        memberships = self._projects.list_projects_for_user(user_id)
        result: list[MyProjectMembershipRead] = []
        for m in memberships:
            project = self._projects.get(m.project_id)
            if project:
                result.append(
                    MyProjectMembershipRead(
                        project_id=project.id, project_name=project.name, is_primary=m.is_primary
                    )
                )
        return result

    def set_primary(self, project_id: str, user_id: str, is_primary: bool) -> ProjectMemberRead:
        member = self._projects.get_member(project_id, user_id)
        if not member:
            raise _not_found("This user is not a member of this project")
        if is_primary:
            self._projects.unset_all_primary_for_user(user_id)
        member.is_primary = is_primary
        updated = self._projects.update_member(member)
        self._db.commit()
        return self._enrich_member(updated)

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    def _enrich_project(self, project: Project) -> ProjectRead:
        r = ProjectRead.model_validate(project)
        r.member_count = self._projects.count_members(project.id)
        return r

    def _enrich_project_list(self, project: Project) -> ProjectListRead:
        r = ProjectListRead.model_validate(project)
        r.member_count = self._projects.count_members(project.id)
        return r

    def _user_display_name(self, user_id: str) -> str:
        user = self._users.get_by_id(user_id)
        return user.display_name if user else user_id

    def _enrich_member(self, member: ProjectMember) -> ProjectMemberRead:
        r = ProjectMemberRead.model_validate(member)
        r.user_display_name = self._user_display_name(member.user_id)
        return r
