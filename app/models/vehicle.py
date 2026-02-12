import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, String, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import VehicleStatus, VehicleCondition


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vin = Column(String, unique=True, index=True, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(String, nullable=False)
    color = Column(String, nullable=True)
    mileage = Column(Float, nullable=True)
    purchase_price = Column(Float, nullable=False)
    lease_price = Column(Float, nullable=True)
    status = Column(String, default=VehicleStatus.available.value, nullable=False)
    condition = Column(String, default=VehicleCondition.good.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer_vehicles = relationship("CustomerVehicle", back_populates="vehicle")
    loans = relationship("Loan", back_populates="vehicle")
