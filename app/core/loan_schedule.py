"""Shared loan schedule helpers: due dates by lease_payment_type (bi_weekly, monthly, semi_monthly)."""
from datetime import date, datetime, timedelta
from calendar import monthrange

LEASE_PAYMENT_TYPE_BI_WEEKLY = "bi_weekly"
LEASE_PAYMENT_TYPE_MONTHLY = "monthly"
LEASE_PAYMENT_TYPE_SEMI_MONTHLY = "semi_monthly"


def get_bi_weekly_due_dates_range(
    loan_created_at: datetime,
    term_months: float,
    from_date: date,
    to_date: date,
) -> list[datetime]:
    """Return bi-weekly due datetimes for a loan between from_date and to_date (inclusive)."""
    return get_due_dates_range(
        loan_created_at, term_months, LEASE_PAYMENT_TYPE_BI_WEEKLY, from_date, to_date
    )


def get_due_dates_range(
    loan_created_at: datetime,
    term_months: float,
    lease_payment_type: str,
    from_date: date,
    to_date: date,
) -> list[datetime]:
    """
    Return due datetimes for a loan between from_date and to_date (inclusive).
    lease_payment_type: bi_weekly (every 14 days), monthly (same day each month), semi_monthly (1st and 15th).
    """
    due_dates: list[datetime] = []
    created = loan_created_at
    if lease_payment_type == LEASE_PAYMENT_TYPE_BI_WEEKLY:
        first_due = created + timedelta(days=14)
        if first_due.date() > to_date:
            return []
        d = first_due
        max_payments = max(1, int(term_months * 2) + 24)
        for _ in range(max_payments):
            if d.date() > to_date:
                break
            if d.date() >= from_date:
                due_dates.append(d)
            d += timedelta(days=14)
        return due_dates

    if lease_payment_type == LEASE_PAYMENT_TYPE_MONTHLY:
        # First due: one month from created (same day of month, or last day if month shorter)
        day = created.day
        y, m = created.year, created.month
        for _ in range(max(1, int(term_months) + 24)):
            m += 1
            if m > 12:
                m, y = 1, y + 1
            last = monthrange(y, m)[1]
            d = date(y, m, min(day, last))
            if d > to_date:
                break
            if d >= from_date:
                due_dates.append(datetime.combine(d, created.time()))
        return due_dates

    if lease_payment_type == LEASE_PAYMENT_TYPE_SEMI_MONTHLY:
        # 1st and 15th of each month (only on or after loan created)
        created_date = created.date()
        y, m = created_date.year, created_date.month
        for _ in range(max(1, int(term_months * 2) + 48)):
            for day in (1, 15):
                if day > monthrange(y, m)[1]:
                    continue
                d = date(y, m, day)
                if d < created_date:
                    continue
                if d > to_date:
                    return due_dates
                if d >= from_date:
                    due_dates.append(datetime.combine(d, created.time()))
            m += 1
            if m > 12:
                m, y = 1, y + 1
        return due_dates

    # fallback bi-weekly
    return get_bi_weekly_due_dates_range(loan_created_at, term_months, from_date, to_date)
