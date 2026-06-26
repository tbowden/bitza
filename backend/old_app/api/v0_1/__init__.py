"""API v0.1 router"""
from fastapi import APIRouter
from app.api.v0_1 import users
from app.api.v0_1 import auth

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(users.router)
api_router.include_router(auth.router)

# Add more routers as you create them:
# api_router.include_router(products.router)
# api_router.include_router(orders.router)
