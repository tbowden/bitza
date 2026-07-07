import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Team(Base):
    """
    The universal responsible/organisational entity.

    Same table serves both deployment shapes (see bitza_project_context.md):
    club use has ~a dozen teams with many members each; home use has one or
    a few teams, often with one member, occasionally shared for a joint
    project. "Team" vs "Project" is a frontend display-label choice only —
    nothing in the schema or API encodes it.

    "Workshop manager" is NOT a special role or flag anywhere in this app.
    It is just a Team named "Workshop" — being (assistant) workshop manager
    means having a TeamMember row pointing at it, exactly like membership
    of any other team. A person can hold this alongside normal team
    membership (most workshop managers are also on a regular team) simply
    by having two TeamMember rows.

    Teams carry NO permissions and NO privacy semantics. A team_id
    anywhere in this schema (see Bitza.responsible_team_id) is purely
    informational — "who to ask about this" — never an access-control
    gate. Any authenticated user may create a team, join one, add another
    user to one, or remove another user from one. Privacy was deliberately
    removed from this app's design entirely.
    """

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )

    members: Mapped[list["TeamMember"]] = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    """
    User <-> Team membership. Plain many-to-many, no temporal history.

    A user may belong to zero, one, or many teams simultaneously — e.g. a
    student on "Aero" who also does a stint as workshop manager just gets
    a second row pointing at the "Workshop" team. There is no separate
    role/position entity, and no started_at/ended_at — "who was on what
    team when" was explicitly ruled out as a requirement. Leaving a team
    is a row deletion, full stop.

    is_primary: at most one True row per user, enforced in the service
    layer (same pattern as refresh-token rotation — setting a new primary
    unsets the old one in the same transaction). Purely a UI convenience
    to pre-select a default team_context when checking out a mobile Bitza.
    Carries no permission meaning whatsoever.
    """

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_team_members_user_team"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )

    team: Mapped["Team"] = relationship("Team", back_populates="members")
