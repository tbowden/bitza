from fastapi import APIRouter

from app.api.v1.endpoints import audit, auth, bitzas, teams, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(teams.router)
api_router.include_router(bitzas.router)
api_router.include_router(audit.router)
