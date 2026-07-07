from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import UserNotFoundError, UserSuspendedError
from app.db.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.bitza_image_repository import BitzaImageRepository
from app.repositories.bitza_repository import BitzaRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.checkout_repository import CheckoutRepository
from app.repositories.stock_log_repository import StockLogRepository
from app.repositories.team_repository import TeamRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.bitza_service import BitzaService
from app.services.team_service import TeamService
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
# Phase 2 (rebuilt) — Repository providers
# ---------------------------------------------------------------------------

def get_category_repository(db: Session = Depends(get_db)) -> CategoryRepository:
    return CategoryRepository(db)


def get_team_repository(db: Session = Depends(get_db)) -> TeamRepository:
    return TeamRepository(db)


def get_bitza_repository(db: Session = Depends(get_db)) -> BitzaRepository:
    return BitzaRepository(db)


def get_checkout_repository(db: Session = Depends(get_db)) -> CheckoutRepository:
    return CheckoutRepository(db)


def get_stock_log_repository(db: Session = Depends(get_db)) -> StockLogRepository:
    return StockLogRepository(db)


def get_bitza_image_repository(db: Session = Depends(get_db)) -> BitzaImageRepository:
    return BitzaImageRepository(db)


def get_audit_repository(db: Session = Depends(get_db)) -> AuditRepository:
    return AuditRepository(db)


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
# Phase 2 (rebuilt) — Service providers
# ---------------------------------------------------------------------------

def get_team_service(
    db: Session = Depends(get_db),
    team_repo: TeamRepository = Depends(get_team_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    bitza_repo: BitzaRepository = Depends(get_bitza_repository),
) -> TeamService:
    return TeamService(
        db=db, team_repo=team_repo, user_repo=user_repo, bitza_repo=bitza_repo
    )


def get_bitza_service(
    db: Session = Depends(get_db),
    bitza_repo: BitzaRepository = Depends(get_bitza_repository),
    team_repo: TeamRepository = Depends(get_team_repository),
    category_repo: CategoryRepository = Depends(get_category_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    checkout_repo: CheckoutRepository = Depends(get_checkout_repository),
    stock_log_repo: StockLogRepository = Depends(get_stock_log_repository),
    image_repo: BitzaImageRepository = Depends(get_bitza_image_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
) -> BitzaService:
    return BitzaService(
        db=db,
        bitza_repo=bitza_repo,
        team_repo=team_repo,
        category_repo=category_repo,
        user_repo=user_repo,
        checkout_repo=checkout_repo,
        stock_log_repo=stock_log_repo,
        image_repo=image_repo,
        audit_repo=audit_repo,
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
