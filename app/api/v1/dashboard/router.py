from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dashboard.schemas import DashboardResponse
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
    dependencies=[Depends(get_current_active_admin_user)]
)
async def get_dashboard(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get admin dashboard data. Only admins can access this endpoint."""
    dashboard_service = DashboardService(db)
    dashboard_data = await dashboard_service.get_dashboard_data()
    return dashboard_data
