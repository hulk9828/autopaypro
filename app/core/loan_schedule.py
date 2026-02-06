"""Shared loan schedule helpers (bi-weekly due dates)."""
from datetime import date, datetime, timedelta


def get_bi_weekly_due_dates_range(
    loan_created_at: datetime,
    term_months: float,
    from_date: date,
    to_date: date,
) -> list[datetime]:
    """Return bi-weekly due datetimes for a loan between from_date and to_date (inclusive)."""
    first_due = loan_created_at + timedelta(days=14)
    if first_due.date() > to_date:
        return []
    due_dates: list[datetime] = []
    d = first_due
    max_payments = max(1, int(term_months * 2) + 24)
    for _ in range(max_payments):
        if d.date() > to_date:
            break
        if d.date() >= from_date:
            due_dates.append(d)
        d += timedelta(days=14)
    return due_dates
