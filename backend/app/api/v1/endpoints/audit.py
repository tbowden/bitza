from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_bitza_service, get_current_user
from app.models.user import User
from app.schemas.audit import AuditLogRead
from app.services.bitza_service import BitzaService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/",
    response_model=list[AuditLogRead],
    summary="View audit log (admin/superuser only)",
)
def list_audit(
    entity_type: Optional[str] = Query(None, description="Filter by entity type, e.g. 'bitza'"),
    entity_id: Optional[str] = Query(None, description="Filter by a specific entity ID"),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    svc: BitzaService = Depends(get_bitza_service),
) -> list[AuditLogRead]:
    return svc.list_audit(
        actor=current_user, entity_type=entity_type, entity_id=entity_id, limit=limit
    )
