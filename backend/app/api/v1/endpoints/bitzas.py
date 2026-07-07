import mimetypes
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.dependencies import get_bitza_service, get_current_user
from app.models.bitza import BitzaKind, BitzaStatus
from app.models.user import User
from app.schemas.bitza import (
    BitzaCreate,
    BitzaImageRead,
    BitzaListRead,
    BitzaRead,
    BitzaRetire,
    BitzaUpdate,
    CheckinRequest,
    CheckoutCreate,
    CheckoutRead,
    ReassignTeamRequest,
    ReassignTeamResponse,
    StockAdjustmentCreate,
    StockAdjustmentRead,
)
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.bitza_service import BitzaService

router = APIRouter(tags=["bitzas"])


# ---------------------------------------------------------------------------
# Categories — unchanged in behaviour from Phase 2
# ---------------------------------------------------------------------------

categories_router = APIRouter(prefix="/categories")


@categories_router.get("/", response_model=list[CategoryRead], summary="List all categories")
def list_categories(
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> list[CategoryRead]:
    return svc.list_categories()


@categories_router.post(
    "/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
def create_category(
    body: CategoryCreate,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> CategoryRead:
    return svc.create_category(data=body, actor=current_user)


@categories_router.patch(
    "/{category_id}", response_model=CategoryRead, summary="Rename a category"
)
def update_category(
    category_id: str,
    body: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> CategoryRead:
    return svc.update_category(category_id=category_id, data=body, actor=current_user)


@categories_router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a category"
)
def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> None:
    """Blocked if any bitzas are assigned to this category."""
    svc.delete_category(category_id=category_id, actor=current_user)


# ---------------------------------------------------------------------------
# Bitzas — the unified location/container/item tree
# ---------------------------------------------------------------------------

bitzas_router = APIRouter(prefix="/bitzas")


@bitzas_router.get(
    "/",
    response_model=list[BitzaListRead],
    summary="List bitzas",
)
def list_bitzas(
    parent_id: Optional[str] = Query(
        None, description="Direct children of this bitza only"
    ),
    root_only: bool = Query(
        False, description="Root bitzas only (parent_id IS NULL) — ignored if parent_id is set"
    ),
    kind: Optional[BitzaKind] = Query(None),
    status_filter: Optional[BitzaStatus] = Query(None, alias="status"),
    responsible_team_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> list[BitzaListRead]:
    """
    Direct children only — per AI_instructions.md, the backend never
    performs full subtree traversal for reads. The frontend drives any
    further descent with repeated calls using ``parent_id``.

    No privacy filtering (there is none in this app — see project context
    doc): every bitza is visible to every authenticated user regardless
    of who created it, who's responsible for it, or where it lives.
    """
    return svc.list_bitzas(
        parent_id=parent_id,
        root_only=root_only,
        kind=kind,
        status_filter=status_filter,
        responsible_team_id=responsible_team_id,
        category_id=category_id,
    )


@bitzas_router.post(
    "/",
    response_model=BitzaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bitza (location, container, tool, or stock item)",
)
def create_bitza(
    body: BitzaCreate,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaRead:
    """Any authenticated user may create any kind of bitza anywhere in
    the tree. responsible_team_id is required — the frontend should
    pre-fill it from the parent bitza's responsible_team_id when adding
    a child, but the backend does not resolve/inherit it automatically."""
    return svc.create_bitza(data=body, actor=current_user)


@bitzas_router.get("/{bitza_id}", response_model=BitzaRead, summary="Get a bitza")
def get_bitza(
    bitza_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaRead:
    return svc.get_bitza(bitza_id=bitza_id)


@bitzas_router.patch(
    "/{bitza_id}",
    response_model=BitzaRead,
    summary="Update a bitza",
)
def update_bitza(
    bitza_id: str,
    body: BitzaUpdate,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaRead:
    """
    Ordinary, single-row edit — never cascades, regardless of kind, even
    if responsible_team_id is included. Use POST /{bitza_id}/reassign-team
    for an explicit cascade scope and a dedicated audit trail entry.
    """
    return svc.update_bitza(bitza_id=bitza_id, data=body, actor=current_user)


@bitzas_router.delete(
    "/{bitza_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a bitza (admin/superuser only)",
    responses={
        403: {"description": "Only admin/superuser may hard-delete"},
        409: {"description": "Blocked — this bitza has children"},
    },
)
def delete_bitza(
    bitza_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> None:
    """
    Reserved for records that genuinely should never have existed
    (duplicates, test entries). For lost/broken/discontinued/superseded
    items, use POST /{bitza_id}/retire instead — that's open to any user
    and fully reversible.
    """
    svc.delete_bitza(bitza_id=bitza_id, actor=current_user)


# ---------------------------------------------------------------------------
# Retire / reactivate — open to any user, freely reversible
# ---------------------------------------------------------------------------

@bitzas_router.post(
    "/{bitza_id}/retire",
    response_model=BitzaRead,
    summary="Flag a bitza as retired (lost/broken/discontinued/superseded)",
)
def retire_bitza(
    bitza_id: str,
    body: BitzaRetire,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaRead:
    """Not an approval workflow — any authenticated user may flag any
    bitza retired, for any of the listed reasons. Reversible via
    /reactivate. See project context doc for why this replaces delete
    for these cases."""
    return svc.retire_bitza(bitza_id=bitza_id, data=body, actor=current_user)


@bitzas_router.post(
    "/{bitza_id}/reactivate",
    response_model=BitzaRead,
    summary="Clear retired status — e.g. a 'lost' item was found",
)
def reactivate_bitza(
    bitza_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaRead:
    return svc.reactivate_bitza(bitza_id=bitza_id, actor=current_user)


# ---------------------------------------------------------------------------
# Team reassignment (with cascade)
# ---------------------------------------------------------------------------

@bitzas_router.post(
    "/{bitza_id}/reassign-team",
    response_model=ReassignTeamResponse,
    summary="Reassign responsible team, optionally cascading to children",
)
def reassign_team(
    bitza_id: str,
    body: ReassignTeamRequest,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> ReassignTeamResponse:
    """
    cascade_scope is required: 'none' | 'direct_children' | 'all_descendants'.
    The backend never infers a default — see ReassignTeamRequest's
    docstring for why the right scope depends on mobility (a cupboard vs
    a toolbox) and is therefore a frontend UX decision, not a backend rule.
    """
    return svc.reassign_team(bitza_id=bitza_id, data=body, actor=current_user)


# ---------------------------------------------------------------------------
# Checkout / checkin (kind = mobile only)
# ---------------------------------------------------------------------------

@bitzas_router.post(
    "/{bitza_id}/checkout",
    response_model=CheckoutRead,
    status_code=status.HTTP_201_CREATED,
    summary="Check out a mobile bitza to yourself",
    responses={409: {"description": "Not a mobile bitza, retired, or already checked out"}},
)
def checkout_bitza(
    bitza_id: str,
    body: CheckoutCreate,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> CheckoutRead:
    """
    Holder is always the current user — there is no checking out on
    behalf of someone else. team_context defaults to your primary team
    if you have one and don't override it; either way it's a snapshot,
    never a live link.
    """
    return svc.checkout_bitza(bitza_id=bitza_id, data=body, actor=current_user)


@bitzas_router.post(
    "/{bitza_id}/checkin",
    response_model=CheckoutRead,
    summary="Return a checked-out mobile bitza",
    responses={409: {"description": "Not currently checked out"}},
)
def checkin_bitza(
    bitza_id: str,
    body: CheckinRequest,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> CheckoutRead:
    """Anyone may check something in, not just the person who checked it
    out — e.g. "I found this lying around and returned it"."""
    return svc.checkin_bitza(bitza_id=bitza_id, data=body, actor=current_user)


@bitzas_router.get(
    "/{bitza_id}/checkouts",
    response_model=list[CheckoutRead],
    summary="Checkout history for a mobile bitza",
)
def list_checkouts(
    bitza_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> list[CheckoutRead]:
    return svc.list_checkouts(bitza_id=bitza_id)


# ---------------------------------------------------------------------------
# Stock adjustments (kind = stock, stock_mode = exact only)
# ---------------------------------------------------------------------------

@bitzas_router.post(
    "/{bitza_id}/stock-adjustments",
    response_model=StockAdjustmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Adjust exact stock quantity (use +/- delta, not an absolute value)",
    responses={409: {"description": "Not an exact-mode stock bitza, or result would be negative"}},
)
def adjust_stock(
    bitza_id: str,
    body: StockAdjustmentCreate,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> StockAdjustmentRead:
    """quantity is never edited directly via PATCH — every change to
    exact-mode stock goes through here so the log stays complete."""
    return svc.adjust_stock(bitza_id=bitza_id, data=body, actor=current_user)


@bitzas_router.get(
    "/{bitza_id}/stock-adjustments",
    response_model=list[StockAdjustmentRead],
    summary="Stock adjustment history",
)
def list_stock_adjustments(
    bitza_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> list[StockAdjustmentRead]:
    return svc.list_stock_logs(bitza_id=bitza_id)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

@bitzas_router.get(
    "/{bitza_id}/images",
    response_model=list[BitzaImageRead],
    summary="List a bitza's images (metadata only — fetch each file separately)",
)
def list_images(
    bitza_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> list[BitzaImageRead]:
    return svc.list_images(bitza_id=bitza_id)


@bitzas_router.post(
    "/{bitza_id}/images",
    response_model=BitzaImageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image for a bitza",
)
async def upload_image(
    bitza_id: str,
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaImageRead:
    """Accepts JPEG, PNG, GIF, or WebP, max 10 MB. The first image
    uploaded for a bitza always becomes primary regardless of is_primary."""
    return await svc.upload_image(
        bitza_id=bitza_id, file=file, actor=current_user, is_primary=is_primary
    )


@bitzas_router.get(
    "/{bitza_id}/images/{image_id}",
    summary="Fetch a single image file",
    response_class=FileResponse,
    responses={
        200: {"content": {"image/*": {}}, "description": "The image file"},
        404: {"description": "Bitza, image, or file not found"},
    },
)
def get_image_file(
    bitza_id: str,
    image_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> FileResponse:
    """
    Authenticated endpoint, not a static file — Angular clients must
    fetch via HttpClient with { responseType: 'blob' } and build an
    object URL; plain <img src> will not send the Authorization header.
    """
    abs_path = svc.get_image_abs_path(bitza_id=bitza_id, image_id=image_id)
    media_type, _ = mimetypes.guess_type(abs_path)
    return FileResponse(abs_path, media_type=media_type or "application/octet-stream")


@bitzas_router.patch(
    "/{bitza_id}/images/{image_id}",
    response_model=BitzaImageRead,
    summary="Set this image as the primary/cover photo",
)
def set_primary_image(
    bitza_id: str,
    image_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> BitzaImageRead:
    return svc.set_primary_image(bitza_id=bitza_id, image_id=image_id)


@bitzas_router.delete(
    "/{bitza_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an image",
)
def delete_image(
    bitza_id: str,
    image_id: str,
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> None:
    """If the deleted image was primary and others remain, the oldest
    remaining image is automatically promoted to primary."""
    svc.delete_image(bitza_id=bitza_id, image_id=image_id)


# ---------------------------------------------------------------------------
# Combine sub-routers
# ---------------------------------------------------------------------------

router.include_router(categories_router)
router.include_router(bitzas_router)
