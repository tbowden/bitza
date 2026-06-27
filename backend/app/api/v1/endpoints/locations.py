from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, get_location_service
from app.models.user import User
from app.schemas.location import (
    LocationDetailCreate,
    LocationDetailListRead,
    LocationDetailRead,
    LocationDetailUpdate,
    StorageLocationCreate,
    StorageLocationListRead,
    StorageLocationRead,
    StorageLocationUpdate,
)
from app.services.location_service import LocationService

router = APIRouter(prefix="/locations", tags=["locations"])


# ---------------------------------------------------------------------------
# Storage Locations
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[StorageLocationListRead],
    summary="List all visible storage locations",
)
def list_locations(
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> list[StorageLocationListRead]:
    """
    Returns all storage locations visible to the current user.
    Private locations are only visible to their owner and the superuser.
    Suitable for populating location dropdowns in the UI.
    """
    return svc.list_locations(actor=current_user)


@router.post(
    "/",
    response_model=StorageLocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a storage location",
)
def create_location(
    body: StorageLocationCreate,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> StorageLocationRead:
    """Any authenticated user may create a top-level storage location."""
    return svc.create_location(data=body, actor=current_user)


@router.get(
    "/{location_id}",
    response_model=StorageLocationRead,
    summary="Get a storage location",
)
def get_location(
    location_id: str,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> StorageLocationRead:
    return svc.get_location(location_id=location_id, actor=current_user)


@router.patch(
    "/{location_id}",
    response_model=StorageLocationRead,
    summary="Update a storage location",
)
def update_location(
    location_id: str,
    body: StorageLocationUpdate,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> StorageLocationRead:
    """
    Owner, admins (shared locations), or superuser may update.
    Only the superuser may reassign ``owner_id``.
    """
    return svc.update_location(
        location_id=location_id, data=body, actor=current_user
    )


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a storage location",
)
def delete_location(
    location_id: str,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> None:
    """Deletion is blocked if any sub-locations exist."""
    svc.delete_location(location_id=location_id, actor=current_user)


# ---------------------------------------------------------------------------
# Location Details (nested under a StorageLocation)
# ---------------------------------------------------------------------------

@router.get(
    "/{location_id}/details",
    response_model=list[LocationDetailListRead],
    summary="List sub-locations for a storage location",
)
def list_details(
    location_id: str,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> list[LocationDetailListRead]:
    """
    Returns all visible sub-locations for a given storage location.
    Privacy cascade is applied — private sub-locations inside a private parent
    are only visible to the parent owner and superuser.
    Suitable for populating sub-location dropdowns when adding assets.
    """
    return svc.list_details(location_id=location_id, actor=current_user)


@router.post(
    "/{location_id}/details",
    response_model=LocationDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sub-location",
)
def create_detail(
    location_id: str,
    body: LocationDetailCreate,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> LocationDetailRead:
    """
    Any user who can see the parent storage location may add a sub-location.
    The creating user becomes the owner of the sub-location.
    """
    return svc.create_detail(
        location_id=location_id, data=body, actor=current_user
    )


@router.get(
    "/{location_id}/details/{detail_id}",
    response_model=LocationDetailRead,
    summary="Get a sub-location",
)
def get_detail(
    location_id: str,
    detail_id: str,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> LocationDetailRead:
    return svc.get_detail(
        location_id=location_id, detail_id=detail_id, actor=current_user
    )


@router.patch(
    "/{location_id}/details/{detail_id}",
    response_model=LocationDetailRead,
    summary="Update a sub-location",
)
def update_detail(
    location_id: str,
    detail_id: str,
    body: LocationDetailUpdate,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> LocationDetailRead:
    return svc.update_detail(
        location_id=location_id,
        detail_id=detail_id,
        data=body,
        actor=current_user,
    )


@router.delete(
    "/{location_id}/details/{detail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a sub-location",
)
def delete_detail(
    location_id: str,
    detail_id: str,
    current_user: User = Depends(get_current_user),
    svc: LocationService = Depends(get_location_service),
) -> None:
    """Deletion is blocked if any assets are stored in this sub-location."""
    svc.delete_detail(
        location_id=location_id, detail_id=detail_id, actor=current_user
    )
