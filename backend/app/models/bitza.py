import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BitzaKind(str, enum.Enum):
    """
    Replaces the old separate StorageLocation / LocationDetail / Asset
    tables — see bitza_project_context.md for the full design history.
    "Is there any real difference between a storage location and a tool?
    Apart from the ability to check it out?" — no. The only meaningful
    axis is this discriminator.

    fixed  — a room, shelf, pegboard. Never checked out; purely a
             container in the tree.
    mobile — a tool, a toolbox, a multimeter. Checkoutable (see Checkout).
             Its "home" is wherever parent_id currently points — moving it
             is a single-row update; nothing cascades to its contents
             unless a reassign-team sweep explicitly says so.
    stock  — a quantity-based consumable (resistors, screws). Tracked via
             quantity/fuzzy_state + StockLog. Never checked out.
    """

    fixed = "fixed"
    mobile = "mobile"
    stock = "stock"


class BitzaStatus(str, enum.Enum):
    """
    Freely settable by ANY authenticated user, no approval, no gate, fully
    reversible — this is a status flag, not a workflow. It exists so that
    "lost" / "broken" / "can't be reordered" / "replaced by a substitute"
    can be recorded without hard-deleting the record. Hard delete is
    reserved for admin/superuser, for records that genuinely should never
    have existed (duplicates, test entries) — never for "this got lost".
    """

    active = "active"
    retired = "retired"


class RetiredReason(str, enum.Enum):
    lost = "lost"
    broken = "broken"
    discontinued = "discontinued"   # can't be reordered
    superseded = "superseded"       # replaced by a substitute
    other = "other"


class StockMode(str, enum.Enum):
    exact = "exact"
    fuzzy = "fuzzy"


class FuzzyState(str, enum.Enum):
    plentiful = "plentiful"
    low = "low"
    empty = "empty"


class Bitza(Base):
    """
    The unified location/container/item entity — replaces StorageLocation,
    LocationDetail, and Asset with one self-referential tree.

    Hierarchy: parent_id is a nullable self-FK. NULL = a root ("Workshop",
    "Garage"). Arbitrary depth, no distinct "top level" type. Per
    AI_instructions.md, reads target direct parent-child rows only
    (WHERE parent_id = ?) — full subtree traversal for DISPLAY is a
    frontend concern, driven by repeated direct-children requests.

    The one deliberate exception is on the WRITE side:
    BitzaService.reassign_team's all_descendants cascade scope. That is
    the one place this app walks a full subtree server-side, and it is a
    distinct, explicit action (not an implicit side-effect of an ordinary
    edit) — see the docstring on that method and the project context doc.

    responsible_team_id is REQUIRED at creation and is a SNAPSHOT, not a
    live inherited link — it does not automatically follow a parent's
    team if the parent's responsibility later changes. It is purely
    informational ("who to ask"), never a permission gate; anyone may
    create, edit, move, checkout, or adjust stock on any Bitza regardless
    of responsible_team_id. Only hard delete is restricted (admin/
    superuser), and only because the record disappears entirely rather
    than being flagged retired.

    Kind-specific columns (stock_mode/quantity/... ) are plain nullable
    columns with application-level discipline rather than SQLAlchemy
    single-table-inheritance — simpler and more transparent at this scale.
    """

    __tablename__ = "bitzas"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[BitzaKind] = mapped_column(Enum(BitzaKind, name="bitzakind"), nullable=False)

    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("bitzas.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # RESTRICT, not SET NULL: responsible_team_id is mandatory, so a Team
    # can never be silently orphaned out from under a Bitza — deleting a
    # Team that anything is still responsible-for fails at the DB level.
    responsible_team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # --- Status / retirement ---
    status: Mapped[BitzaStatus] = mapped_column(
        Enum(BitzaStatus, name="bitzastatus"), nullable=False, default=BitzaStatus.active
    )
    retired_reason: Mapped[RetiredReason | None] = mapped_column(
        Enum(RetiredReason, name="retiredreason"), nullable=True
    )
    retired_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    retired_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Acquisition / provenance ---
    # purchased_by_user_id doubles as "added by" — the project decided
    # these never need to be tracked separately.
    purchased_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purchase_date: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    order_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- kind = stock only ---
    stock_mode: Mapped[StockMode | None] = mapped_column(
        Enum(StockMode, name="stockmode"), nullable=True
    )
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuzzy_state: Mapped[FuzzyState | None] = mapped_column(
        Enum(FuzzyState, name="fuzzystate"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    parent: Mapped["Bitza | None"] = relationship(
        "Bitza", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Bitza"]] = relationship("Bitza", back_populates="parent")
    images: Mapped[list["BitzaImage"]] = relationship(
        "BitzaImage", back_populates="bitza", cascade="all, delete-orphan"
    )
    checkouts: Mapped[list["Checkout"]] = relationship(
        "Checkout", back_populates="bitza", cascade="all, delete-orphan",
        order_by="Checkout.checked_out_at",
    )
    stock_logs: Mapped[list["StockLog"]] = relationship(
        "StockLog", back_populates="bitza", cascade="all, delete-orphan",
        order_by="StockLog.created_at",
    )


class BitzaImage(Base):
    """
    Multiple images per Bitza. Exactly one may be is_primary=True —
    enforced in the service layer the same way refresh-token rotation
    enforces "one active token": setting a new primary unsets the old one
    in the same transaction.
    """

    __tablename__ = "bitza_images"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bitza_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utcnow)

    bitza: Mapped["Bitza"] = relationship("Bitza", back_populates="images")


class Checkout(Base):
    """
    Custody log for kind=mobile Bitzas. "Currently checked out" is always
    DERIVED — a row with checked_in_at IS NULL — never a separately
    maintained state field on Bitza itself.

    Deliberately minimal: no due dates, no approvals — item-level
    workflows were explicitly ruled out of scope (only the account/role
    permission system from Phase 1 stayed as originally built).

    team_context is a free-text SNAPSHOT, not a live FK to Team. Pre-filled
    from the holder's primary TeamMember at checkout time if they have
    one, freely overridable (e.g. helping out a team you're not on). Being
    a snapshot means it can never be silently corrupted by the holder's
    team memberships changing later.
    """

    __tablename__ = "checkouts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bitza_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_context: Mapped[str | None] = mapped_column(String(150), nullable=True)
    checked_out_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utcnow)
    checked_in_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    bitza: Mapped["Bitza"] = relationship("Bitza", back_populates="checkouts")


class StockLog(Base):
    """
    Adjustment log for kind=stock Bitzas (stock_mode=exact only —
    fuzzy_state is edited directly with no log, consistent with "fuzzy =
    approximate, no expectation of perfect accuracy"). Structurally
    identical to the old AssetTransaction it replaces: this is exactly
    the "lightweight who/when log" the project settled on — enough to
    answer "who used the last one" without any reconciliation/valuation
    machinery.
    """

    __tablename__ = "stock_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bitza_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utcnow)

    bitza: Mapped["Bitza"] = relationship("Bitza", back_populates="stock_logs")
