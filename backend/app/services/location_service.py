import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, PermissionDeniedError, UserNotFoundError
from app.models.location import LocationDetail, StorageLocation
from app.models.user import User, UserRole
from app.repositories.asset_repository import AssetRepository
from app.repositories.location_repository import LocationRepository
from app.repositories.user_repository import UserRepository
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

# Reusable sentinel for "not found" without importing HTTPException here.
from fastapi import HTTPException, status


def _not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


class LocationService:
    """
    Business logic for storage locations and location details.

    Privacy matrix:
    ┌─────────────────────────────────┬───────────────┬──────────────┐
    │ Resource                        │ superuser     │ others       │
    ├─────────────────────────────────┼───────────────┼──────────────┤
    │ Private StorageLocation         │ visible       │ owner only   │
    │ Private LocationDetail          │ visible       │ owner only   │
    │ Cascaded private (parent priv.) │ visible       │ owner of     │
    │                                 │               │ parent only  │
    └─────────────────────────────────┴───────────────┴──────────────┘
    Admins respect privacy rules exactly like regular users.

    Edit / Delete:
    - Superuser: any resource.
    - Owner: their own resource.
    - Admin: any *shared* resource.
    """

    def __init__(
        self,
        db: Session,
        location_repo: LocationRepository,
        user_repo: UserRepository,
        asset_repo: AssetRepository,
    ) -> None:
        self._db = db
        self._loc = location_repo
        self._users = user_repo
        self._assets = asset_repo

    # ------------------------------------------------------------------ #
    # Privacy helpers
    # ------------------------------------------------------------------ #

    def _can_see_location(self, loc: StorageLocation, actor: User) -> bool:
        if actor.role == UserRole.superuser:
            return True
        if not loc.is_private:
            return True
        return loc.owner_id == actor.id

    def _can_see_detail(
        self, detail: LocationDetail, parent: StorageLocation, actor: User
    ) -> bool:
        if actor.role == UserRole.superuser:
            return True
        # Cascade: if parent is private, only parent owner can see anything inside.
        if parent.is_private:
            return parent.owner_id == actor.id
        # Parent is shared — apply detail's own privacy flag.
        if not detail.is_private:
            return True
        return detail.owner_id == actor.id

    def _can_edit_location(self, loc: StorageLocation, actor: User) -> bool:
        if actor.role == UserRole.superuser:
            return True
        if loc.owner_id == actor.id:
            return True
        if actor.role == UserRole.admin and not loc.is_private:
            return True
        return False

    def _can_edit_detail(
        self, detail: LocationDetail, parent: StorageLocation, actor: User
    ) -> bool:
        if actor.role == UserRole.superuser:
            return True
        if detail.owner_id == actor.id:
            return True
        if parent.owner_id == actor.id:
            return True
        if actor.role == UserRole.admin and not parent.is_private and not detail.is_private:
            return True
        return False

    def _effective_private(
        self, detail: LocationDetail, parent: StorageLocation
    ) -> bool:
        """True if the detail is private either directly or via cascade."""
        return parent.is_private or detail.is_private

    # ------------------------------------------------------------------ #
    # StorageLocation CRUD
    # ------------------------------------------------------------------ #

    def create_location(
        self, data: StorageLocationCreate, actor: User
    ) -> StorageLocationRead:
        location = StorageLocation(
            id=str(uuid.uuid4()),
            name=data.name,
            owner_id=actor.id,
            is_private=data.is_private,
        )
        created = self._loc.create_location(location)
        self._db.commit()
        return self._enrich_location(created)

    def get_location(self, location_id: str, actor: User) -> StorageLocationRead:
        loc = self._loc.get_location(location_id)
        if not loc:
            raise _not_found("Storage location not found")
        if not self._can_see_location(loc, actor):
            raise _not_found("Storage location not found")  # intentionally opaque
        return self._enrich_location(loc)

    def list_locations(self, actor: User) -> list[StorageLocationListRead]:
        all_locs = self._loc.list_locations()
        visible = [l for l in all_locs if self._can_see_location(l, actor)]
        return [self._enrich_location_list(l) for l in visible]

    def update_location(
        self, location_id: str, data: StorageLocationUpdate, actor: User
    ) -> StorageLocationRead:
        loc = self._loc.get_location(location_id)
        if not loc or not self._can_see_location(loc, actor):
            raise _not_found("Storage location not found")
        if not self._can_edit_location(loc, actor):
            raise PermissionDeniedError("You do not have permission to edit this location")

        if data.name is not None:
            loc.name = data.name
        if data.is_private is not None:
            loc.is_private = data.is_private
        if data.owner_id is not None:
            # Only superuser may reassign ownership.
            if actor.role != UserRole.superuser:
                raise PermissionDeniedError("Only the superuser may reassign location ownership")
            new_owner = self._users.get_by_id(data.owner_id)
            if not new_owner:
                raise UserNotFoundError("New owner user not found")
            loc.owner_id = data.owner_id

        updated = self._loc.update_location(loc)
        self._db.commit()
        return self._enrich_location(updated)

    def delete_location(self, location_id: str, actor: User) -> None:
        loc = self._loc.get_location(location_id)
        if not loc or not self._can_see_location(loc, actor):
            raise _not_found("Storage location not found")
        if not self._can_edit_location(loc, actor):
            raise PermissionDeniedError("You do not have permission to delete this location")

        detail_count = self._loc.count_details(location_id)
        if detail_count > 0:
            raise ConflictError(
                f"Cannot delete location with {detail_count} sub-location(s). "
                "Remove all sub-locations first."
            )

        self._loc.delete_location(loc)
        self._db.commit()

    # ------------------------------------------------------------------ #
    # LocationDetail CRUD
    # ------------------------------------------------------------------ #

    def create_detail(
        self,
        location_id: str,
        data: LocationDetailCreate,
        actor: User,
    ) -> LocationDetailRead:
        parent = self._loc.get_location(location_id)
        if not parent or not self._can_see_location(parent, actor):
            raise _not_found("Storage location not found")

        detail = LocationDetail(
            id=str(uuid.uuid4()),
            storage_location_id=location_id,
            name=data.name,
            owner_id=actor.id,
            is_private=data.is_private,
            rfid_tag=data.rfid_tag,
        )
        created = self._loc.create_detail(detail)
        self._db.commit()
        return self._enrich_detail(created, parent)

    def get_detail(
        self, location_id: str, detail_id: str, actor: User
    ) -> LocationDetailRead:
        parent = self._loc.get_location(location_id)
        if not parent or not self._can_see_location(parent, actor):
            raise _not_found("Storage location not found")

        detail = self._loc.get_detail(detail_id)
        if not detail or detail.storage_location_id != location_id:
            raise _not_found("Location detail not found")
        if not self._can_see_detail(detail, parent, actor):
            raise _not_found("Location detail not found")

        return self._enrich_detail(detail, parent)

    def list_details(
        self, location_id: str, actor: User
    ) -> list[LocationDetailListRead]:
        parent = self._loc.get_location(location_id)
        if not parent or not self._can_see_location(parent, actor):
            raise _not_found("Storage location not found")

        all_details = self._loc.list_details_for_location(location_id)
        visible = [d for d in all_details if self._can_see_detail(d, parent, actor)]
        return [self._enrich_detail_list(d, parent) for d in visible]

    def update_detail(
        self,
        location_id: str,
        detail_id: str,
        data: LocationDetailUpdate,
        actor: User,
    ) -> LocationDetailRead:
        parent = self._loc.get_location(location_id)
        if not parent or not self._can_see_location(parent, actor):
            raise _not_found("Storage location not found")

        detail = self._loc.get_detail(detail_id)
        if not detail or detail.storage_location_id != location_id:
            raise _not_found("Location detail not found")
        if not self._can_see_detail(detail, parent, actor):
            raise _not_found("Location detail not found")
        if not self._can_edit_detail(detail, parent, actor):
            raise PermissionDeniedError("You do not have permission to edit this location detail")

        if data.name is not None:
            detail.name = data.name
        if data.is_private is not None:
            detail.is_private = data.is_private
        if data.rfid_tag is not None:
            detail.rfid_tag = data.rfid_tag
        if data.owner_id is not None:
            if actor.role != UserRole.superuser:
                raise PermissionDeniedError("Only the superuser may reassign detail ownership")
            new_owner = self._users.get_by_id(data.owner_id)
            if not new_owner:
                raise UserNotFoundError("New owner user not found")
            detail.owner_id = data.owner_id

        updated = self._loc.update_detail(detail)
        self._db.commit()
        return self._enrich_detail(updated, parent)

    def delete_detail(
        self, location_id: str, detail_id: str, actor: User
    ) -> None:
        parent = self._loc.get_location(location_id)
        if not parent or not self._can_see_location(parent, actor):
            raise _not_found("Storage location not found")

        detail = self._loc.get_detail(detail_id)
        if not detail or detail.storage_location_id != location_id:
            raise _not_found("Location detail not found")
        if not self._can_see_detail(detail, parent, actor):
            raise _not_found("Location detail not found")
        if not self._can_edit_detail(detail, parent, actor):
            raise PermissionDeniedError("You do not have permission to delete this location detail")

        asset_count = self._loc.count_assets_for_detail(detail_id)
        if asset_count > 0:
            raise ConflictError(
                f"Cannot delete sub-location with {asset_count} asset(s). "
                "Reassign or delete assets first."
            )

        self._loc.delete_detail(detail)
        self._db.commit()

    # ------------------------------------------------------------------ #
    # Visibility helper (used by AssetService)
    # ------------------------------------------------------------------ #

    def assert_detail_visible(self, detail_id: str, actor: User) -> LocationDetail:
        """
        Return the LocationDetail if the actor can see it, else raise 404.
        Used by AssetService when creating/moving assets.
        """
        detail = self._loc.get_detail(detail_id)
        if not detail:
            raise _not_found("Location detail not found")
        parent = self._loc.get_location(detail.storage_location_id)
        if not parent or not self._can_see_detail(detail, parent, actor):
            raise _not_found("Location detail not found")
        return detail

    # ------------------------------------------------------------------ #
    # Enrichment helpers
    # ------------------------------------------------------------------ #

    def _owner_name(self, owner_id: str) -> str:
        user = self._users.get_by_id(owner_id)
        return user.display_name if user else owner_id

    def _enrich_location(self, loc: StorageLocation) -> StorageLocationRead:
        detail_count = self._loc.count_details(loc.id)
        r = StorageLocationRead.model_validate(loc)
        r.owner_display_name = self._owner_name(loc.owner_id)
        r.detail_count = detail_count
        return r

    def _enrich_location_list(self, loc: StorageLocation) -> StorageLocationListRead:
        r = StorageLocationListRead.model_validate(loc)
        r.owner_display_name = self._owner_name(loc.owner_id)
        r.detail_count = self._loc.count_details(loc.id)
        return r

    def _enrich_detail(
        self, detail: LocationDetail, parent: StorageLocation
    ) -> LocationDetailRead:
        r = LocationDetailRead.model_validate(detail)
        r.storage_location_name = parent.name
        r.owner_display_name = self._owner_name(detail.owner_id)
        r.effective_private = self._effective_private(detail, parent)
        r.asset_count = self._loc.count_assets_for_detail(detail.id)
        return r

    def _enrich_detail_list(
        self, detail: LocationDetail, parent: StorageLocation
    ) -> LocationDetailListRead:
        r = LocationDetailListRead.model_validate(detail)
        r.storage_location_name = parent.name
        r.effective_private = self._effective_private(detail, parent)
        r.asset_count = self._loc.count_assets_for_detail(detail.id)
        return r
