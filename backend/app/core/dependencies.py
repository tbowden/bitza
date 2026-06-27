from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import UserNotFoundError, UserSuspendedError
from app.db.session import get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.location_repository import LocationRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.services.asset_service import AssetService
from app.services.auth_service import AuthService
from app.services.location_service import LocationService
from app.services.user_service import UserService

_bearer = HTTPBearer()


# ---------------------------------------------------------------------------
# Phase 1 — Repository providers
# ---------------------------------------------------------------------------

def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_token_repository(db: Session = Depends(get_db)) -> TokenRepository:
    return TokenRepository(db)


# ---------------------------------------------------------------------------
# Phase 2 — Repository providers
# ---------------------------------------------------------------------------

def get_location_repository(db: Session = Depends(get_db)) -> LocationRepository:
    return LocationRepository(db)


def get_category_repository(db: Session = Depends(get_db)) -> CategoryRepository:
    return CategoryRepository(db)


def get_asset_repository(db: Session = Depends(get_db)) -> AssetRepository:
    return AssetRepository(db)


# ---------------------------------------------------------------------------
# Phase 1 — Service providers
# ---------------------------------------------------------------------------

def get_auth_service(
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: TokenRepository = Depends(get_token_repository),
) -> AuthService:
    return AuthService(db=db, user_repo=user_repo, token_repo=token_repo)


def get_user_service(
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: TokenRepository = Depends(get_token_repository),
) -> UserService:
    return UserService(db=db, user_repo=user_repo, token_repo=token_repo)


# ---------------------------------------------------------------------------
# Phase 2 — Service providers
# ---------------------------------------------------------------------------

def get_location_service(
    db: Session = Depends(get_db),
    location_repo: LocationRepository = Depends(get_location_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    asset_repo: AssetRepository = Depends(get_asset_repository),
) -> LocationService:
    return LocationService(
        db=db,
        location_repo=location_repo,
        user_repo=user_repo,
        asset_repo=asset_repo,
    )


def get_asset_service(
    db: Session = Depends(get_db),
    asset_repo: AssetRepository = Depends(get_asset_repository),
    cat_repo: CategoryRepository = Depends(get_category_repository),
    loc_repo: LocationRepository = Depends(get_location_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    loc_service: LocationService = Depends(get_location_service),
) -> AssetService:
    return AssetService(
        db=db,
        asset_repo=asset_repo,
        cat_repo=cat_repo,
        loc_repo=loc_repo,
        user_repo=user_repo,
        loc_service=loc_service,
    )


# ---------------------------------------------------------------------------
# Current-user resolver
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    auth_service: AuthService = Depends(get_auth_service),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """
    Validate the Bearer access token and return the active User.
    Raises InvalidTokenError, UserNotFoundError, or UserSuspendedError.
    """
    user_id = auth_service.get_current_user_id_from_access_token(
        credentials.credentials
    )
    user = user_repo.get_by_id(user_id)
    if not user:
        raise UserNotFoundError("Authenticated user no longer exists")
    if not user.is_active:
        raise UserSuspendedError()
    return user
