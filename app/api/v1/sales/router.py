from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sales.schemas import (
    CreateSaleRequest,
    SaleResponse,
    SalesListResponse,
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
    description="Calculate estimated bi-weekly payment for a sale without creating it.",
    tags=["sales"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def estimate_bi_weekly_payment(
    data: BiWeeklyEstimateRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns estimated bi-weekly payment for given sale amount, down payment, term, and rate."""
    service = SaleService(db)
    return service.get_bi_weekly_estimate(data)


@router.post(
    "/",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new sale",
    description="Set up a new vehicle sale with loan terms for an existing customer.",
    tags=["sales"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def create_sale(
    data: CreateSaleRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new sale: select customer, select available vehicle, set sale amount,
    down payment, term, and interest rate. Creates loan and links vehicle to customer.
    """
    service = SaleService(db)
    return await service.create_sale(data)


@router.get(
    "/",
    response_model=SalesListResponse,
    status_code=status.HTTP_200_OK,
    summary="List sales",
    description="List all sales (loans) with summary stats. Search by customer or vehicle; optionally filter by customer_id.",
    tags=["sales"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def list_sales(
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    search: Optional[str] = Query(None, description="Search by customer name or vehicle (make, model, year)"),
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List sales with dashboard summary. Search by customer or vehicle; filter by customer_id if provided."""
    service = SaleService(db)
    return await service.get_sales(customer_id=customer_id, search=search)
