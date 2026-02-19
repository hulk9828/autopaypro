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
    """Vehicle to assign to customer on lease (fixed term).
    lease_price = total agreed price; lease_amount = amount paid over the loan term (installments).
    down_payment is computed as lease_price - lease_amount if not provided.
    """
    vehicle_id: UUID
    lease_price: float = Field(..., gt=0, description="Lease price for this vehicle (total agreed price)")
    lease_amount: float = Field(
        ...,
        ge=0,
        description="Amount to be paid over the loan term (total of all installments); must be <= lease_price",
    )
    down_payment: Optional[float] = Field(
        None,
        ge=0,
        description="Down payment / security deposit. If omitted, computed as lease_price - lease_amount.",
    )
    lease_payment_type: Literal["bi_weekly", "monthly", "semi_monthly"] = Field(
        default="bi_weekly",
        description="Payment frequency: bi_weekly, monthly, or semi_monthly",
    )
    loan_term_months: int = Field(..., ge=0, description="Lease term in months (0 if full down payment, no schedule)")
    lease_period_months: Optional[int] = Field(
        default=None,
        ge=0,
        description="Lease period in months for this vehicle. If not set, loan_term_months is used.",
    )

    @model_validator(mode="after")
    def lease_amount_and_down_payment_consistent(self):
        if self.lease_amount > self.lease_price:
            raise ValueError("lease_amount (amount paid over term) must be less than or equal to lease_price")
        if self.down_payment is None:
            self.down_payment = round(self.lease_price - self.lease_amount, 2)
        else:
            expected = round(self.lease_price - self.lease_amount, 2)
            if abs(self.down_payment - expected) > 0.01:
                raise ValueError(
                    f"down_payment must equal lease_price - lease_amount (expected {expected})"
                )
        if self.down_payment < 0:
            raise ValueError("down_payment cannot be negative (lease_amount must be <= lease_price)")
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


def _payment_schedule_description(lease_payment_type: str) -> str:
    """Human-readable payment frequency for lease_payment_type."""
    if lease_payment_type == "monthly":
        return "Monthly (same day each month)"
    if lease_payment_type == "semi_monthly":
        return "Twice per month (1st and 15th)"
    return "Every 2 weeks (bi-weekly)"


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
    payment_amount: float = Field(..., description="Amount due per payment (same as bi_weekly_payment_amount; varies by lease_payment_type frequency)")
    payment_schedule_description: str = Field(..., description="Human-readable payment frequency, e.g. 'Every 2 weeks (bi-weekly)', 'Monthly', 'Twice per month (1st and 15th)'")
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
    payment_amount: float = Field(..., description="Amount due per payment")
    payment_schedule_description: str = Field(..., description="Human-readable payment frequency")
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


# Payment schedule API (customer sees when to pay how much)
class PaymentScheduleEntry(BaseModel):
    """Single due date entry: when to pay and how much."""
    due_date: datetime = Field(..., description="Date and time when this payment is due")
    amount: float = Field(..., description="Amount due on this date")
    status: Literal["paid", "upcoming", "overdue"] = Field(
        ...,
        description="paid = already paid; upcoming = future due; overdue = past due not yet paid",
    )


class LoanPaymentSchedule(BaseModel):
    """Payment schedule for one loan: vehicle info, payment frequency, and list of due dates with amounts."""
    loan_id: UUID
    vehicle_display: str = Field(..., description="e.g. '2024 Honda Civic'")
    lease_payment_type: Literal["bi_weekly", "monthly", "semi_monthly"]
    payment_schedule_description: str
    payment_amount: float = Field(..., description="Amount due per payment date")
    entries: List[PaymentScheduleEntry] = Field(..., description="Due dates with amount and status (paid/upcoming/overdue)")


class CustomerPaymentScheduleResponse(BaseModel):
    """Full payment schedule for the customer: all loans with due dates and amounts."""
    customer_id: UUID
    customer_name: str
    loans: List[LoanPaymentSchedule]


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
