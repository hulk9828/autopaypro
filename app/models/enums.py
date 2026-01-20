from enum import Enum


class Role(str, Enum):
    user = "user"
    admin = "admin"


class VehicleStatus(str, Enum):
    available = "available"
    sold = "sold"


class VehicleCondition(str, Enum):
    bad = "bad"
    good = "good"
    excellent = "excellent"


class AccountStatus(str, Enum):
    active = "active"
    inactive = "inactive"
