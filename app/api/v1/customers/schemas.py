from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BasicInfo(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str


class AddressDocs(BaseModel):
    address: str
    driver_license_number: str
    employer_name: Optional[str] = None


class VehiclePurchase(BaseModel):
    vehicle_id: UUID
    purchase_price: float
    down_payment: float
    interest_rate: float
    loan_term_months: int


class PaymentInfo(BaseModel):
    bi_weekly_payment_amount: float


class CreateCustomerRequest(BaseModel):
    basic_info: BasicInfo
    address_docs: AddressDocs
    vehicles_to_purchase: List[VehiclePurchase]


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


class CustomerLogin(BaseModel):
    email: str
    password: str
