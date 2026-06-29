import mimetypes
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, status
from fastapi.responses import FileResponse

from app.core.dependencies import get_current_user, get_asset_service
from app.models.user import User
from app.schemas.asset import (
    AssetCreate,
    AssetListRead,
    AssetRead,
    AssetUpdate,
    AuditLogRead,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    TransactionCreate,
    TransactionRead,
)
from app.services.asset_service import AssetService

router = APIRouter(tags=["assets"])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

categories_router = APIRouter(prefix="/categories")


@categories_router.get(
    "/",
    response_model=list[CategoryRead],
    summary="List all categories",
)
def list_categories(
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> list[CategoryRead]:
    return svc.list_categories()


@categories_router.post(
    "/",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
def create_category(
    body: CategoryCreate,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> CategoryRead:
    """Any authenticated user may create categories."""
    return svc.create_category(data=body, actor=current_user)


@categories_router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Rename a category",
)
def update_category(
    category_id: str,
    body: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> CategoryRead:
    return svc.update_category(
        category_id=category_id, data=body, actor=current_user
    )


@categories_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
)
def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> None:
    """Blocked if any assets are assigned to this category."""
    svc.delete_category(category_id=category_id, actor=current_user)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

assets_router = APIRouter(prefix="/assets")


@assets_router.get(
    "/",
    response_model=list[AssetListRead],
    summary="List assets",
)
def list_assets(
    location_detail_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> list[AssetListRead]:
    """
    Returns all assets visible to the current user.
    Optionally filter by ``location_detail_id`` or ``category_id``.
    Privacy rules from the location chain are applied automatically.
    """
    return svc.list_assets(
        actor=current_user,
        location_detail_id=location_detail_id,
        category_id=category_id,
    )


@assets_router.post(
    "/",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an asset",
)
def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> AssetRead:
    """
    Any authenticated user may create an asset, provided they can see
    the target ``location_detail_id``.  An initial transaction is created
    automatically if ``initial_quantity > 0``.
    """
    return svc.create_asset(data=body, actor=current_user)


@assets_router.get(
    "/{asset_id}",
    response_model=AssetRead,
    summary="Get an asset",
)
def get_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> AssetRead:
    return svc.get_asset(asset_id=asset_id, actor=current_user)


@assets_router.patch(
    "/{asset_id}",
    response_model=AssetRead,
    summary="Update an asset's details",
)
def update_asset(
    asset_id: str,
    body: AssetUpdate,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> AssetRead:
    """
    All fields are optional.  To adjust stock levels use the
    ``/assets/{id}/transactions`` endpoint instead.
    """
    return svc.update_asset(asset_id=asset_id, data=body, actor=current_user)


@assets_router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an asset",
)
def delete_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> None:
    svc.delete_asset(asset_id=asset_id, actor=current_user)


@assets_router.get(
    "/{asset_id}/image",
    summary="Get the image for an asset",
    response_class=FileResponse,
    responses={
        200: {"content": {"image/*": {}}, "description": "The asset image"},
        404: {"description": "Asset not found, not visible, or has no image"},
    },
)
def get_asset_image(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> FileResponse:
    """
    Stream the asset's image file.

    Applies the same access rules as GET /assets/{id} — if you cannot see
    the asset you cannot see its image.

    Note for the Angular frontend: browsers do not send Authorization headers
    with plain <img> tags. Fetch this endpoint via HttpClient with
    { responseType: 'blob' } and create a blob URL for display.
    Remember to call URL.revokeObjectURL() when the component is destroyed.
    """
    abs_path = svc.get_asset_image_path(asset_id=asset_id, actor=current_user)
    media_type, _ = mimetypes.guess_type(abs_path)
    return FileResponse(
        abs_path,
        media_type=media_type or "application/octet-stream",
    )


@assets_router.post(
    "/{asset_id}/image",
    response_model=AssetRead,
    summary="Upload or replace an asset image",
)
async def upload_image(
    asset_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> AssetRead:
    """
    Accepts JPEG, PNG, GIF, or WebP.  Max 10 MB.
    Replaces any existing image.
    """
    return await svc.upload_image(asset_id=asset_id, file=file, actor=current_user)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@assets_router.get(
    "/{asset_id}/transactions",
    response_model=list[TransactionRead],
    summary="List stock transactions for an asset",
)
def list_transactions(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> list[TransactionRead]:
    """
    Returns the full transaction history for an asset, newest first.
    Visible to anyone who can see the asset.
    """
    return svc.list_transactions(asset_id=asset_id, actor=current_user)


@assets_router.post(
    "/{asset_id}/transactions",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a stock transaction",
)
def add_transaction(
    asset_id: str,
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> TransactionRead:
    """
    Use a positive ``delta`` to add stock, negative to remove.
    Rejected if the result would make quantity negative.
    Visible to anyone who can see the asset's location.
    """
    return svc.add_transaction(
        asset_id=asset_id, data=body, actor=current_user
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

audit_router = APIRouter(prefix="/audit")


@audit_router.get(
    "/",
    response_model=list[AuditLogRead],
    summary="View audit log (admin/superuser only)",
)
def list_audit(
    entity_type: Optional[str] = Query(None, description="Filter by entity type, e.g. 'asset'"),
    entity_id: Optional[str] = Query(None, description="Filter by a specific entity ID"),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    svc: AssetService = Depends(get_asset_service),
) -> list[AuditLogRead]:
    return svc.list_audit(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=current_user,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Combine all sub-routers into one for mounting
# ---------------------------------------------------------------------------

router.include_router(categories_router)
router.include_router(assets_router)
router.include_router(audit_router)
