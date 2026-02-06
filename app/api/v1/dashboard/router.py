from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dashboard.schemas import DashboardResponse, RecentPaymentsResponse
from app.api.v1.dashboard.service import DashboardService
from app.core.deps import get_db, get_current_active_admin_user
from app.models.user import User

router = APIRouter()


@router.get(
    "/",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get admin dashboard data",
    description="Get complete dashboard data including summary statistics, recent payments, overdue accounts, and upcoming payments. Admin only.",
    tags=["admin-dashboard"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_dashboard(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get admin dashboard data. Only admins can access this endpoint."""
    dashboard_service = DashboardService(db)
    dashboard_data = await dashboard_service.get_dashboard_data()
    return dashboard_data


@router.get(
    "/recent-payments",
    response_model=RecentPaymentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Recent payments (admin dashboard)",
    description="Get recent payments for the admin dashboard. Admin only.",
    tags=["admin-dashboard"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_recent_payments(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
):
    """Get recent payments for the admin dashboard."""
    dashboard_service = DashboardService(db)
    recent_payments = await dashboard_service.get_recent_payments(limit=limit)
    return RecentPaymentsResponse(recent_payments=recent_payments)
