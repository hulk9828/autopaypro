from enum import Enum


class Role(str, Enum):
    user = "user"
    admin = "admin"


class VehicleStatus(str, Enum):
    available = "available"
    leased = "leased"
    # Legacy: 'sold' may exist in DB; treat as leased. New assignments use leased.
    sold = "sold"


class VehicleCondition(str, Enum):
    bad = "bad"
    good = "good"
    excellent = "excellent"


class AccountStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class LeasePaymentType(str, Enum):
    bi_weekly = "bi_weekly"
    monthly = "monthly"
    semi_monthly = "semi_monthly"
