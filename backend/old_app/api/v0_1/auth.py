"""Auth endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
#router = APIRouter(prefix="/auth")


@router.post("/login", response_model=TokenPair)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    return AuthService.login(
        db=db,
        email=login_data.email,
        password=login_data.password,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db),
):
    return AuthService.refresh(
        db=db,
        refresh_token=refresh_data.refresh_token,
    )

