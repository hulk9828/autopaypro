import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.v1.payments.schemas import (
    AdminTransactionHistoryResponse,
    BulkOverdueReminderResponse,
    CompleteCheckoutRequest,
    CompleteCheckoutResponse,
    CreateCheckoutRequest,
    CreateCheckoutResponse,
    DueCustomersResponse,
    DueInstallmentsResponse,
    GetCheckoutResponse,
    NotificationListResponse,
    OverduePaymentsResponse,
    PaymentReceiptResponse,
    PaymentSummaryResponse,
    RecordManualPaymentRequest,
    TransactionHistoryResponse,
    TransactionItem,
    UpdatePaymentErrorResponse,
    UpdatePaymentRequest,
    UpdatePaymentResponse,
    UpdatePaymentStatusRequest,
    WaiveOverdueRequest,
    WaiveOverdueByCustomerRequest,
)
from app.api.v1.payments.service import PaymentService
from app.core.deps import get_db, get_current_active_admin_user, get_current_customer
from app.core.exceptions import AppException
from app.models.customer import Customer
from app.models.user import User

router = APIRouter()


# --- Checkout: create (admin), fetch by token, complete (no auth for fetch/complete) ---
@router.post(
    "/checkout",
    response_model=CreateCheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Create checkout (admin)",
    description="Create a checkout and send a payment link to the customer's email. Customer can open the link and pay on the frontend, then complete via POST /checkout/{token}/complete.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def create_checkout(
    data: CreateCheckoutRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin creates checkout; payment link is emailed to the customer."""
    service = PaymentService(db)
    result = await service.create_checkout_admin(
        customer_id=data.customer_id,
        loan_id=data.loan_id,
        amount=data.amount,
    )
    return CreateCheckoutResponse(**result)


@router.get(
    "/checkout/{token}",
    response_model=GetCheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Get checkout by token (no auth)",
    description="Fetch checkout details by token (from the payment link). Use this when the user opens the payment link to display amount, vehicle, and customer info. Returns 404 if token invalid or expired.",
    tags=["payments"],
)
async def get_checkout(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get checkout details for the payment page. No auth required."""
    service = PaymentService(db)
    result = await service.get_checkout_by_token(token)
    if result is None:
        AppException().raise_404("Checkout not found or link has expired")
    return GetCheckoutResponse(**result)


@router.post(
    "/checkout/{token}/complete",
    response_model=CompleteCheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete checkout (no auth)",
    description="Record payment for this checkout (user has paid on frontend). Send optional amount in body; if omitted, checkout amount is used. Returns payment_id and remaining_balance.",
    tags=["payments"],
    responses={400: {"description": "Checkout not found, expired, or already completed"}},
)
async def complete_checkout(
    token: str,
    data: Optional[CompleteCheckoutRequest] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """Complete checkout: record the payment and mark checkout as completed. No auth required."""
    service = PaymentService(db)
    amount = data.amount if data is not None else None
    result = await service.complete_checkout(token, amount=amount)
    if not result.get("success"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": result.get("message", "Invalid request")},
        )
    return CompleteCheckoutResponse(
        success=True,
        message=result["message"],
        payment_id=result["payment_id"],
        remaining_balance=result["remaining_balance"],
    )


# --- External payment (no auth): record payment from external system ---
@router.post(
    "/update-payment",
    response_model=UpdatePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Record payment (external system)",
    description="Record a payment from an external payment system. No authentication required. Provide customer_id, loan_id, and amount. Payment is applied to earliest unpaid installments. Returns payment_id and remaining_balance on success.",
    tags=["payments"],
    responses={
        200: {"description": "Payment recorded successfully", "model": UpdatePaymentResponse},
        400: {"description": "Validation error", "model": UpdatePaymentErrorResponse},
    },
)
async def update_payment(
    data: UpdatePaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a payment (customer_id, loan_id, amount). Used by external payment systems. No auth required."""
    service = PaymentService(db)
    result = await service.record_external_payment(
        customer_id=data.customer_id,
        loan_id=data.loan_id,
        amount=data.amount,
    )
    if not result.get("success"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=UpdatePaymentErrorResponse(
                success=False,
                message=result.get("message", "Invalid request"),
            ).model_dump(),
        )
    return UpdatePaymentResponse(
        success=True,
        message=result["message"],
        payment_id=result["payment_id"],
        remaining_balance=result["remaining_balance"],
    )


@router.post(
    "/update-loan-payment",
    response_model=UpdatePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update loan payment (no auth)",
    description="Update loan payment without bearer token using customer_id, loan_id, and amount. This is an alias of update-payment for external clients.",
    tags=["payments"],
    responses={
        200: {"description": "Payment recorded successfully", "model": UpdatePaymentResponse},
        400: {"description": "Validation error", "model": UpdatePaymentErrorResponse},
    },
)
async def update_loan_payment(
    data: UpdatePaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """No-auth endpoint to record payment by customer_id + loan_id + amount."""
    service = PaymentService(db)
    result = await service.record_external_payment(
        customer_id=data.customer_id,
        loan_id=data.loan_id,
        amount=data.amount,
    )
    if not result.get("success"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=UpdatePaymentErrorResponse(
                success=False,
                message=result.get("message", "Invalid request"),
            ).model_dump(),
        )
    return UpdatePaymentResponse(
        success=True,
        message=result["message"],
        payment_id=result["payment_id"],
        remaining_balance=result["remaining_balance"],
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


# --- Customer: Get my receipt for a payment ---
@router.get(
    "/my-receipt/{payment_id}",
    response_model=PaymentReceiptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my payment receipt (customer)",
    description="Get receipt data for one of your payments. Customer can only access their own receipts.",
    tags=["payments"],
)
async def my_payment_receipt(
    payment_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Returns receipt data for the given payment ID (only if it belongs to the current customer)."""
    service = PaymentService(db)
    receipt = await service.get_receipt_for_customer(payment_id, current_customer.id)
    if not receipt:
        AppException().raise_404("Payment not found or you do not have access to this receipt")
    return PaymentReceiptResponse(**receipt)


# --- Admin: record manual payment ---
@router.post(
    "/record-manual",
    response_model=TransactionItem,
    status_code=status.HTTP_200_OK,
    summary="Record manual payment (admin)",
    description="Admin records a manual payment using customer_id, loan_id, amount, payment_method, and optional note. Payment date is when admin records it.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def record_manual_payment(
    data: RecordManualPaymentRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin records a payment manually (cash/check/online/card)."""
    service = PaymentService(db)
    transaction = await service.record_manual_payment_admin(
        customer_id=data.customer_id,
        loan_id=data.loan_id,
        amount=data.amount,
        payment_method=data.payment_method,
        note=data.note,
    )
    if not transaction:
        AppException().raise_400(
            "Invalid request. Ensure customer belongs to loan and amount is greater than 0."
        )
    return transaction


# --- Admin: waive overdue installment ---
@router.post(
    "/waive-overdue",
    response_model=TransactionItem,
    status_code=status.HTTP_200_OK,
    summary="Waive overdue installment (admin)",
    description="Waive an unpaid installment for a loan. Creates a zero-amount completed payment marked as waived; the due is then considered satisfied.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def waive_overdue_installment(
    data: WaiveOverdueRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Waive one overdue (or any unpaid) installment: loan_id + due_date_iso. Optional note for the waiver."""
    service = PaymentService(db)
    result = await service.waive_overdue_installment_admin(
        loan_id=data.loan_id,
        due_date_iso=data.due_date_iso,
        note=data.note,
    )
    if not result:
        AppException().raise_400(
            "Invalid or already paid/waived due date. Check loan_id and due_date_iso (must be a scheduled unpaid installment)."
        )
    return result


@router.post(
    "/waive-overdue-by-customer",
    response_model=TransactionItem,
    status_code=status.HTTP_200_OK,
    summary="Waive earliest overdue by customer and loan (admin)",
    description="Waive the earliest overdue installment for a customer's loan. Send customer_id and loan_id; the oldest unpaid overdue due is waived.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def waive_overdue_by_customer(
    data: WaiveOverdueByCustomerRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Waive the earliest overdue payment for the given customer_id and loan_id."""
    service = PaymentService(db)
    result = await service.waive_earliest_overdue_by_customer_loan(
        customer_id=data.customer_id,
        loan_id=data.loan_id,
        note=data.note,
    )
    if not result:
        AppException().raise_400(
            "No overdue installment found for this customer and loan, or loan does not belong to customer, or loan is closed."
        )
    return result


# --- Admin: bulk email + notification to customers with overdue payments ---
@router.post(
    "/bulk-overdue-reminder",
    response_model=BulkOverdueReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk overdue reminder (admin)",
    description="Send default overdue alert email and push notification to all customers who have at least one overdue payment. No request body; uses default message.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def bulk_overdue_reminder(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Send bulk email and push notification to all customers with overdue installments (default overdue alert message)."""
    service = PaymentService(db)
    result = await service.send_bulk_overdue_reminder()
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


# --- Admin: Get receipt for a payment ---
@router.get(
    "/{payment_id}/receipt",
    response_model=PaymentReceiptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment receipt (admin)",
    description="Get receipt data for a payment (customer, amount, date, vehicle, etc.) for display or print. Admin only.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_payment_receipt(
    payment_id: UUID,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns receipt data for the given payment ID."""
    service = PaymentService(db)
    receipt = await service.get_receipt_for_payment(payment_id)
    if not receipt:
        AppException().raise_404("Payment not found")
    return PaymentReceiptResponse(**receipt)


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
        items=data["items"],
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
    "/transactions/export",
    status_code=status.HTTP_200_OK,
    summary="Export transactions to Excel",
    description="Download transactions data as an Excel (.xlsx) file. Same filters as list: customer_id, loan_id, from_date, to_date.",
    tags=["payments"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def export_transactions_excel(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    loan_id: Optional[UUID] = Query(None, description="Filter by loan ID"),
    from_date: Optional[date] = Query(None, description="Filter from date (payment_date)"),
    to_date: Optional[date] = Query(None, description="Filter to date (payment_date)"),
):
    """Export transactions to Excel (.xlsx). Admin only."""
    service = PaymentService(db)
    content = await service.export_transactions_to_excel(
        customer_id=customer_id,
        loan_id=loan_id,
        from_date=from_date,
        to_date=to_date,
    )
    filename = "transactions_export.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
