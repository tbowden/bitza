import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.models.audit import AuditLog
from app.models.category import Category
from app.models.bitza import (
    Bitza,
    BitzaImage,
    BitzaKind,
    BitzaStatus,
    Checkout,
    StockLog,
    StockMode,
)
from app.models.user import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.bitza_image_repository import BitzaImageRepository
from app.repositories.bitza_repository import BitzaRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.checkout_repository import CheckoutRepository
from app.repositories.stock_log_repository import StockLogRepository
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.audit import AuditLogRead
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
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

settings = get_settings()

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BitzaService:
    """
    Business logic for the unified Bitza tree, plus its satellite records
    (images, checkouts, stock logs).

    Permission philosophy (see bitza_project_context.md): any authenticated
    user may create, edit, move, retire/reactivate, check out/in, and
    adjust stock on ANY Bitza — there is no ownership-based gate anywhere
    in this service, deliberately. The single exception is hard delete,
    restricted to admin/superuser, because a delete makes the record
    disappear entirely rather than just flagging it retired.

    Cascading team reassignment is the one place this service walks a
    full subtree — see reassign_team — and it is always a distinct,
    explicit action, never an implicit side-effect of an ordinary edit.
    """

    def __init__(
        self,
        db: Session,
        bitza_repo: BitzaRepository,
        team_repo: TeamRepository,
        category_repo: CategoryRepository,
        user_repo: UserRepository,
        checkout_repo: CheckoutRepository,
        stock_log_repo: StockLogRepository,
        image_repo: BitzaImageRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._db = db
        self._bitzas = bitza_repo
        self._teams = team_repo
        self._categories = category_repo
        self._users = user_repo
        self._checkouts = checkout_repo
        self._stock_logs = stock_log_repo
        self._images = image_repo
        self._audit = audit_repo

    # ------------------------------------------------------------------
    # Category CRUD — unchanged in behaviour from Phase 2, just now
    # counting against Bitza instead of the old Asset table
    # ------------------------------------------------------------------

    def create_category(self, data: CategoryCreate, actor: User) -> CategoryRead:
        if self._categories.get_by_name(data.name):
            raise ConflictError(f"Category '{data.name}' already exists")
        cat = Category(id=str(uuid.uuid4()), name=data.name, created_by=actor.id)
        created = self._categories.create(cat)
        self._db.commit()
        return self._enrich_category(created)

    def list_categories(self) -> list[CategoryRead]:
        return [self._enrich_category(c) for c in self._categories.list_all()]

    def update_category(self, category_id: str, data: CategoryUpdate, actor: User) -> CategoryRead:
        cat = self._categories.get(category_id)
        if not cat:
            raise _not_found("Category not found")
        existing = self._categories.get_by_name(data.name)
        if existing and existing.id != category_id:
            raise ConflictError(f"Category '{data.name}' already exists")
        cat.name = data.name
        updated = self._categories.update(cat)
        self._db.commit()
        return self._enrich_category(updated)

    def delete_category(self, category_id: str, actor: User) -> None:
        cat = self._categories.get(category_id)
        if not cat:
            raise _not_found("Category not found")
        if self._categories.count_bitzas(category_id) > 0:
            raise ConflictError(
                "Cannot delete a category that has bitzas assigned to it. "
                "Reassign or delete those bitzas first."
            )
        self._categories.delete(cat)
        self._db.commit()

    # ------------------------------------------------------------------
    # Create / read / update / delete
    # ------------------------------------------------------------------

    def create_bitza(self, data: BitzaCreate, actor: User) -> BitzaRead:
        if data.parent_id and not self._bitzas.get(data.parent_id):
            raise _not_found("Parent bitza not found")
        if not self._teams.get(data.responsible_team_id):
            raise _not_found("Responsible team not found")
        if data.category_id and not self._categories.get(data.category_id):
            raise _not_found("Category not found")

        purchased_by = data.purchased_by_user_id or actor.id

        bitza = Bitza(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            kind=data.kind,
            parent_id=data.parent_id,
            responsible_team_id=data.responsible_team_id,
            category_id=data.category_id,
            tags=data.tags or [],
            purchased_by_user_id=purchased_by,
            vendor=data.vendor,
            purchase_date=data.purchase_date,
            order_url=data.order_url,
            stock_mode=data.stock_mode,
            quantity=data.quantity,
            low_stock_threshold=data.low_stock_threshold,
            fuzzy_state=data.fuzzy_state,
        )
        created = self._bitzas.create(bitza)
        self._write_audit("bitza", created.id, "CREATE", actor.id, f"Created '{created.name}'")
        self._db.commit()
        return self._enrich_bitza(created)

    def get_bitza(self, bitza_id: str) -> BitzaRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        return self._enrich_bitza(bitza)

    def list_bitzas(
        self,
        parent_id: Optional[str] = None,
        root_only: bool = False,
        kind: Optional[BitzaKind] = None,
        status_filter: Optional[BitzaStatus] = None,
        responsible_team_id: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> list[BitzaListRead]:
        if parent_id is not None:
            bitzas = self._bitzas.list_by_parent(parent_id)
        elif root_only:
            bitzas = self._bitzas.list_roots()
        else:
            bitzas = self._bitzas.list_filtered(
                kind=kind,
                status=status_filter,
                responsible_team_id=responsible_team_id,
                category_id=category_id,
            )
            return [self._enrich_bitza_list(b) for b in bitzas]

        # parent_id / root_only paths: apply the remaining filters in memory
        # (direct-children/roots result sets are small — see
        # AI_instructions.md, this stays a single non-recursive query).
        if kind is not None:
            bitzas = [b for b in bitzas if b.kind == kind]
        if status_filter is not None:
            bitzas = [b for b in bitzas if b.status == status_filter]
        if responsible_team_id is not None:
            bitzas = [b for b in bitzas if b.responsible_team_id == responsible_team_id]
        if category_id is not None:
            bitzas = [b for b in bitzas if b.category_id == category_id]
        return [self._enrich_bitza_list(b) for b in bitzas]

    def update_bitza(self, bitza_id: str, data: BitzaUpdate, actor: User) -> BitzaRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")

        if data.parent_id is not None and data.parent_id != bitza.parent_id:
            new_parent = self._bitzas.get(data.parent_id)
            if not new_parent:
                raise _not_found("New parent bitza not found")
            if self._would_create_cycle(bitza_id, data.parent_id):
                raise ConflictError(
                    "Cannot move a bitza underneath its own descendant"
                )
            bitza.parent_id = data.parent_id

        if data.responsible_team_id is not None:
            if not self._teams.get(data.responsible_team_id):
                raise _not_found("Responsible team not found")
            bitza.responsible_team_id = data.responsible_team_id

        if data.name is not None:
            bitza.name = data.name
        if data.description is not None:
            bitza.description = data.description
        if data.category_id is not None:
            if data.category_id and not self._categories.get(data.category_id):
                raise _not_found("Category not found")
            bitza.category_id = data.category_id
        if data.tags is not None:
            bitza.tags = data.tags
        if data.vendor is not None:
            bitza.vendor = data.vendor
        if data.purchase_date is not None:
            bitza.purchase_date = data.purchase_date
        if data.order_url is not None:
            bitza.order_url = data.order_url
        if data.low_stock_threshold is not None:
            bitza.low_stock_threshold = data.low_stock_threshold
        if data.fuzzy_state is not None:
            bitza.fuzzy_state = data.fuzzy_state

        updated = self._bitzas.update(bitza)
        self._write_audit("bitza", bitza_id, "UPDATE", actor.id, f"Updated '{bitza.name}'")
        self._db.commit()
        return self._enrich_bitza(updated)

    def delete_bitza(self, bitza_id: str, actor: User) -> None:
        if actor.role not in (UserRole.admin, UserRole.superuser):
            raise PermissionDeniedError(
                "Only admins or the superuser may permanently delete a bitza — "
                "use retire instead to record it as lost/broken/discontinued"
            )
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        child_count = self._bitzas.count_children(bitza_id)
        if child_count > 0:
            raise ConflictError(
                f"Cannot delete a bitza with {child_count} child bitza(s). "
                "Move or delete them first."
            )
        self._write_audit("bitza", bitza_id, "DELETE", actor.id, f"Deleted '{bitza.name}'")
        self._bitzas.delete(bitza)
        self._db.commit()

    # ------------------------------------------------------------------
    # Retire / reactivate — freely settable by any user, not a workflow
    # ------------------------------------------------------------------

    def retire_bitza(self, bitza_id: str, data: BitzaRetire, actor: User) -> BitzaRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        bitza.status = BitzaStatus.retired
        bitza.retired_reason = data.reason
        bitza.retired_note = data.note
        bitza.retired_at = _utcnow()
        bitza.retired_by_user_id = actor.id
        updated = self._bitzas.update(bitza)
        self._write_audit(
            "bitza", bitza_id, "RETIRE", actor.id,
            f"Retired '{bitza.name}' (reason={data.reason.value})",
        )
        self._db.commit()
        return self._enrich_bitza(updated)

    def reactivate_bitza(self, bitza_id: str, actor: User) -> BitzaRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        bitza.status = BitzaStatus.active
        bitza.retired_reason = None
        bitza.retired_note = None
        bitza.retired_at = None
        bitza.retired_by_user_id = None
        updated = self._bitzas.update(bitza)
        self._write_audit("bitza", bitza_id, "REACTIVATE", actor.id, f"Reactivated '{bitza.name}'")
        self._db.commit()
        return self._enrich_bitza(updated)

    # ------------------------------------------------------------------
    # Team reassignment — the one place this service walks a full subtree
    # ------------------------------------------------------------------

    def reassign_team(
        self, bitza_id: str, data: ReassignTeamRequest, actor: User
    ) -> ReassignTeamResponse:
        """
        cascade_scope is required on the request and is never inferred —
        see ReassignTeamRequest's docstring. "none" behaves like a plain
        PATCH but produces a dedicated, single audit entry summarising
        the whole sweep (not one row per affected bitza, so a large
        cascade doesn't flood the log).
        """
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        team = self._teams.get(data.team_id)
        if not team:
            raise _not_found("Team not found")

        affected: list[Bitza] = [bitza]
        if data.cascade_scope == "direct_children":
            affected.extend(self._bitzas.list_by_parent(bitza_id))
        elif data.cascade_scope == "all_descendants":
            affected.extend(self._collect_descendants(bitza_id))
        elif data.cascade_scope != "none":
            # Schema regex already restricts this, but fail loudly rather
            # than silently no-op if it ever gets bypassed.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown cascade_scope '{data.cascade_scope}'",
            )

        for b in affected:
            b.responsible_team_id = data.team_id
            self._bitzas.update(b)

        self._write_audit(
            "bitza", bitza_id, "REASSIGN_TEAM", actor.id,
            f"Reassigned to team '{team.name}' (scope={data.cascade_scope}, "
            f"{len(affected)} bitza(s) affected)",
        )
        self._db.commit()
        return ReassignTeamResponse(
            bitza_id=bitza_id,
            team_id=data.team_id,
            cascade_scope=data.cascade_scope,
            updated_count=len(affected),
        )

    def _collect_descendants(self, bitza_id: str) -> list[Bitza]:
        """
        Level-by-level BFS using repeated direct-children calls — the one
        deliberate exception to "no full subtree traversal on the
        backend" (that rule is about the READ path / display latency;
        this is a rare, explicit WRITE operation). Not a single recursive
        SQL statement — see AI_instructions.md and the project context
        doc for why that distinction matters here.
        """
        result: list[Bitza] = []
        frontier = self._bitzas.list_by_parent(bitza_id)
        while frontier:
            result.extend(frontier)
            next_frontier: list[Bitza] = []
            for b in frontier:
                next_frontier.extend(self._bitzas.list_by_parent(b.id))
            frontier = next_frontier
        return result

    def _would_create_cycle(self, bitza_id: str, candidate_parent_id: str) -> bool:
        if candidate_parent_id == bitza_id:
            return True
        ancestors = self._bitzas.get_ancestors(candidate_parent_id)
        return any(a.id == bitza_id for a in ancestors)

    # ------------------------------------------------------------------
    # Checkout / checkin (kind = mobile only)
    # ------------------------------------------------------------------

    def checkout_bitza(
        self, bitza_id: str, data: CheckoutCreate, actor: User
    ) -> CheckoutRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        if bitza.kind != BitzaKind.mobile:
            raise ConflictError("Only mobile bitzas can be checked out")
        if bitza.status == BitzaStatus.retired:
            raise ConflictError("Cannot check out a retired bitza")

        existing = self._checkouts.get_open_checkout(bitza_id)
        if existing:
            holder = self._user_display_name(existing.holder_id) if existing.holder_id else "someone"
            raise ConflictError(f"Already checked out to {holder}")

        team_context = data.team_context
        if team_context is None:
            primary = self._teams.get_primary_membership(actor.id)
            if primary:
                team = self._teams.get(primary.team_id)
                team_context = team.name if team else None

        checkout = Checkout(
            id=str(uuid.uuid4()),
            bitza_id=bitza_id,
            holder_id=actor.id,
            team_context=team_context,
            note=data.note,
        )
        created = self._checkouts.create(checkout)
        self._db.commit()
        return self._enrich_checkout(created)

    def checkin_bitza(
        self, bitza_id: str, data: CheckinRequest, actor: User
    ) -> CheckoutRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        open_checkout = self._checkouts.get_open_checkout(bitza_id)
        if not open_checkout:
            raise ConflictError("This bitza is not currently checked out")

        open_checkout.checked_in_at = _utcnow()
        if data.note:
            open_checkout.note = (
                f"{open_checkout.note}\n{data.note}" if open_checkout.note else data.note
            )
        updated = self._checkouts.update(open_checkout)
        self._db.commit()
        return self._enrich_checkout(updated)

    def list_checkouts(self, bitza_id: str) -> list[CheckoutRead]:
        if not self._bitzas.get(bitza_id):
            raise _not_found("Bitza not found")
        return [self._enrich_checkout(c) for c in self._checkouts.list_for_bitza(bitza_id)]

    # ------------------------------------------------------------------
    # Stock adjustments (kind = stock, stock_mode = exact only)
    # ------------------------------------------------------------------

    def adjust_stock(
        self, bitza_id: str, data: StockAdjustmentCreate, actor: User
    ) -> StockAdjustmentRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")
        if bitza.kind != BitzaKind.stock or bitza.stock_mode != StockMode.exact:
            raise ConflictError(
                "Stock adjustments only apply to bitzas with kind='stock' and "
                "stock_mode='exact'"
            )

        current = bitza.quantity or 0
        new_qty = current + data.delta
        if new_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Adjustment would result in negative quantity "
                       f"({current} + {data.delta} = {new_qty})",
            )

        bitza.quantity = new_qty
        self._bitzas.update(bitza)

        log = StockLog(
            id=str(uuid.uuid4()),
            bitza_id=bitza_id,
            delta=data.delta,
            quantity_after=new_qty,
            user_id=actor.id,
            note=data.note,
        )
        created = self._stock_logs.create(log)
        self._db.commit()
        return self._enrich_stock_log(created)

    def list_stock_logs(self, bitza_id: str) -> list[StockAdjustmentRead]:
        if not self._bitzas.get(bitza_id):
            raise _not_found("Bitza not found")
        return [self._enrich_stock_log(l) for l in self._stock_logs.list_for_bitza(bitza_id)]

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    async def upload_image(
        self, bitza_id: str, file: UploadFile, actor: User, is_primary: bool = False
    ) -> BitzaImageRead:
        bitza = self._bitzas.get(bitza_id)
        if not bitza:
            raise _not_found("Bitza not found")

        if file.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported image type '{file.content_type}'. "
                       f"Allowed: {', '.join(_ALLOWED_IMAGE_TYPES)}",
            )
        contents = await file.read()
        if len(contents) > _MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image exceeds 10 MB limit",
            )

        ext = Path(file.filename or "image.jpg").suffix or ".jpg"
        rel_path = f"bitzas/{bitza_id}/{uuid.uuid4().hex}{ext}"
        abs_path = Path(settings.UPLOAD_DIR) / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(contents)

        # The first image on a bitza is always primary, regardless of what
        # was requested — there should never be a bitza with images but no
        # designated cover photo.
        no_existing_images = len(self._images.list_for_bitza(bitza_id)) == 0
        make_primary = is_primary or no_existing_images
        if make_primary:
            self._images.unset_primary_for_bitza(bitza_id)

        image = BitzaImage(
            id=str(uuid.uuid4()),
            bitza_id=bitza_id,
            image_path=rel_path,
            is_primary=make_primary,
            uploaded_by=actor.id,
        )
        created = self._images.create(image)
        self._db.commit()
        return self._enrich_image(created)

    def list_images(self, bitza_id: str) -> list[BitzaImageRead]:
        if not self._bitzas.get(bitza_id):
            raise _not_found("Bitza not found")
        return [self._enrich_image(i) for i in self._images.list_for_bitza(bitza_id)]

    def get_image_abs_path(self, bitza_id: str, image_id: str) -> str:
        image = self._images.get(image_id)
        if not image or image.bitza_id != bitza_id:
            raise _not_found("Image not found")
        abs_path = Path(settings.UPLOAD_DIR) / image.image_path
        if not abs_path.exists():
            raise _not_found("Image file not found")
        return str(abs_path)

    def set_primary_image(self, bitza_id: str, image_id: str) -> BitzaImageRead:
        image = self._images.get(image_id)
        if not image or image.bitza_id != bitza_id:
            raise _not_found("Image not found")
        self._images.unset_primary_for_bitza(bitza_id)
        image.is_primary = True
        updated = self._images.update(image)
        self._db.commit()
        return self._enrich_image(updated)

    def delete_image(self, bitza_id: str, image_id: str) -> None:
        image = self._images.get(image_id)
        if not image or image.bitza_id != bitza_id:
            raise _not_found("Image not found")
        was_primary = image.is_primary

        abs_path = Path(settings.UPLOAD_DIR) / image.image_path
        try:
            if abs_path.exists():
                abs_path.unlink()
        except OSError:
            pass

        self._images.delete(image)

        if was_primary:
            remaining = self._images.list_for_bitza(bitza_id)
            if remaining:
                remaining[0].is_primary = True
                self._images.update(remaining[0])

        self._db.commit()

    # ------------------------------------------------------------------
    # Audit log — admin/superuser only (read visibility, not a mutation;
    # the one place in this service that DOES gate by role for a read,
    # unchanged from Phase 2's original behaviour)
    # ------------------------------------------------------------------

    def list_audit(
        self,
        actor: User,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 200,
    ) -> list[AuditLogRead]:
        if actor.role not in (UserRole.admin, UserRole.superuser):
            raise PermissionDeniedError("Only admins and superusers may view the audit log")
        entries = self._audit.list_all(entity_type=entity_type, entity_id=entity_id, limit=limit)
        return [self._enrich_audit(e) for e in entries]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write_audit(
        self, entity_type: str, entity_id: str, action: str, user_id: str, description: str
    ) -> None:
        entry = AuditLog(
            id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            description=description,
        )
        self._audit.create(entry)

    def _user_display_name(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "unknown"
        user = self._users.get_by_id(user_id)
        return user.display_name if user else user_id

    def _enrich_bitza(self, bitza: Bitza) -> BitzaRead:
        r = BitzaRead.model_validate(bitza)

        if bitza.parent_id:
            parent = self._bitzas.get(bitza.parent_id)
            r.parent_name = parent.name if parent else None
        r.child_count = self._bitzas.count_children(bitza.id)

        team = self._teams.get(bitza.responsible_team_id)
        r.responsible_team_name = team.name if team else ""

        if bitza.category_id:
            cat = self._categories.get(bitza.category_id)
            r.category_name = cat.name if cat else None

        if bitza.retired_by_user_id:
            r.retired_by_display_name = self._user_display_name(bitza.retired_by_user_id)

        r.purchased_by_display_name = self._user_display_name(bitza.purchased_by_user_id)

        if bitza.kind == BitzaKind.mobile:
            open_checkout = self._checkouts.get_open_checkout(bitza.id)
            if open_checkout:
                r.is_checked_out = True
                r.current_holder_display_name = self._user_display_name(open_checkout.holder_id)

        return r

    def _enrich_bitza_list(self, bitza: Bitza) -> BitzaListRead:
        r = BitzaListRead.model_validate(bitza)
        if bitza.parent_id:
            parent = self._bitzas.get(bitza.parent_id)
            r.parent_name = parent.name if parent else None
        team = self._teams.get(bitza.responsible_team_id)
        r.responsible_team_name = team.name if team else ""
        if bitza.category_id:
            cat = self._categories.get(bitza.category_id)
            r.category_name = cat.name if cat else None
        r.child_count = self._bitzas.count_children(bitza.id)
        if bitza.kind == BitzaKind.mobile:
            r.is_checked_out = self._checkouts.get_open_checkout(bitza.id) is not None
        return r

    def _enrich_checkout(self, checkout: Checkout) -> CheckoutRead:
        r = CheckoutRead.model_validate(checkout)
        r.holder_display_name = self._user_display_name(checkout.holder_id)
        return r

    def _enrich_stock_log(self, log: StockLog) -> StockAdjustmentRead:
        r = StockAdjustmentRead.model_validate(log)
        r.user_display_name = self._user_display_name(log.user_id)
        return r

    def _enrich_image(self, image: BitzaImage) -> BitzaImageRead:
        r = BitzaImageRead.model_validate(image)
        r.uploaded_by_display_name = self._user_display_name(image.uploaded_by)
        return r

    def _enrich_audit(self, entry: AuditLog) -> AuditLogRead:
        r = AuditLogRead.model_validate(entry)
        r.user_display_name = self._user_display_name(entry.user_id)
        return r

    def _enrich_category(self, cat: Category) -> CategoryRead:
        r = CategoryRead.model_validate(cat)
        r.bitza_count = self._categories.count_bitzas(cat.id)
        return r
