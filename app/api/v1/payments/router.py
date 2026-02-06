from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.payments.schemas import (
    MakePaymentRequest,
    MakePaymentResponse,
    TransactionHistoryResponse,
)
from app.api.v1.payments.service import PaymentService
from app.core.deps import get_db, get_current_active_admin_user, get_current_customer
from app.models.customer import Customer
from app.models.user import User

router = APIRouter()


# --- Make Payment (customer, card token) ---
@router.post(
    "/",
    response_model=MakePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Make payment",
    description="Process a payment using card token for next or due amount. No raw card details stored.",
    tags=["payments"],
)
async def make_payment(
    data: MakePaymentRequest,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Accepts card_token, processes payment for next or due amount, updates payment status."""
    service = PaymentService(db)
    result = await service.make_payment(
        customer_id=current_customer.id,
        loan_id=data.loan_id,
        card_token=data.card_token,
        payment_type=data.payment_type,
        due_date_iso=data.due_date_iso,
    )
    return MakePaymentResponse(
        success=result["success"],
        message=result["message"],
        transaction=result.get("transaction"),
    )


# --- Transaction History (user) ---
@router.get(
    "/history",
    response_model=TransactionHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="My transaction history",
    description="Returns payment history for the logged-in user.",
    tags=["payments"],
)
async def my_transaction_history(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Paginated transaction history for the current customer."""
    service = PaymentService(db)
    items, total = await service.list_my_transactions(
        customer_id=current_customer.id,
        skip=skip,
        limit=limit,
    )
    return TransactionHistoryResponse(items=items, total=total)


# --- Transaction History (admin) ---
@router.get(
    "/transactions",
    response_model=TransactionHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="All transactions (admin)",
    description="Returns transaction history for all users with optional filters.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def admin_transaction_history(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    loan_id: Optional[UUID] = Query(None, description="Filter by loan ID"),
    from_date: Optional[date] = Query(None, description="Filter from date (payment_date)"),
    to_date: Optional[date] = Query(None, description="Filter to date (payment_date)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Paginated transaction history with filters."""
    service = PaymentService(db)
    items, total = await service.list_transactions_admin(
        customer_id=customer_id,
        loan_id=loan_id,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )
    return TransactionHistoryResponse(items=items, total=total)
