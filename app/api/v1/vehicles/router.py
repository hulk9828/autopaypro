from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.vehicles.schemas import (
    CreateVehicleRequest,
    UpdateVehicleRequest,
    VehicleResponse
)
from app.api.v1.vehicles.service import VehicleService
from app.core.deps import get_db, get_current_active_admin_user
from app.core.exceptions import AppException
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new vehicle",
    description="Create a new vehicle in the inventory. Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def create_vehicle(
    vehicle_data: CreateVehicleRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    result = await vehicle_service.create_vehicle(vehicle_data)
    return VehicleResponse.model_validate(result["vehicle"])


@router.get(
    "/",
    response_model=List[VehicleResponse],
    summary="Get all vehicles",
    description="Retrieve a list of vehicles with optional filtering by status and condition. Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def get_all_vehicles(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by vehicle status (available/leased)"),
    condition: Optional[str] = Query(None, description="Filter by vehicle condition (bad/good/excellent)"),
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    result = await vehicle_service.get_all_vehicles(
        skip=skip,
        limit=limit,
        status=status,
        condition=condition
    )
    return [VehicleResponse.model_validate(vehicle) for vehicle in result["vehicles"]]


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Get vehicle by ID",
    description="Retrieve a specific vehicle by its ID. Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def get_vehicle_by_id(
    vehicle_id: UUID,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    result = await vehicle_service.get_vehicle_by_id(vehicle_id)
    if not result or not result["vehicle"]:
        AppException().raise_404(f"Vehicle with id {vehicle_id} not found")
    return VehicleResponse.model_validate(result["vehicle"])


@router.get(
    "/vin/{vin}",
    response_model=VehicleResponse,
    summary="Get vehicle by VIN",
    description="Retrieve a specific vehicle by its VIN (Vehicle Identification Number). Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def get_vehicle_by_vin(
    vin: str,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    result = await vehicle_service.get_vehicle_by_vin(vin)
    if not result or not result["vehicle"]:
        AppException().raise_404(f"Vehicle with VIN {vin} not found")
    return VehicleResponse.model_validate(result["vehicle"])


@router.put(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Update vehicle",
    description="Update an existing vehicle's information. Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def update_vehicle(
    vehicle_id: UUID,
    vehicle_data: UpdateVehicleRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    result = await vehicle_service.update_vehicle(vehicle_id, vehicle_data)
    return VehicleResponse.model_validate(result["vehicle"])


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Partially update vehicle",
    description="Partially update an existing vehicle's information. Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def patch_vehicle(
    vehicle_id: UUID,
    vehicle_data: UpdateVehicleRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    result = await vehicle_service.update_vehicle(vehicle_id, vehicle_data)
    return VehicleResponse.model_validate(result["vehicle"])


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete vehicle",
    description="Delete a vehicle from the inventory. Cannot delete vehicles with associated loans or customer assignments. Admin only.",
    dependencies=[Depends(get_current_active_admin_user)]
)
async def delete_vehicle(
    vehicle_id: UUID,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle_service = VehicleService(db)
    await vehicle_service.delete_vehicle(vehicle_id)
    return None
