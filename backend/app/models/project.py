import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """
    The universal responsible/organisational entity.

    Same table serves both deployment shapes (see bitza_project_context.md):
    club use has ~a dozen projects with many members each; home use has one or
    a few projects, often with one member, occasionally shared for a joint
    project. Formerly called "Team" throughout the backend (Stage 5 renamed
    the frontend's display label to "Project"; Stage 6 brought the backend
    into line — see bitza_open_issues.md).

    "Workshop manager" is NOT a special role or flag anywhere in this app.
    It is just a Project named "Workshop" — being (assistant) workshop manager
    means having a ProjectMember row pointing at it, exactly like membership
    of any other project. A person can hold this alongside normal project
    membership (most workshop managers are also on a regular project) simply
    by having two ProjectMember rows.

    Projects carry NO permissions and NO privacy semantics. A project_id
    anywhere in this schema (see Bitza.responsible_project_id) is purely
    informational — "who to ask about this" — never an access-control
    gate. Any authenticated user may create a project, join one, add another
    user to one, or remove another user from one. Privacy was deliberately
    removed from this app's design entirely.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )

    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(Base):
    """
    User <-> Project membership. Plain many-to-many, no temporal history.

    A user may belong to zero, one, or many projects simultaneously — e.g. a
    student on "Aero" who also does a stint as workshop manager just gets
    a second row pointing at the "Workshop" project. There is no separate
    role/position entity, and no started_at/ended_at — "who was on what
    project when" was explicitly ruled out as a requirement. Leaving a project
    is a row deletion, full stop.

    is_primary: at most one True row per user, enforced in the service
    layer (same pattern as refresh-token rotation — setting a new primary
    unsets the old one in the same transaction). Purely a UI convenience
    to pre-select a default project_context when checking out a mobile Bitza.
    Carries no permission meaning whatsoever.
    """

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_project_members_user_project"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )

    project: Mapped["Project"] = relationship("Project", back_populates="members")
