from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.calendar.schemas import PaymentCalendarResponse
from app.api.v1.calendar.service import CalendarService
from app.core.deps import get_db, get_current_active_admin_user
from app.models.user import User

router = APIRouter()


@router.get(
    "/payment",
    response_model=PaymentCalendarResponse,
    summary="Payment calendar by date",
    description="Get paid, pending, and overdue payments for a calendar date. Tracks due dates and payment schedules.",
    tags=["calendar"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_payment_calendar(
    date_param: date = Query(..., alias="date", description="Calendar date (YYYY-MM-DD)"),
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns paid (due on this date and paid), pending (due on this date not paid), and overdue (due before this date not paid) with counts and lists."""
    service = CalendarService(db)
    return await service.get_payment_calendar(date_param)
