import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.v1.payments.schemas import (
    AdminTransactionHistoryResponse,
    MakePaymentRequest,
    MakePaymentResponse,
    NotificationListResponse,
    OverduePaymentsResponse,
    TransactionHistoryResponse,
    TransactionItem,
    UpdatePaymentStatusRequest,
)
from app.api.v1.payments.service import PaymentService
from app.core.deps import get_db, get_current_active_admin_user, get_current_customer
from app.core.exceptions import AppException
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
    # Log request parameters (mask card_token for security)
    card_preview = f"{data.card_token[:20]}...({len(data.card_token)} chars)" if len(data.card_token) > 20 else "***"
    logger.info(
        "POST /payments/ request: loan_id=%s payment_type=%s due_date_iso=%s card_token=%s",
        data.loan_id,
        data.payment_type,
        data.due_date_iso,
        card_preview,
    )
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


# --- Notifications (customer) ---
@router.get(
    "/my-notifications",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all notifications (customer)",
    description="Returns all notifications for the logged-in customer (payment received, confirmed, due tomorrow, overdue). Use skip/limit for pagination.",
    tags=["payments"],
)
async def my_notifications(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
):
    """Get all notifications of the customer."""
    service = PaymentService(db)
    items, total = await service.list_notifications_for_customer(
        customer_id=current_customer.id,
        skip=skip,
        limit=limit,
    )
    return NotificationListResponse(items=items, total=total)


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


# --- Admin: update payment status (triggers Payment Confirmed notification) ---
@router.patch(
    "/{payment_id}/status",
    response_model=TransactionItem,
    status_code=status.HTTP_200_OK,
    summary="Update payment status (admin)",
    description="Admin updates payment status to completed or failed. Sends 'Payment Confirmed' notification when set to completed.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def update_payment_status(
    payment_id: UUID,
    data: UpdatePaymentStatusRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update payment status; sends payment_confirmed notification when status is completed."""
    service = PaymentService(db)
    updated = await service.update_payment_status_admin(payment_id=payment_id, status=data.status)
    if not updated:
        AppException().raise_404("Payment not found")
    return updated


# --- Admin: Overdue Accounts ---
@router.get(
    "/overdue",
    response_model=OverduePaymentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Overdue accounts (admin)",
    description="Overdue Accounts: list of overdue installments, overdue payment count, total overdue amount, and average overdue days.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def overdue_payments(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
):
    """Overdue Accounts: list of overdue installments plus total count, total overdue amount, avg overdue days."""
    service = PaymentService(db)
    items, total_count, total_outstanding, avg_days = await service.list_overdue_for_admin(
        skip=skip,
        limit=limit,
    )
    return OverduePaymentsResponse(
        items=items,
        total_overdue_payments=total_count,
        total_outstanding_amount=round(total_outstanding, 2),
        avg_overdue_days=round(avg_days, 2),
    )


# --- Notifications (admin) ---
@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all notifications (admin)",
    description="Returns all notifications (all customers). Optionally filter by customer_id. Use skip/limit for pagination.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def admin_notifications(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
):
    """Get all notifications; admin sees all (or filtered by customer)."""
    service = PaymentService(db)
    items, total = await service.list_notifications_admin(
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )
    return NotificationListResponse(items=items, total=total)


# --- Transaction History (admin) ---
@router.get(
    "/transactions",
    response_model=AdminTransactionHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="All transactions (admin)",
    description="Returns transaction history with summary: total, total_amount, completed_count, pending_count, failed_count.",
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
    """Paginated transaction history with summary stats for dashboard (Total, $amount, Completed, Pending, Failed)."""
    service = PaymentService(db)
    items, total, total_amount, completed_count, failed_count = await service.list_transactions_admin(
        customer_id=customer_id,
        loan_id=loan_id,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )
    return AdminTransactionHistoryResponse(
        items=items,
        total=total,
        total_amount=round(total_amount, 2),
        completed_count=completed_count,
        pending_count=0,
        failed_count=failed_count,
    )
