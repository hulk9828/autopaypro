from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sales.schemas import (
    CreateLeaseRequest,
    LeaseResponse,
    LeasesListResponse,
    BiWeeklyEstimateRequest,
    BiWeeklyEstimateResponse,
)
from app.api.v1.sales.service import SaleService
from app.core.deps import get_db, get_current_active_admin_user
from app.models.user import User

router = APIRouter()


@router.post(
    "/estimate",
    response_model=BiWeeklyEstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate bi-weekly payment",
    description="Calculate estimated bi-weekly payment for a lease without creating it.",
    tags=["leases"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def estimate_bi_weekly_payment(
    data: BiWeeklyEstimateRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns estimated bi-weekly payment for given lease amount, down payment, term, and rate."""
    service = SaleService(db)
    return service.get_bi_weekly_estimate(data)


@router.post(
    "/",
    response_model=LeaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new lease",
    description="Set up a new vehicle lease with loan terms for an existing customer. Vehicle is marked as leased.",
    tags=["leases"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def create_lease(
    data: CreateLeaseRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new lease: select customer, select available vehicle, set lease amount,
    down payment, term, and interest rate. Creates loan and links vehicle to customer (lease period stored).
    """
    service = SaleService(db)
    return await service.create_lease(data)


@router.get(
    "/",
    response_model=LeasesListResponse,
    status_code=status.HTTP_200_OK,
    summary="List leases",
    description="List all leases (loans) with summary stats. Search by customer or vehicle; optionally filter by customer_id.",
    tags=["leases"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def list_leases(
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    search: Optional[str] = Query(None, description="Search by customer name or vehicle (make, model, year)"),
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List leases with dashboard summary. Search by customer or vehicle; filter by customer_id if provided."""
    service = SaleService(db)
    return await service.get_leases(customer_id=customer_id, search=search)


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export leases to Excel",
    description="Download leases data as an Excel (.xlsx) file. Same filters as list: customer_id, search.",
    tags=["leases"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def export_leases_excel(
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    search: Optional[str] = Query(None, description="Search by customer name or vehicle (make, model, year)"),
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Export leases data to Excel (.xlsx). Admin only."""
    service = SaleService(db)
    content = await service.export_leases_to_excel(customer_id=customer_id, search=search)
    filename = "leases_export.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
