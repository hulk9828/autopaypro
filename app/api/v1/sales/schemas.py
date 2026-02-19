from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateLeaseRequest(BaseModel):
    """Request to create a new vehicle lease with loan terms."""
    customer_id: UUID = Field(..., description="Existing customer ID")
    vehicle_id: UUID = Field(..., description="Available vehicle ID")
    lease_price: float = Field(..., gt=0, description="Lease price for this vehicle (entered when assigning to customer)")
    lease_amount: float = Field(..., gt=0, description="Total lease/finance amount")
    down_payment: float = Field(..., ge=0, description="Down payment / security deposit")
    term_months: int = Field(..., gt=0, le=360, description="Lease term in months")
    lease_payment_type: str = Field(
        default="bi_weekly",
        description="Payment frequency: bi_weekly, monthly, or semi_monthly",
    )

    @model_validator(mode="after")
    def down_payment_not_exceed_lease(self):
        if self.down_payment >= self.lease_amount:
            raise ValueError("Down payment must be less than lease amount")
        return self


class BiWeeklyEstimateRequest(BaseModel):
    """Request to estimate payment without creating a lease (no interest)."""
    lease_amount: float = Field(..., gt=0)
    down_payment: float = Field(..., ge=0)
    term_months: int = Field(..., gt=0, le=360)
    lease_payment_type: str = Field(default="bi_weekly", description="bi_weekly, monthly, or semi_monthly")

    @model_validator(mode="after")
    def down_payment_less_than_lease(self):
        if self.down_payment >= self.lease_amount:
            raise ValueError("Down payment must be less than lease amount")
        return self


class BiWeeklyEstimateResponse(BaseModel):
    """Estimated payment per due date (no interest)."""
    lease_amount: float
    down_payment: float
    amount_financed: float
    term_months: int
    lease_payment_type: str
    estimated_payment_amount: float


class LeaseResponse(BaseModel):
    """Created lease (loan) response with customer and vehicle info."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str
    vehicle_id: UUID
    vehicle_display: str
    lease_amount: float
    down_payment: float
    amount_financed: float
    term_months: int
    lease_payment_type: str
    bi_weekly_payment_amount: float
    payment_amount: float = Field(..., description="Amount due per payment (per lease_payment_type frequency)")
    payment_schedule_description: str = Field(..., description="Human-readable payment frequency")
    created_at: datetime

    class Config:
        from_attributes = True


class LeaseListItem(BaseModel):
    """Lease (loan) summary for listing."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str
    vehicle_id: UUID
    vehicle_display: str
    lease_amount: float
    bi_weekly_payment_amount: float
    payment_amount: float = Field(..., description="Amount due per payment")
    payment_schedule_description: str = Field(..., description="Human-readable payment frequency")
    lease_payment_type: str = Field(default="bi_weekly", description="bi_weekly, monthly, or semi_monthly")
    term_months: float
    created_at: datetime

    class Config:
        from_attributes = True


class LeasesSummary(BaseModel):
    """Dashboard summary for leases list."""
    total_leases: int = Field(..., description="Total number of leases")
    total_value: float = Field(..., description="Total value of all leases ($)")
    active_loans: int = Field(..., description="Number of active loans")
    this_month: int = Field(..., description="Leases created this month")


class LeasesListResponse(BaseModel):
    """List leases response with summary stats."""
    summary: LeasesSummary
    leases: List["LeaseListItem"]

    class Config:
        from_attributes = True
