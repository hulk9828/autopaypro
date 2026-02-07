from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.customers.router import router as customers_router
from app.api.v1.users.router import router as users_router
from app.api.v1.admins.router import router as admins_router
from app.api.v1.vehicles.router import router as vehicles_router
from app.api.v1.dashboard.router import router as dashboard_router
from app.api.v1.sales.router import router as sales_router
from app.api.v1.contents.router import router as contents_router
from app.api.v1.calendar.router import router as calendar_router
from app.api.v1.notifications.router import router as notifications_router
from app.api.v1.payments.router import router as payments_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(customers_router, prefix="/customers")  # Tags are defined in the router itself
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(admins_router, prefix="/admins", tags=["admins"])
api_router.include_router(vehicles_router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["admin-dashboard"])
api_router.include_router(sales_router, prefix="/sales", tags=["sales"])
api_router.include_router(contents_router, prefix="/contents", tags=["content"])
api_router.include_router(calendar_router, prefix="/calendar", tags=["calendar"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])