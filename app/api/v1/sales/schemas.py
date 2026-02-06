from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateSaleRequest(BaseModel):
    """Request to create a new vehicle sale with loan terms."""
    customer_id: UUID = Field(..., description="Existing customer ID")
    vehicle_id: UUID = Field(..., description="Available vehicle ID")
    sale_amount: float = Field(..., gt=0, description="Total sale/purchase amount")
    down_payment: float = Field(..., ge=0, description="Down payment amount")
    term_months: int = Field(..., gt=0, le=360, description="Loan term in months")
    interest_rate: float = Field(..., ge=0, le=100, description="Annual interest rate (%)")

    @model_validator(mode="after")
    def down_payment_not_exceed_sale(self):
        if self.down_payment >= self.sale_amount:
            raise ValueError("Down payment must be less than sale amount")
        return self


class BiWeeklyEstimateRequest(BaseModel):
    """Request to estimate bi-weekly payment without creating a sale."""
    sale_amount: float = Field(..., gt=0)
    down_payment: float = Field(..., ge=0)
    term_months: int = Field(..., gt=0, le=360)
    interest_rate: float = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def down_payment_less_than_sale(self):
        if self.down_payment >= self.sale_amount:
            raise ValueError("Down payment must be less than sale amount")
        return self


class BiWeeklyEstimateResponse(BaseModel):
    """Estimated bi-weekly payment response."""
    sale_amount: float
    down_payment: float
    amount_financed: float
    term_months: int
    interest_rate: float
    estimated_bi_weekly_payment: float


class SaleResponse(BaseModel):
    """Created sale (loan) response with customer and vehicle info."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str
    vehicle_id: UUID
    vehicle_display: str  # e.g. "2020 Honda Civic"
    sale_amount: float
    down_payment: float
    amount_financed: float
    term_months: int
    interest_rate: float
    bi_weekly_payment_amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class SaleListItem(BaseModel):
    """Sale (loan) summary for listing."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str
    vehicle_id: UUID
    vehicle_display: str
    sale_amount: float
    bi_weekly_payment_amount: float
    term_months: float
    created_at: datetime

    class Config:
        from_attributes = True


class SalesSummary(BaseModel):
    """Dashboard summary for sales list."""
    total_sales: int = Field(..., description="Total number of sales")
    total_value: float = Field(..., description="Total value of all sales ($)")
    active_loans: int = Field(..., description="Number of active loans")
    this_month: int = Field(..., description="Sales created this month")


class SalesListResponse(BaseModel):
    """List sales response with summary stats."""
    summary: SalesSummary
    sales: List["SaleListItem"]

    class Config:
        from_attributes = True
