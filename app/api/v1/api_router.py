from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.customers.router import router as customers_router
from app.api.v1.users.router import router as users_router
from app.api.v1.admins.router import router as admins_router
from app.api.v1.vehicles.router import router as vehicles_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(customers_router, prefix="/customers", tags=["customers"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(admins_router, prefix="/admins", tags=["admins"])
api_router.include_router(vehicles_router, prefix="/vehicles", tags=["vehicles"])