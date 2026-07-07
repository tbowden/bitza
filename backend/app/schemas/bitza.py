from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.bitza import BitzaKind, BitzaStatus, FuzzyState, RetiredReason, StockMode


# ---------------------------------------------------------------------------
# Bitza — create / update
# ---------------------------------------------------------------------------

class BitzaCreate(BaseModel):
    """
    Kind-conditional validation lives here, not in the service, since it's
    pure input-shape validation with no DB lookups involved:
      - kind=stock requires stock_mode; exact requires quantity (and
        forbids fuzzy_state); fuzzy requires fuzzy_state (and forbids
        quantity/low_stock_threshold).
      - kind in (fixed, mobile) forbids all stock_* fields entirely.

    responsible_team_id is REQUIRED — there is no inheritance/resolution
    at read time (see Bitza model docstring). The frontend is expected to
    pre-fill this from the parent's responsible_team_id when adding a
    child under an existing Bitza; the backend only validates presence
    and that the team exists.
    """

    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    kind: BitzaKind
    parent_id: Optional[str] = None
    responsible_team_id: str
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None

    # Acquisition — purchased_by_user_id defaults to the creating user if
    # omitted (see BitzaService.create_bitza).
    purchased_by_user_id: Optional[str] = None
    vendor: Optional[str] = Field(None, max_length=200)
    purchase_date: Optional[datetime] = None
    order_url: Optional[str] = None

    # kind = stock only
    stock_mode: Optional[StockMode] = None
    quantity: Optional[int] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    fuzzy_state: Optional[FuzzyState] = None

    @model_validator(mode="after")
    def _validate_kind_conditional_fields(self) -> "BitzaCreate":
        if self.kind != BitzaKind.stock:
            if any(
                v is not None
                for v in (self.stock_mode, self.quantity, self.low_stock_threshold, self.fuzzy_state)
            ):
                raise ValueError(
                    "stock_mode/quantity/low_stock_threshold/fuzzy_state may only be "
                    "set when kind='stock'"
                )
            return self

        # kind == stock
        if self.stock_mode is None:
            raise ValueError("stock_mode is required when kind='stock'")
        if self.stock_mode == StockMode.exact:
            if self.quantity is None:
                raise ValueError("quantity is required when stock_mode='exact'")
            if self.fuzzy_state is not None:
                raise ValueError("fuzzy_state must not be set when stock_mode='exact'")
        else:  # fuzzy
            if self.fuzzy_state is None:
                raise ValueError("fuzzy_state is required when stock_mode='fuzzy'")
            if self.quantity is not None or self.low_stock_threshold is not None:
                raise ValueError(
                    "quantity/low_stock_threshold must not be set when stock_mode='fuzzy'"
                )
        return self


class BitzaUpdate(BaseModel):
    """
    Ordinary, single-row edit — never cascades, regardless of kind. This
    includes responsible_team_id: a plain PATCH may reassign it, but only
    for this one row. Use POST /bitzas/{id}/reassign-team when you want an
    explicit cascade scope and a dedicated audit trail entry for the sweep.

    kind is intentionally NOT editable — converting a fixed location into
    a checkoutable tool (or vice versa) is a re-creation, not an update.

    quantity is intentionally NOT editable here — exact stock changes must
    go through POST /bitzas/{id}/stock-adjustments so the log stays
    complete. fuzzy_state IS editable here directly, matching "fuzzy =
    approximate, no expectation of perfect accuracy, no log needed".
    """

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[str] = None
    responsible_team_id: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None

    vendor: Optional[str] = Field(None, max_length=200)
    purchase_date: Optional[datetime] = None
    order_url: Optional[str] = None

    low_stock_threshold: Optional[int] = Field(None, ge=0)
    fuzzy_state: Optional[FuzzyState] = None


# ---------------------------------------------------------------------------
# Bitza — read
# ---------------------------------------------------------------------------

class BitzaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    kind: BitzaKind

    parent_id: Optional[str]
    parent_name: Optional[str] = None          # populated by service
    child_count: int = 0                        # populated by service

    responsible_team_id: str
    responsible_team_name: str = ""             # populated by service

    category_id: Optional[str]
    category_name: Optional[str] = None         # populated by service
    tags: Optional[list[str]]

    status: BitzaStatus
    retired_reason: Optional[RetiredReason]
    retired_note: Optional[str]
    retired_at: Optional[datetime]
    retired_by_user_id: Optional[str]
    retired_by_display_name: Optional[str] = None   # populated by service

    purchased_by_user_id: Optional[str]
    purchased_by_display_name: str = ""         # populated by service
    vendor: Optional[str]
    purchase_date: Optional[datetime]
    order_url: Optional[str]

    stock_mode: Optional[StockMode]
    quantity: Optional[int]
    low_stock_threshold: Optional[int]
    fuzzy_state: Optional[FuzzyState]

    # kind = mobile only — derived from the open Checkout row, if any.
    is_checked_out: bool = False                # populated by service
    current_holder_display_name: Optional[str] = None   # populated by service

    created_at: datetime
    updated_at: datetime


class BitzaListRead(BaseModel):
    """Compact form for list/browse views."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: BitzaKind
    parent_id: Optional[str]
    parent_name: Optional[str] = None
    responsible_team_name: str = ""
    category_name: Optional[str] = None
    status: BitzaStatus
    quantity: Optional[int]
    fuzzy_state: Optional[FuzzyState]
    is_checked_out: bool = False
    child_count: int = 0


# ---------------------------------------------------------------------------
# Retire / reactivate
# ---------------------------------------------------------------------------

class BitzaRetire(BaseModel):
    reason: RetiredReason
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Reassign team (with cascade)
# ---------------------------------------------------------------------------

class ReassignTeamRequest(BaseModel):
    """
    cascade_scope is REQUIRED — the backend never guesses a default. This
    is the one place team-responsibility changes can affect more than a
    single row, and it is always an explicit, separate action from an
    ordinary PATCH (see Bitza model + BitzaUpdate docstrings).

    none            — only this Bitza changes (equivalent to a plain
                      PATCH, but produces a dedicated audit trail entry).
    direct_children — this Bitza and its immediate children only.
    all_descendants — this Bitza and every descendant at any depth.

    Which scope makes sense depends on mobility, not enforced by the
    backend: a cupboard's reassign dialog might default its scope-picker
    to `none` (moving the cupboard between teams doesn't necessarily move
    the shelves' contents), while a toolbox's might default to
    `all_descendants` (the tools inside travel with it). That default is
    purely a frontend UX choice — the backend accepts any scope for any
    kind and never infers one.
    """

    team_id: str
    cascade_scope: str = Field(pattern="^(none|direct_children|all_descendants)$")


class ReassignTeamResponse(BaseModel):
    bitza_id: str
    team_id: str
    cascade_scope: str
    updated_count: int


# ---------------------------------------------------------------------------
# Checkout / checkin
# ---------------------------------------------------------------------------

class CheckoutCreate(BaseModel):
    """
    team_context is optional — if omitted, BitzaService pre-fills it from
    the holder's primary TeamMember (if they have one); either way it's a
    snapshot at checkout time, never a live link. holder is always the
    current authenticated user — there is no "check out on behalf of
    someone else".
    """
    team_context: Optional[str] = Field(None, max_length=150)
    note: Optional[str] = None


class CheckinRequest(BaseModel):
    note: Optional[str] = None


class CheckoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bitza_id: str
    holder_id: Optional[str]
    holder_display_name: str = ""   # populated by service
    team_context: Optional[str]
    checked_out_at: datetime
    checked_in_at: Optional[datetime]
    note: Optional[str]


# ---------------------------------------------------------------------------
# Stock adjustments
# ---------------------------------------------------------------------------

class StockAdjustmentCreate(BaseModel):
    delta: int = Field(..., description="Positive = stock in, negative = stock out")
    note: Optional[str] = None


class StockAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bitza_id: str
    delta: int
    quantity_after: int
    user_id: Optional[str]
    user_display_name: str = ""   # populated by service
    note: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class BitzaImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bitza_id: str
    is_primary: bool
    uploaded_by: Optional[str]
    uploaded_by_display_name: str = ""   # populated by service
    uploaded_at: datetime


class BitzaImageSetPrimary(BaseModel):
    is_primary: bool
