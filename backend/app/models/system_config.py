from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemConfig(Base):
    """
    A deliberately tiny singleton table — exactly one row, id fixed at 1
    (enforced by both a CheckConstraint and application discipline: only
    BitzaService.create_root_bitza ever inserts into this table, and only
    once). Its sole purpose is to record which Bitza is the tree's single,
    permanent root, WITHOUT adding an `is_root`-style column to every row
    of the (potentially large) bitzas table.

    This mirrors the existing "only one superuser" pattern (see
    UserRepository.get_superuser / UserService.create_superuser) in
    spirit — a well-known singleton, looked up centrally, enforced at the
    service layer rather than a raw DB uniqueness trick — but Bitza has no
    existing column like User.role to piggyback on, so a dedicated pointer
    table is the equivalent for an entity with no natural "specialness"
    column of its own.

    The root bitza itself is created exactly once, via the CLI
    (`create-root`), never via the ordinary POST /bitzas/ endpoint —
    BitzaCreate.parent_id is a required field precisely so the ordinary
    create path can never produce a second root-level bitza. See
    BitzaService.create_root_bitza and the RootBitzaExistsError /
    RootBitzaProtectedError exceptions.

    root_bitza_id uses ondelete="RESTRICT" as a defence-in-depth measure:
    even a hypothetical direct DB delete of the root bitza row (bypassing
    the application entirely) would fail at the DB level while this
    pointer still references it.
    """

    __tablename__ = "system_config"
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_config_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    root_bitza_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bitzas.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utcnow)
