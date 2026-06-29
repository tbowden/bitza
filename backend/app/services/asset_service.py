import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.models.asset import Asset, AssetTransaction, AuditLog, Category
from app.models.user import User, UserRole
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.location_repository import LocationRepository
from app.repositories.user_repository import UserRepository
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
from app.services.location_service import LocationService

settings = get_settings()

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


class AssetService:
    """
    Business logic for categories, assets, transactions, and audit log.

    Asset visibility follows the LocationDetail/StorageLocation privacy cascade
    (delegated to LocationService.assert_detail_visible).

    Edit/Delete permissions:
    - Superuser:  any asset.
    - Creator:    their own asset.
    - Admin:      any asset whose location chain is fully shared.
    """

    def __init__(
        self,
        db: Session,
        asset_repo: AssetRepository,
        cat_repo: CategoryRepository,
        loc_repo: LocationRepository,
        user_repo: UserRepository,
        loc_service: LocationService,
    ) -> None:
        self._db = db
        self._assets = asset_repo
        self._cats = cat_repo
        self._locs = loc_repo
        self._users = user_repo
        self._loc_service = loc_service

    # ------------------------------------------------------------------ #
    # Permission helper
    # ------------------------------------------------------------------ #

    def _can_edit_asset(self, asset: Asset, actor: User) -> bool:
        if actor.role == UserRole.superuser:
            return True
        if asset.created_by == actor.id:
            return True
        if actor.role == UserRole.admin:
            # Admin can edit if the location chain is entirely shared.
            detail = self._locs.get_detail(asset.location_detail_id)
            if not detail:
                return False
            parent = self._locs.get_location(detail.storage_location_id)
            if not parent:
                return False
            return not parent.is_private and not detail.is_private
        return False

    def _asset_visible_to(self, asset: Asset, actor: User) -> bool:
        """Check visibility by delegating to the location service."""
        try:
            self._loc_service.assert_detail_visible(asset.location_detail_id, actor)
            return True
        except HTTPException:
            return False

    # ------------------------------------------------------------------ #
    # Category CRUD
    # ------------------------------------------------------------------ #

    def create_category(self, data: CategoryCreate, actor: User) -> CategoryRead:
        if self._cats.get_by_name(data.name):
            raise ConflictError(f"Category '{data.name}' already exists")
        cat = Category(id=str(uuid.uuid4()), name=data.name, created_by=actor.id)
        created = self._cats.create(cat)
        self._db.commit()
        return self._enrich_category(created)

    def list_categories(self) -> list[CategoryRead]:
        return [self._enrich_category(c) for c in self._cats.list_all()]

    def update_category(
        self, category_id: str, data: CategoryUpdate, actor: User
    ) -> CategoryRead:
        cat = self._cats.get(category_id)
        if not cat:
            raise _not_found("Category not found")
        existing = self._cats.get_by_name(data.name)
        if existing and existing.id != category_id:
            raise ConflictError(f"Category '{data.name}' already exists")
        cat.name = data.name
        updated = self._cats.update(cat)
        self._db.commit()
        return self._enrich_category(updated)

    def delete_category(self, category_id: str, actor: User) -> None:
        cat = self._cats.get(category_id)
        if not cat:
            raise _not_found("Category not found")
        if self._cats.count_assets(category_id) > 0:
            raise ConflictError(
                "Cannot delete a category that has assets assigned to it. "
                "Reassign or delete those assets first."
            )
        self._cats.delete(cat)
        self._db.commit()

    # ------------------------------------------------------------------ #
    # Asset CRUD
    # ------------------------------------------------------------------ #

    def create_asset(self, data: AssetCreate, actor: User) -> AssetRead:
        # Verify the target location_detail is visible to this user.
        self._loc_service.assert_detail_visible(data.location_detail_id, actor)

        if data.category_id and not self._cats.get(data.category_id):
            raise _not_found("Category not found")

        asset = Asset(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            quantity=data.initial_quantity,
            unit=data.unit,
            source_supplier=data.source_supplier,
            part_number=data.part_number,
            datasheet_url=data.datasheet_url,
            order_url=data.order_url,
            category_id=data.category_id,
            tags=data.tags or [],
            project_name=data.project_name,
            trello_link=data.trello_link,
            location_detail_id=data.location_detail_id,
            created_by=actor.id,
        )
        created = self._assets.create(asset)

        # Auto-create the initial transaction if quantity > 0.
        if data.initial_quantity > 0:
            txn = AssetTransaction(
                id=str(uuid.uuid4()),
                asset_id=created.id,
                delta=data.initial_quantity,
                quantity_after=data.initial_quantity,
                user_id=actor.id,
                note="Initial stock",
            )
            self._assets.create_transaction(txn)

        self._write_audit(
            entity_type="asset",
            entity_id=created.id,
            action="CREATE",
            user_id=actor.id,
            description=f"Created asset '{created.name}' (qty: {created.quantity})",
        )
        self._db.commit()
        return self._enrich_asset(created)

    def get_asset(self, asset_id: str, actor: User) -> AssetRead:
        asset = self._assets.get(asset_id)
        if not asset:
            raise _not_found("Asset not found")
        if not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")
        return self._enrich_asset(asset)

    def list_assets(
        self,
        actor: User,
        location_detail_id: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> list[AssetListRead]:
        if location_detail_id:
            assets = self._assets.list_by_location_detail(location_detail_id)
        elif category_id:
            assets = self._assets.list_by_category(category_id)
        else:
            assets = self._assets.list_all()

        visible = [a for a in assets if self._asset_visible_to(a, actor)]
        return [self._enrich_asset_list(a) for a in visible]

    def update_asset(
        self, asset_id: str, data: AssetUpdate, actor: User
    ) -> AssetRead:
        asset = self._assets.get(asset_id)
        if not asset or not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")
        if not self._can_edit_asset(asset, actor):
            raise PermissionDeniedError("You do not have permission to edit this asset")

        if data.name is not None:
            asset.name = data.name
        if data.description is not None:
            asset.description = data.description
        if data.unit is not None:
            asset.unit = data.unit
        if data.source_supplier is not None:
            asset.source_supplier = data.source_supplier
        if data.part_number is not None:
            asset.part_number = data.part_number
        if data.datasheet_url is not None:
            asset.datasheet_url = data.datasheet_url
        if data.order_url is not None:
            asset.order_url = data.order_url
        if data.category_id is not None:
            if data.category_id and not self._cats.get(data.category_id):
                raise _not_found("Category not found")
            asset.category_id = data.category_id
        if data.tags is not None:
            asset.tags = data.tags
        if data.project_name is not None:
            asset.project_name = data.project_name
        if data.trello_link is not None:
            asset.trello_link = data.trello_link
        if data.location_detail_id is not None:
            self._loc_service.assert_detail_visible(data.location_detail_id, actor)
            asset.location_detail_id = data.location_detail_id

        updated = self._assets.update(asset)
        self._write_audit("asset", asset_id, "UPDATE", actor.id, f"Updated asset '{asset.name}'")
        self._db.commit()
        return self._enrich_asset(updated)

    def delete_asset(self, asset_id: str, actor: User) -> None:
        asset = self._assets.get(asset_id)
        if not asset or not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")
        if not self._can_edit_asset(asset, actor):
            raise PermissionDeniedError("You do not have permission to delete this asset")

        # Remove image file from disk if present.
        if asset.image_path:
            _remove_image_file(asset.image_path)

        self._write_audit("asset", asset_id, "DELETE", actor.id, f"Deleted asset '{asset.name}'")
        self._assets.delete(asset)
        self._db.commit()

    # ------------------------------------------------------------------ #
    # Image upload
    # ------------------------------------------------------------------ #

    def get_asset_image_path(self, asset_id: str, actor: User) -> str:
        """
        Return the absolute filesystem path to the asset's image.
        Applies the same visibility rules as get_asset().
        Raises 404 if the asset is not visible, has no image, or the file
        is missing from disk (e.g. after a manual cleanup).
        """
        asset = self._assets.get(asset_id)
        if not asset or not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")
        if not asset.image_path:
            raise _not_found("This asset has no image")

        abs_path = Path(settings.UPLOAD_DIR) / asset.image_path
        if not abs_path.exists():
            raise _not_found("Image file not found")

        return str(abs_path)

    async def upload_image(
        self, asset_id: str, file: UploadFile, actor: User
    ) -> AssetRead:
        asset = self._assets.get(asset_id)
        if not asset or not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")
        if not self._can_edit_asset(asset, actor):
            raise PermissionDeniedError("You do not have permission to edit this asset")

        if file.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported image type '{file.content_type}'. "
                       f"Allowed: {', '.join(_ALLOWED_IMAGE_TYPES)}",
            )

        # Read and size-check.
        contents = await file.read()
        if len(contents) > _MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image exceeds 10 MB limit",
            )

        # Remove old image if one exists.
        if asset.image_path:
            _remove_image_file(asset.image_path)

        # Save new image.
        ext = Path(file.filename or "image.jpg").suffix or ".jpg"
        rel_path = f"assets/{asset_id}/{uuid.uuid4().hex}{ext}"
        abs_path = Path(settings.UPLOAD_DIR) / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(contents)

        asset.image_path = rel_path
        updated = self._assets.update(asset)
        self._db.commit()
        return self._enrich_asset(updated)

    # ------------------------------------------------------------------ #
    # Transactions
    # ------------------------------------------------------------------ #

    def add_transaction(
        self, asset_id: str, data: TransactionCreate, actor: User
    ) -> TransactionRead:
        asset = self._assets.get(asset_id)
        if not asset or not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")

        new_qty = asset.quantity + data.delta
        if new_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Transaction would result in negative quantity "
                       f"({asset.quantity} + {data.delta} = {new_qty})",
            )

        asset.quantity = new_qty
        self._assets.update(asset)

        txn = AssetTransaction(
            id=str(uuid.uuid4()),
            asset_id=asset_id,
            delta=data.delta,
            quantity_after=new_qty,
            user_id=actor.id,
            note=data.note,
        )
        created_txn = self._assets.create_transaction(txn)
        self._db.commit()
        return self._enrich_transaction(created_txn)

    def list_transactions(
        self, asset_id: str, actor: User
    ) -> list[TransactionRead]:
        asset = self._assets.get(asset_id)
        if not asset or not self._asset_visible_to(asset, actor):
            raise _not_found("Asset not found")
        txns = self._assets.list_transactions(asset_id)
        return [self._enrich_transaction(t) for t in txns]

    # ------------------------------------------------------------------ #
    # Audit log
    # ------------------------------------------------------------------ #

    def list_audit(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor: User = None,
        limit: int = 200,
    ) -> list[AuditLogRead]:
        if actor and actor.role == UserRole.user:
            raise PermissionDeniedError("Only admins and superusers may view the audit log")
        entries = self._assets.list_audit(
            entity_type=entity_type, entity_id=entity_id, limit=limit
        )
        return [self._enrich_audit(e) for e in entries]

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _write_audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: Optional[str],
        description: Optional[str] = None,
    ) -> None:
        entry = AuditLog(
            id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            description=description,
        )
        self._assets.create_audit(entry)

    def _user_name(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "unknown"
        user = self._users.get_by_id(user_id)
        return user.display_name if user else user_id

    def _enrich_category(self, cat: Category) -> CategoryRead:
        r = CategoryRead.model_validate(cat)
        r.asset_count = self._cats.count_assets(cat.id)
        return r

    def _enrich_asset(self, asset: Asset) -> AssetRead:
        r = AssetRead.model_validate(asset)
        if asset.category_id:
            cat = self._cats.get(asset.category_id)
            r.category_name = cat.name if cat else None
        detail = self._locs.get_detail(asset.location_detail_id)
        if detail:
            r.location_detail_name = detail.name
            parent = self._locs.get_location(detail.storage_location_id)
            if parent:
                r.storage_location_id = parent.id
                r.storage_location_name = parent.name
        r.created_by_display_name = self._user_name(asset.created_by)
        return r

    def _enrich_asset_list(self, asset: Asset) -> AssetListRead:
        r = AssetListRead.model_validate(asset)
        if asset.category_id:
            cat = self._cats.get(asset.category_id)
            r.category_name = cat.name if cat else None
        detail = self._locs.get_detail(asset.location_detail_id)
        if detail:
            r.location_detail_name = detail.name
            parent = self._locs.get_location(detail.storage_location_id)
            if parent:
                r.storage_location_name = parent.name
        return r

    def _enrich_transaction(self, txn: AssetTransaction) -> TransactionRead:
        r = TransactionRead.model_validate(txn)
        r.user_display_name = self._user_name(txn.user_id)
        return r

    def _enrich_audit(self, entry: AuditLog) -> AuditLogRead:
        r = AuditLogRead.model_validate(entry)
        r.user_display_name = self._user_name(entry.user_id)
        return r


def _remove_image_file(rel_path: str) -> None:
    """Best-effort removal of an image file from disk."""
    try:
        full = Path(settings.UPLOAD_DIR) / rel_path
        if full.exists():
            full.unlink()
    except OSError:
        pass
