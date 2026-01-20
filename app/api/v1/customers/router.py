from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.api.v1.customers.schemas import CreateCustomerRequest, CustomerResponse, CustomerLogin
from app.api.v1.customers.service import CustomerService
from app.core.deps import get_db
from app.core.security import create_access_token
from app.core.config import settings

router = APIRouter()


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer and associated loans/vehicles",
)
async def create_customer(
    customer_data: CreateCustomerRequest,
    db: AsyncSession = Depends(get_db),
):
    customer_service = CustomerService(db)
    new_customer = await customer_service.create_customer_and_loan(customer_data)
    return CustomerResponse.model_validate(new_customer)


@router.post(
    "/login",
    summary="Customer login",
    description="Authenticate customer and receive access token"
)
async def customer_login(
    customer_login_data: CustomerLogin,
    db: AsyncSession = Depends(get_db),
):
    customer_service = CustomerService(db)
    customer = await customer_service.authenticate_customer(customer_login_data)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(customer.id),
            "role": "customer"
        },
        expires_delta=access_token_expires,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "customer": CustomerResponse.model_validate(customer)
    }
