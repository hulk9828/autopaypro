import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.v1.payments.schemas import (
    AdminTransactionHistoryResponse,
    BulkOverdueReminderRequest,
    BulkOverdueReminderResponse,
    CheckoutRequest,
    CheckoutResponse,
    DueCustomersResponse,
    DueInstallmentsResponse,
    GetCheckoutResponse,
    MakePaymentRequest,
    MakePaymentResponse,
    NotificationListResponse,
    OverduePaymentsResponse,
    PaymentSummaryResponse,
    PublicPaymentRequest,
    RecordManualPaymentRequest,
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


# --- Checkout: create (admin only) and get (public) ---
@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Create checkout (admin)",
    description="Create a checkout: get payment details for a due installment (amount, Stripe client_secret, payment_intent_id). Identify customer by email or customer_id. JWT protected, admin only.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def create_checkout(
    data: CheckoutRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create checkout (admin only): returns payment details and Stripe PaymentIntent client_secret for client-side payment form."""
    service = PaymentService(db)
    result = await service.get_checkout(
        loan_id=data.loan_id,
        payment_type=data.payment_type,
        due_date_iso=data.due_date_iso,
        email=data.email,
        customer_id=data.customer_id,
    )
    return CheckoutResponse(**result)


@router.get(
    "/checkout/{payment_intent_id}",
    response_model=GetCheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Get checkout (no auth)",
    description="Get checkout details by Stripe PaymentIntent ID (e.g. to poll status or re-display). Returns amount, status, client_secret, and metadata. No auth token required.",
    tags=["payments"],
)
async def get_checkout(
    payment_intent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get checkout by payment_intent_id (from create checkout response). Use to check status (e.g. succeeded) or re-use client_secret."""
    service = PaymentService(db)
    result = await service.get_checkout_by_payment_intent_id(payment_intent_id)
    return GetCheckoutResponse(**result)


# --- Public payment (no auth): confirm PaymentIntent with card token ---
@router.post(
    "/pay",
    response_model=MakePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm payment (no auth)",
    description="Confirm payment using payment_intent_id from checkout and card_token (Stripe PaymentMethod/token). No auth token required.",
    tags=["payments"],
)
async def confirm_payment(
    data: PublicPaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm Stripe PaymentIntent with card; records payment and returns transaction."""
    service = PaymentService(db)
    result = await service.confirm_public_payment(
        payment_intent_id=data.payment_intent_id,
        card_token=data.card_token,
    )
    return MakePaymentResponse(
        success=result["success"],
        message=result["message"],
        transaction=result.get("transaction"),
    )


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


# --- Admin: record manual payment ---
@router.post(
    "/record-manual",
    response_model=TransactionItem,
    status_code=status.HTTP_200_OK,
    summary="Record manual payment (admin)",
    description="Admin records a manual payment received from a customer: select customer, loan, due date, amount paid, payment method, and optional note.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def record_manual_payment(
    data: RecordManualPaymentRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin records a payment received manually (cash, check, etc.) from a customer."""
    service = PaymentService(db)
    transaction = await service.record_manual_payment_admin(
        customer_id=data.customer_id,
        loan_id=data.loan_id,
        due_date_iso=data.due_date_iso,
        amount=data.amount,
        payment_method=data.payment_method,
        note=data.note,
    )
    if not transaction:
        AppException().raise_400(
            "Invalid or already paid due date. Ensure customer belongs to loan and the due date is an unpaid scheduled installment."
        )
    return transaction


# --- Admin: bulk email + notification to customers with overdue payments ---
@router.post(
    "/bulk-overdue-reminder",
    response_model=BulkOverdueReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk overdue reminder (admin)",
    description="Send email and push notification to all customers who have at least one overdue payment. Optional custom subject/body for email and title/body for notification.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def bulk_overdue_reminder(
    data: BulkOverdueReminderRequest | None = None,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Send bulk email and push notification to all customers with overdue installments."""
    if data is None:
        data = BulkOverdueReminderRequest()
    service = PaymentService(db)
    result = await service.send_bulk_overdue_reminder(
        email_subject=data.email_subject,
        email_body_override=data.email_body_override,
        notification_title=data.notification_title,
        notification_body=data.notification_body,
    )
    return BulkOverdueReminderResponse(**result)


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


# --- Admin: Customers with dues (for create checkout) ---
@router.get(
    "/due-customers",
    response_model=DueCustomersResponse,
    status_code=status.HTTP_200_OK,
    summary="List customers with due payments (admin)",
    description="List customers who have unpaid dues, with loan_id, email, and next due. Use each item to call create checkout (POST /checkout) with loan_id and email or customer_id, payment_type=next or due.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def due_customers(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    loan_id: Optional[UUID] = Query(None, description="Filter by loan ID"),
    search: Optional[str] = Query(None, description="Search by customer name, email, or phone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
):
    """List customers with at least one unpaid due; includes everything needed for create checkout."""
    service = PaymentService(db)
    items, total = await service.list_due_customers_admin(
        customer_id=customer_id,
        loan_id=loan_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    return DueCustomersResponse(items=items, total=total)


# --- Admin: List due installments (for create checkout per due) ---
@router.get(
    "/due-installments",
    response_model=DueInstallmentsResponse,
    status_code=status.HTTP_200_OK,
    summary="List due installments (admin)",
    description="List every unpaid due installment with loan_id, customer, due_date_iso, amount. Use each item to call create checkout (POST /checkout) with loan_id, email or customer_id, payment_type=due, due_date_iso.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def due_installments(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    loan_id: Optional[UUID] = Query(None, description="Filter by loan ID"),
    search: Optional[str] = Query(None, description="Search by customer name, email, or phone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
):
    """List all unpaid due installments with fields needed for create checkout (payment_type=due, due_date_iso)."""
    service = PaymentService(db)
    items, total, total_amount = await service.list_due_installments_admin(
        customer_id=customer_id,
        loan_id=loan_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    return DueInstallmentsResponse(
        items=items,
        total=total,
        total_amount=round(total_amount, 2),
    )


# --- Admin: Payment Summary (paid, unpaid, overdue, totals, search) ---
@router.get(
    "/summary",
    response_model=PaymentSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Payment summary (admin)",
    description="Get paid dues, unpaid dues, overdue payments, total collected, pending, overdue, total payment left. Search by customer name/email/phone.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def payment_summary(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    loan_id: Optional[UUID] = Query(None, description="Filter by loan ID"),
    search: Optional[str] = Query(None, description="Search by customer name, email, or phone"),
):
    """Payment summary: paid, unpaid, overdue lists; total collected, pending, overdue, total payment left; search."""
    service = PaymentService(db)
    data = await service.get_payment_summary_admin(
        customer_id=customer_id,
        loan_id=loan_id,
        search=search,
    )
    return PaymentSummaryResponse(
        paid_dues=data["paid_dues"],
        unpaid_dues=data["unpaid_dues"],
        overdue_payments=data["overdue_payments"],
        total_collected_amount=round(data["total_collected_amount"], 2),
        pending_amount=round(data["pending_amount"], 2),
        overdue_amount=round(data["overdue_amount"], 2),
        total_payment_left=round(data["total_payment_left"], 2),
    )


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
