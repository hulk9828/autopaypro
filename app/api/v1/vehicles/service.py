from typing import Optional
import uuid
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, cast, String

from app.api.v1.vehicles.schemas import CreateVehicleRequest, UpdateVehicleRequest
from app.core.exceptions import AppException
from app.models.vehicle import Vehicle
from app.models.loan import Loan
from app.models.customer_vehicle import CustomerVehicle
from app.models.enums import VehicleStatus, VehicleCondition


class VehicleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_vehicle(self, vehicle_data: CreateVehicleRequest) -> Vehicle:
        # Check if VIN already exists
        existing_vehicle = await self.db.execute(
            select(Vehicle).where(Vehicle.vin == vehicle_data.vin)
        )
        if existing_vehicle.scalar_one_or_none():
            AppException().raise_400(f"Vehicle with VIN {vehicle_data.vin} already exists")

        # Validate status and condition
        if vehicle_data.status and vehicle_data.status not in [s.value for s in VehicleStatus]:
            AppException().raise_400(f"Invalid status. Must be one of: {[s.value for s in VehicleStatus]}")

        if vehicle_data.condition and vehicle_data.condition not in [c.value for c in VehicleCondition]:
            AppException().raise_400(f"Invalid condition. Must be one of: {[c.value for c in VehicleCondition]}")

        new_vehicle = Vehicle(
            id=uuid.uuid4(),
            vin=vehicle_data.vin,
            make=vehicle_data.make,
            model=vehicle_data.model,
            year=vehicle_data.year,
            color=vehicle_data.color,
            mileage=vehicle_data.mileage,
            purchase_price=vehicle_data.purchase_price,
            status=vehicle_data.status or VehicleStatus.available.value,
            condition=vehicle_data.condition or VehicleCondition.good.value,
        )

        self.db.add(new_vehicle)
        await self.db.commit()
        await self.db.refresh(new_vehicle)
        return {"message": "Vehicle created successfully", "vehicle": new_vehicle}

    async def get_vehicle_by_id(self, vehicle_id: uuid.UUID) -> Optional[Vehicle]:
        vehicle = await self.db.get(Vehicle, vehicle_id)
        return {"message": "Vehicle retrieved successfully", "vehicle": vehicle}

    async def get_vehicle_by_vin(self, vin: str) -> Optional[Vehicle]:
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.vin == vin)
        )
        return {"message": "Vehicle retrieved successfully", "vehicle": result.scalar_one_or_none()}

    async def get_all_vehicles(
        self,
        skip: int = 0,
        offset: Optional[int] = None,
        limit: int = 100,
        search: Optional[str] = None,
        status: Optional[str] = None,
        condition: Optional[str] = None
    ) -> dict:
        filters = []

        if status:
            filters.append(Vehicle.status == status)
        if condition:
            filters.append(Vehicle.condition == condition)
        if search and search.strip():
            search_text = search.strip()
            full_pattern = search_text
            tokens = [token for token in search_text.split() if token]
            normalized_search_text = " ".join(tokens)

            def validate_regex(pattern: str, label: str = "search") -> None:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    AppException().raise_400(f"Invalid {label} regex pattern: {exc}")

            def regex_filter(pattern: str):
                return or_(
                    Vehicle.vin.op("~*")(pattern),
                    Vehicle.make.op("~*")(pattern),
                    Vehicle.model.op("~*")(pattern),
                    cast(Vehicle.year, String).op("~*")(pattern),
                    Vehicle.color.op("~*")(pattern),
                    func.concat(Vehicle.make, " ", Vehicle.model).op("~*")(pattern),
                    func.concat(Vehicle.model, " ", Vehicle.make).op("~*")(pattern),
                )

            validate_regex(full_pattern)
            if tokens:
                token_filters = []
                for token in tokens:
                    validate_regex(token, "token")
                    token_filters.append(regex_filter(token))
                # All tokens must match at least one searchable field.
                filters.append(
                    or_(
                        and_(*token_filters),
                        func.concat(Vehicle.make, " ", Vehicle.model).op("~*")(full_pattern),
                        func.concat(Vehicle.model, " ", Vehicle.make).op("~*")(full_pattern),
                    )
                )
            else:
                filters.append(regex_filter(full_pattern))

        query = select(Vehicle)
        if filters:
            query = query.where(and_(*filters))
        if offset is not None:
            effective_offset = offset
        else:
            # Backward compatible behavior:
            # skip=0 or skip=1 -> first page, skip=2 -> second page.
            page_index = 0 if skip <= 1 else skip - 1
            effective_offset = page_index * limit
        query = query.offset(effective_offset).limit(limit).order_by(Vehicle.created_at.desc())

        result = await self.db.execute(query)
        vehicles = list(result.scalars().all())

        total_query = select(func.count(Vehicle.id))
        available_query = select(func.count(Vehicle.id)).where(Vehicle.status == VehicleStatus.available.value)
        leased_query = select(func.count(Vehicle.id)).where(Vehicle.status == VehicleStatus.leased.value)
        inventory_value_query = select(func.sum(Vehicle.purchase_price))
        if filters:
            total_query = total_query.where(and_(*filters))
            available_query = available_query.where(and_(*filters))
            leased_query = leased_query.where(and_(*filters))
            inventory_value_query = inventory_value_query.where(and_(*filters))

        total_result = await self.db.execute(total_query)
        available_result = await self.db.execute(
            available_query
        )
        leased_result = await self.db.execute(
            leased_query
        )
        inventory_value_result = await self.db.execute(inventory_value_query)

        return {
            "message": "Vehicles retrieved successfully",
            "vehicles": vehicles,
            "total_vehicles": total_result.scalar() or 0,
            "available": available_result.scalar() or 0,
            "leased": leased_result.scalar() or 0,
            "inventory_value": float(inventory_value_result.scalar() or 0),
        }

    async def update_vehicle(
        self,
        vehicle_id: uuid.UUID,
        vehicle_data: UpdateVehicleRequest
    ) -> Vehicle:
        # Get vehicle directly from database
        vehicle = await self.db.get(Vehicle, vehicle_id)
        if not vehicle:
            AppException().raise_404(f"Vehicle with id {vehicle_id} not found")

        # Check if VIN is being updated and if it already exists
        if vehicle_data.vin and vehicle_data.vin != vehicle.vin:
            result = await self.db.execute(
                select(Vehicle).where(Vehicle.vin == vehicle_data.vin)
            )
            existing_vehicle = result.scalar_one_or_none()
            if existing_vehicle:
                AppException().raise_400(f"Vehicle with VIN {vehicle_data.vin} already exists")

        # Validate status and condition if provided
        if vehicle_data.status and vehicle_data.status not in [s.value for s in VehicleStatus]:
            AppException().raise_400(f"Invalid status. Must be one of: {[s.value for s in VehicleStatus]}")

        if vehicle_data.condition and vehicle_data.condition not in [c.value for c in VehicleCondition]:
            AppException().raise_400(f"Invalid condition. Must be one of: {[c.value for c in VehicleCondition]}")

        # Update fields
        update_data = vehicle_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(vehicle, field, value)

        self.db.add(vehicle)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return {"message": "Vehicle updated successfully", "vehicle": vehicle}

    async def delete_vehicle(self, vehicle_id: uuid.UUID) -> bool:
        # Get vehicle directly from database
        vehicle = await self.db.get(Vehicle, vehicle_id)
        if not vehicle:
            AppException().raise_404(f"Vehicle with id {vehicle_id} not found")

        # Check if vehicle is associated with any loans
        loan_result = await self.db.execute(
            select(Loan).where(Loan.vehicle_id == vehicle_id)
        )
        if loan_result.scalar_one_or_none():
            AppException().raise_400("Cannot delete vehicle that has associated loans")

        # Check if vehicle is assigned to any customers
        customer_vehicle_result = await self.db.execute(
            select(CustomerVehicle).where(CustomerVehicle.vehicle_id == vehicle_id)
        )
        if customer_vehicle_result.scalar_one_or_none():
            AppException().raise_400("Cannot delete vehicle that is assigned to customers")

        await self.db.delete(vehicle)
        await self.db.commit()
        return {"message": "Vehicle deleted successfully"}
