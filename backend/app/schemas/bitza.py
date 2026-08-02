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

    responsible_project_id is REQUIRED — there is no inheritance/resolution
    at read time (see Bitza model docstring). The frontend is expected to
    pre-fill this from the parent's responsible_project_id when adding a
    child under an existing Bitza; the backend only validates presence
    and that the project exists.

    parent_id is likewise REQUIRED (not Optional) — there is exactly one
    root bitza in the whole tree, created once via the CLI's create-root
    command and never through this endpoint. See
    BitzaService.create_root_bitza and RootBitzaExistsError. A request
    with no parent_id is rejected by Pydantic itself before it ever
    reaches the service layer.
    """

    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    kind: BitzaKind
    parent_id: str
    responsible_project_id: str
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
    includes responsible_project_id: a plain PATCH may reassign it, but only
    for this one row. Use POST /bitzas/{id}/reassign-project when you want an
    explicit cascade scope and a dedicated audit trail entry for the sweep.

    kind IS conditionally editable (see BitzaService.update_bitza for the
    history guards — this schema only validates input shape, not
    persisted history, since that needs a DB lookup):
      - Moving to kind='stock' needs the same stock_mode/quantity/
        fuzzy_state shape BitzaCreate requires.
      - Moving away from kind='stock' forbids all stock_* fields (they're
        nulled out server-side instead).
      - stock_mode may also be changed on an already-stock bitza without
        touching kind — same nested shape rules apply, since it's the
        same kind of transition (exact -> fuzzy or back).

    quantity is otherwise NOT editable here — exact stock changes must
    go through POST /bitzas/{id}/stock-adjustments so the log stays
    complete. It's only accepted here as the *starting* value for a
    transition into stock_mode='exact' (see the validator below); the
    service layer separately rejects it if stock_mode isn't actually
    changing. fuzzy_state IS editable here directly when no transition
    is happening, matching "fuzzy = approximate, no expectation of
    perfect accuracy, no log needed".
    """

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    kind: Optional[BitzaKind] = None
    parent_id: Optional[str] = None
    responsible_project_id: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None

    vendor: Optional[str] = Field(None, max_length=200)
    purchase_date: Optional[datetime] = None
    order_url: Optional[str] = None

    stock_mode: Optional[StockMode] = None
    quantity: Optional[int] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    fuzzy_state: Optional[FuzzyState] = None

    @model_validator(mode="after")
    def _validate_kind_transition_shape(self) -> "BitzaUpdate":
        # No kind/stock_mode change requested — existing standalone
        # fuzzy_state/low_stock_threshold editing is untouched by this
        # validator; the service layer still checks those against the
        # bitza's persisted kind/stock_mode. quantity, however, is only
        # ever valid here as a transition's starting value.
        if self.kind is None and self.stock_mode is None:
            if self.quantity is not None:
                raise ValueError(
                    "quantity may only be set here as the starting value when "
                    "moving to stock_mode='exact' — ongoing exact-mode quantity "
                    "changes must go through POST .../stock-adjustments"
                )
            return self

        # kind explicitly moving to something other than 'stock'.
        if self.kind is not None and self.kind != BitzaKind.stock:
            if any(
                v is not None
                for v in (self.stock_mode, self.quantity, self.low_stock_threshold, self.fuzzy_state)
            ):
                raise ValueError(
                    "stock_mode/quantity/low_stock_threshold/fuzzy_state may only be "
                    "set when kind='stock'"
                )
            return self

        # Either kind is becoming/staying 'stock', or stock_mode is
        # changing on an already-stock bitza (kind omitted — the
        # service layer confirms the bitza really is kind='stock'
        # before allowing a bare stock_mode change).
        if self.stock_mode is None:
            raise ValueError("stock_mode is required when changing kind to 'stock'")
        if self.stock_mode == StockMode.exact:
            if self.quantity is None:
                raise ValueError(
                    "quantity is required (as the starting value) when moving to "
                    "stock_mode='exact'"
                )
            if self.fuzzy_state is not None:
                raise ValueError("fuzzy_state must not be set when stock_mode='exact'")
        else:  # fuzzy
            if self.fuzzy_state is None:
                raise ValueError(
                    "fuzzy_state is required when moving to stock_mode='fuzzy'"
                )
            if self.quantity is not None or self.low_stock_threshold is not None:
                raise ValueError(
                    "quantity/low_stock_threshold must not be set when stock_mode='fuzzy'"
                )
        return self


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
    is_root: bool = False                        # populated by service — see SystemConfig

    responsible_project_id: str
    responsible_project_name: str = ""             # populated by service

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
    responsible_project_name: str = ""
    category_name: Optional[str] = None
    status: BitzaStatus
    quantity: Optional[int]
    fuzzy_state: Optional[FuzzyState]
    is_checked_out: bool = False
    child_count: int = 0
    is_root: bool = False


class BitzaAncestorRead(BaseModel):
    """
    Minimal shape for GET /bitzas/{id}/ancestors — just enough to link
    and label a breadcrumb, deliberately lighter than BitzaListRead
    (no project/category lookups per ancestor). Ordered nearest parent
    first, root last — the same order BitzaRepository.get_ancestors()
    already computes; reversing a handful of items client-side for
    root-first breadcrumb display is cheaper than baking one specific
    consumer's preferred order into a general-purpose endpoint.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


# ---------------------------------------------------------------------------
# Retire / reactivate
# ---------------------------------------------------------------------------

class BitzaRetire(BaseModel):
    reason: RetiredReason
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Reassign project (with cascade)
# ---------------------------------------------------------------------------

class ReassignProjectRequest(BaseModel):
    """
    cascade_scope is REQUIRED — the backend never guesses a default. This
    is the one place project-responsibility changes can affect more than a
    single row, and it is always an explicit, separate action from an
    ordinary PATCH (see Bitza model + BitzaUpdate docstrings).

    none            — only this Bitza changes (equivalent to a plain
                      PATCH, but produces a dedicated audit trail entry).
    direct_children — this Bitza and its immediate children only.
    all_descendants — this Bitza and every descendant at any depth.

    Which scope makes sense depends on mobility, not enforced by the
    backend: a cupboard's reassign dialog might default its scope-picker
    to `none` (moving the cupboard between projects doesn't necessarily move
    the shelves' contents), while a toolbox's might default to
    `all_descendants` (the tools inside travel with it). That default is
    purely a frontend UX choice — the backend accepts any scope for any
    kind and never infers one.
    """

    project_id: str
    cascade_scope: str = Field(pattern="^(none|direct_children|all_descendants)$")


class ReassignProjectResponse(BaseModel):
    bitza_id: str
    project_id: str
    cascade_scope: str
    updated_count: int


# ---------------------------------------------------------------------------
# Checkout / checkin
# ---------------------------------------------------------------------------

class CheckoutCreate(BaseModel):
    """
    project_context is optional — if omitted, BitzaService pre-fills it from
    the holder's primary ProjectMember (if they have one); either way it's a
    snapshot at checkout time, never a live link. holder is always the
    current authenticated user — there is no "check out on behalf of
    someone else".
    """
    project_context: Optional[str] = Field(None, max_length=150)
    note: Optional[str] = None


class CheckinRequest(BaseModel):
    note: Optional[str] = None


class CheckoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bitza_id: str
    holder_id: Optional[str]
    holder_display_name: str = ""   # populated by service
    project_context: Optional[str]
    checked_out_at: datetime
    checked_in_at: Optional[datetime]
    note: Optional[str]


class MyCheckoutRead(BaseModel):
    """One row of the current user's open checkouts, for the '/me'
    landing page. Not built via ``model_validate`` from the Checkout ORM
    object (unlike CheckoutRead) since bitza_name/bitza_kind live on the
    related Bitza, not the Checkout row itself — the service assembles
    this directly."""

    id: str
    bitza_id: str
    bitza_name: str
    bitza_kind: Optional[BitzaKind] = None   # None only if the bitza row is gone
    project_context: Optional[str]
    checked_out_at: datetime
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
