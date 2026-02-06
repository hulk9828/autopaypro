from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.api.v1.customers.schemas import (
    CreateCustomerRequest, 
    CustomerResponse, 
    CustomerLogin,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    CustomerHomePageResponse,
    CustomerDetailResponse,
    CustomerListResponse,
    CustomerProfileResponse,
    CustomerProfileUpdate,
    VerifyOtpRequest
)
from app.api.v1.customers.service import CustomerService
from app.core.deps import get_db, get_current_customer, get_current_active_admin_user
from app.core.security import create_access_token
from app.core.exceptions import AppException
from app.core.config import settings
from app.models.customer import Customer
from app.models.user import User

router = APIRouter()


# ============================================================
# ADMIN ENDPOINTS (Requires admin authentication)
# ============================================================

@router.get(
    "/",
    response_model=CustomerListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all customers",
    description="Get a list of all customers with pagination, search, and summary stats. Admin only.",
    tags=["admin-customers"],
    dependencies=[Depends(get_current_active_admin_user)]
)
async def get_all_customers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search by first name, last name, or email"),
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all customers with stats (total_customers, active_loans, new_this_week, overdue_count). Only admins."""
    customer_service = CustomerService(db)
    customers, total_customers, active_loans, new_this_week, overdue_count = await customer_service.get_all_customers(
        skip=skip, limit=limit, search=search
    )
    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total_customers=total_customers,
        active_loans=active_loans,
        new_this_week=new_this_week,
        overdue_count=overdue_count,
    )


# Customer path /home must be declared before /{customer_id} so it is matched first
@router.get(
    "/home",
    response_model=CustomerHomePageResponse,
    status_code=status.HTTP_200_OK,
    summary="Customer home page",
    description="Get customer home page data including all vehicles, loan information, remaining balance, and next payment due dates. Requires bearer token authentication.",
    tags=["customer"]
)
async def get_customer_home_page(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Customer home page. Returns vehicles, loan details, remaining balance, next payment due. Requires customer bearer token."""
    customer_service = CustomerService(db)
    home_page_data = await customer_service.get_customer_home_page_data(current_customer)
    return home_page_data


@router.get(
    "/profile",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer profile",
    description="Get current authenticated customer profile.",
    tags=["customer"]
)
async def get_customer_profile(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Get the current customer's profile."""
    customer_service = CustomerService(db)
    customer = await customer_service.get_customer_profile(current_customer.id)
    if not customer:
        AppException().raise_404("Customer not found")
    return CustomerProfileResponse.model_validate(customer)


@router.patch(
    "/profile",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update customer profile",
    description="Update current customer profile (name, phone, email, address, etc.).",
    tags=["customer"]
)
async def update_customer_profile(
    data: CustomerProfileUpdate,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Update the current customer's profile. At least one field can be provided."""
    customer_service = CustomerService(db)
    customer = await customer_service.get_customer_profile(current_customer.id)
    if not customer:
        AppException().raise_404("Customer not found")
    updated = await customer_service.update_customer_profile(customer, data)
    return CustomerProfileResponse.model_validate(updated)


@router.post(
    "/profile/photo",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload profile photo",
    description="Upload a profile photo (image file). Stored in S3 and URL saved to profile. Max 5 MB; allowed: JPEG, PNG, WebP, GIF.",
    tags=["customer"]
)
async def upload_customer_profile_photo(
    photo: UploadFile = File(..., description="Image file (JPEG, PNG, WebP, GIF)"),
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Upload profile photo for the current customer. File is uploaded to S3; profile_pic is updated with the URL."""
    if not photo.content_type or not photo.content_type.startswith("image/"):
        AppException().raise_400("File must be an image (JPEG, PNG, WebP, or GIF)")
    content = await photo.read()
    if not content:
        AppException().raise_400("Empty file")
    customer_service = CustomerService(db)
    customer = await customer_service.get_customer_profile(current_customer.id)
    if not customer:
        AppException().raise_404("Customer not found")
    updated = await customer_service.upload_profile_photo(customer, content, photo.content_type)
    return CustomerProfileResponse.model_validate(updated)
 

@router.get(
    "/{customer_id}",
    response_model=CustomerDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer by ID",
    description="Get detailed customer information including loans and vehicles. Admin only.",
    tags=["admin-customers"],
    dependencies=[Depends(get_current_active_admin_user)]
)
async def get_customer_by_id(
    customer_id: UUID,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed customer information by ID. Only admins can access this endpoint."""
    customer_service = CustomerService(db)
    customer_detail = await customer_service.get_customer_details(customer_id)
    return customer_detail


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer and associated loans/vehicles",
    description="Admin-only endpoint to create a new customer. Requires admin authentication.",
    tags=["admin-customers"],
    dependencies=[Depends(get_current_active_admin_user)]
)
async def create_customer(
    customer_data: CreateCustomerRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new customer. Only admins can create customers."""
    customer_service = CustomerService(db)
    new_customer = await customer_service.create_customer_and_loan(customer_data)
    return CustomerResponse.model_validate(new_customer)


# ============================================================
# CUSTOMER ENDPOINTS (Customer-facing, some require authentication)
# ============================================================

@router.post(
    "/login",
    summary="Customer login",
    description="Authenticate customer and receive access token",
    tags=["customer-auth"]
)
async def customer_login(
    customer_login_data: CustomerLogin,
    db: AsyncSession = Depends(get_db),
):
    """Customer login endpoint. Returns JWT token for authenticated customers."""
    customer_service = CustomerService(db)
    customer = await customer_service.authenticate_customer(customer_login_data)
    
    if not customer:
        AppException().raise_401("Incorrect email or password, or account is inactive")
    
    if customer_login_data.device_token is not None and customer_login_data.device_token.strip():
        await customer_service.update_device_token(customer.id, customer_login_data.device_token.strip())
        await db.refresh(customer)
    
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


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change password for authenticated customer. Requires bearer token authentication and current password verification.",
    tags=["customer-auth"]
)
async def change_password(
    password_data: ChangePasswordRequest,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Change password for the authenticated customer. Requires bearer token."""
    customer_service = CustomerService(db)
    await customer_service.change_password(current_customer, password_data)
    return {"message": "Password changed successfully"}


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Forgot password",
    description="Request password reset. Generates and sends OTP code to email.",
    tags=["customer-auth"]
)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Forgot password endpoint.
    Generates OTP and sends it to the customer's email address.
    """
    customer_service = CustomerService(db)
    await customer_service.generate_and_send_otp(forgot_data.email)
    
    # Always return success message for security (don't reveal if email exists)
    return {
        "message": "If an account with this email exists, an OTP code has been sent to your email."
    }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Reset password using email and OTP code. Requires valid OTP code sent via email.",
    tags=["customer-auth"]
)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password endpoint.
    Requires valid OTP code that was sent to the customer's email.
    """
    customer_service = CustomerService(db)
    await customer_service.reset_password(reset_data)
    return {"message": "Password reset successfully. Please login with your new password."}


@router.post(
    "/resend-otp",
    status_code=status.HTTP_200_OK,
    summary="Resend OTP",
    description="Resend OTP code for password reset. If OTP has expired, a new one will be generated.",
    tags=["customer-auth"]
)
async def resend_otp(
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Resend OTP endpoint.
    Resends the existing OTP if it hasn't expired, otherwise generates a new one.
    """
    customer_service = CustomerService(db)
    await customer_service.resend_otp(forgot_data.email)
    
    # Always return success message for security (don't reveal if email exists)
    return {
        "message": "If an account with this email exists and a password reset was requested, an OTP code has been sent to your email."
    }


@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
    description="Verify OTP code for password reset. Returns success if OTP is valid.",
    tags=["customer-auth"]
)
async def verify_otp(
    verify_data: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify OTP endpoint.
    Verifies the OTP code sent to the customer's email.
    Returns success if OTP is valid, otherwise returns an error.
    """
    customer_service = CustomerService(db)
    await customer_service.verify_otp(verify_data.email, verify_data.otp_code)
    
    return {
        "message": "OTP verified successfully. You can now proceed to reset your password."
    }
