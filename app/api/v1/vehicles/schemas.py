from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class CreateVehicleRequest(BaseModel):
    vin: str = Field(..., description="Vehicle Identification Number")
    make: str = Field(..., description="Vehicle manufacturer")
    model: str = Field(..., description="Vehicle model")
    year: str = Field(..., description="Vehicle year")
    color: Optional[str] = Field(None, description="Vehicle color")
    mileage: Optional[float] = Field(None, ge=0, description="Vehicle mileage")
    purchase_price: float = Field(..., gt=0, description="Purchase price of the vehicle")
    sale_price: Optional[float] = Field(None, gt=0, description="Sale price of the vehicle")
    status: Optional[str] = Field("available", description="Vehicle status (available/sold)")
    condition: Optional[str] = Field("good", description="Vehicle condition (bad/good/excellent)")


class UpdateVehicleRequest(BaseModel):
    vin: Optional[str] = Field(None, description="Vehicle Identification Number")
    make: Optional[str] = Field(None, description="Vehicle manufacturer")
    model: Optional[str] = Field(None, description="Vehicle model")
    year: Optional[str] = Field(None, description="Vehicle year")
    color: Optional[str] = Field(None, description="Vehicle color")
    mileage: Optional[float] = Field(None, ge=0, description="Vehicle mileage")
    purchase_price: Optional[float] = Field(None, gt=0, description="Purchase price of the vehicle")
    sale_price: Optional[float] = Field(None, gt=0, description="Sale price of the vehicle")
    status: Optional[str] = Field(None, description="Vehicle status (available/sold)")
    condition: Optional[str] = Field(None, description="Vehicle condition (bad/good/excellent)")


class VehicleResponse(BaseModel):
    id: UUID
    vin: str
    make: str
    model: str
    year: str
    color: Optional[str]
    mileage: Optional[float]
    purchase_price: float
    sale_price: Optional[float]
    status: str
    condition: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
