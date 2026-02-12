from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BasicInfo(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str


class AddressDocs(BaseModel):
    address: str
    driver_license_number: str
    employer_name: Optional[str] = None


class VehicleLease(BaseModel):
    """Vehicle to assign to customer on lease (fixed term)."""
    vehicle_id: UUID
    lease_amount: float = Field(..., description="Agreed total lease/finance amount")
    down_payment: float = Field(..., ge=0, description="Down payment / security deposit")
    lease_payment_type: Literal["bi_weekly", "monthly", "semi_monthly"] = Field(
        default="bi_weekly",
        description="Payment frequency: bi_weekly, monthly, or semi_monthly",
    )
    loan_term_months: int = Field(..., ge=0, description="Lease term in months (0 if full down payment, no schedule)")

    @model_validator(mode="after")
    def down_payment_less_than_lease_amount(self):
        if self.down_payment >= self.lease_amount:
            raise ValueError("Down payment must be less than lease amount")
        return self


class PaymentInfo(BaseModel):
    bi_weekly_payment_amount: float


class CreateCustomerRequest(BaseModel):
    basic_info: BasicInfo
    address_docs: AddressDocs
    vehicles_to_lease: List[VehicleLease] = Field(..., description="Vehicles to assign to customer on lease")


class CustomerResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: str
    address: str
    driver_license_number: str
    employer_name: Optional[str] = None
    account_status: str

    class Config:
        from_attributes = True


class CustomerProfileResponse(BaseModel):
    """Customer profile for GET (no password)."""
    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: str
    address: str
    driver_license_number: str
    employer_name: Optional[str] = None
    profile_pic: Optional[str] = None
    account_status: str
    device_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerProfileUpdate(BaseModel):
    """Update customer profile (all optional)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    driver_license_number: Optional[str] = None
    employer_name: Optional[str] = None
    profile_pic: Optional[str] = None
    device_token: Optional[str] = None


class CustomerLogin(BaseModel):
    email: str
    password: str
    device_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Customer email address")


class VerifyOtpRequest(BaseModel):
    email: str = Field(..., description="Customer email address")
    otp_code: str = Field(..., min_length=6, max_length=6, description="OTP code received via email")


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., description="Customer email address")
    otp_code: str = Field(..., min_length=6, max_length=6, description="OTP code received via email")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class VehicleLoanInfo(BaseModel):
    """Vehicle and loan information for customer home page."""
    vehicle_id: UUID
    loan_id: UUID
    vin: str
    make: str
    model: str
    year: str
    color: Optional[str]
    mileage: Optional[float]
    total_purchase_price: float
    down_payment: float
    amount_financed: float
    bi_weekly_payment_amount: float
    remaining_balance: float
    loan_term_months: float
    lease_payment_type: Literal["bi_weekly", "monthly", "semi_monthly"] = "bi_weekly"
    loan_start_date: datetime
    loan_end_date: datetime
    next_payment_due_date: datetime
    payments_remaining: int
    loan_status: Literal["open", "closed"] = Field(
        default="open",
        description="open = loan active; closed = loan fully paid",
    )

    class Config:
        from_attributes = True


class CustomerHomePageResponse(BaseModel):
    """Customer home page response with all vehicles and loan information."""
    customer_id: UUID
    customer_name: str
    total_vehicles: int
    total_remaining_balance: float
    next_payment_due_date: Optional[datetime] = None
    next_payment_amount: Optional[float] = None
    vehicles: List[VehicleLoanInfo]


class LoanDetail(BaseModel):
    """Loan detail information."""
    loan_id: UUID
    vehicle_id: UUID
    vehicle_vin: str
    vehicle_make: str
    vehicle_model: str
    vehicle_year: str
    total_purchase_price: float
    down_payment: float
    amount_financed: float
    bi_weekly_payment_amount: float
    loan_term_months: float
    lease_payment_type: Literal["bi_weekly", "monthly", "semi_monthly"] = "bi_weekly"
    created_at: datetime
    next_payment_due_date: Optional[datetime] = None
    loan_status: Literal["open", "closed"] = Field(
        default="open",
        description="open = loan active; closed = loan fully paid",
    )

    class Config:
        from_attributes = True


class CustomerDetailResponse(BaseModel):
    """Detailed customer response with loans and vehicles for admin."""
    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: str
    address: str
    driver_license_number: str
    employer_name: Optional[str]
    account_status: str
    created_at: datetime
    updated_at: datetime
    total_loans: int
    next_payment_due_date: Optional[datetime] = None
    next_payment_amount: Optional[float] = None
    loans: List[LoanDetail]

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """Paginated customer list with summary stats."""
    items: List[CustomerResponse]
    total_customers: int
    active_loans: int
    new_this_week: int
    overdue_count: int
