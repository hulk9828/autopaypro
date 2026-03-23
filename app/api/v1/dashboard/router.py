from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dashboard.schemas import (
    DashboardResponse,
    RecentPaymentsResponse,
    CustomersWithPendingLoanResponse,
)
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


@router.get(
    "/pending-loans",
    response_model=CustomersWithPendingLoanResponse,
    status_code=status.HTTP_200_OK,
    summary="Customers with pending loan amount",
    description="List customers who have pending loan amount (remaining balance). Returns customer details, loan_id, and pending EMIs (due date and amount) each user has to pay. Admin only.",
    tags=["admin-dashboard"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_customers_with_pending_loan(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all customers with pending loan amount: customer details, loan ID, and pending EMIs."""
    dashboard_service = DashboardService(db)
    return await dashboard_service.get_customers_with_pending_loan()
