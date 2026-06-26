"""Minimal API route definitions, logic in user_services"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session


from app.db.session import get_db
from app.schemas.user import AdminUserCreate, AdminUserUpdate, AdminUserResponse, UserListResponse, MeRequest, MeResponse
from app.schemas.utilities import SuccessMessageResponse, ErrorMessageResponse
from app.services.user_service import UserService

router = APIRouter(prefix = "/users", tags = ["users"])


@router.post("/", response_model = AdminUserResponse, status_code = status.HTTP_201_CREATED)
def create_user(
        user_in: AdminUserCreate,
        db: Session = Depends(get_db)
        ):
    """Create new user"""
    return UserService.admin_create_user(db, user_in)


@router.get("/", response_model = UserListResponse, status_code = status.HTTP_200_OK)
def list_users(
        skip: int = 0, 
        limit: int = 100,
        active_only = True,
        db: Session = Depends(get_db),
        ):
    """List users"""
    users, total = UserService.list_users(db, skip, limit, active_only)
    return {
            "items": users,
            "total": total,
            }


@router.get("/{user_id}", response_model = AdminUserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID"""
    return UserService.get_user_by_id(db, user_id)
