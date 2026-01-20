from typing import List, Optional
import uuid
import secrets
import string
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.customers.schemas import CreateCustomerRequest, VehiclePurchase, CustomerLogin
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.customer_vehicle import CustomerVehicle
from app.models.loan import Loan
from app.models.enums import VehicleStatus, AccountStatus
from app.core.security import get_password_hash, verify_password
from app.core.email import send_customer_password_email


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_customer_and_loan(self, customer_data: CreateCustomerRequest) -> Customer:
        # Generate a strong password
        password_length = 12
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        generated_password = ''.join(secrets.choice(alphabet) for _ in range(password_length))
        
        # Hash the password
        password_hash = get_password_hash(generated_password)
        
        # Create customer
        new_customer = Customer(
            id=uuid.uuid4(),
            first_name=customer_data.basic_info.first_name,
            last_name=customer_data.basic_info.last_name,
            phone=customer_data.basic_info.phone,
            email=customer_data.basic_info.email,
            password_hash=password_hash,
            address=customer_data.address_docs.address,
            driver_license_number=customer_data.address_docs.driver_license_number,
            employer_name=customer_data.address_docs.employer_name,
        )
        self.db.add(new_customer)
        await self.db.flush()

        # Assign vehicles and create loans
        for vehicle_purchase in customer_data.vehicles_to_purchase:
            # Fetch vehicle
            vehicle = await self.db.get(Vehicle, vehicle_purchase.vehicle_id)
            if not vehicle or vehicle.status == VehicleStatus.sold.value:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vehicle not available or does not exist")

            # Mark vehicle as sold
            vehicle.status = VehicleStatus.sold.value
            self.db.add(vehicle)
            await self.db.flush()

            # Create CustomerVehicle entry
            customer_vehicle = CustomerVehicle(
                customer_id=new_customer.id,
                vehicle_id=vehicle.id
            )
            self.db.add(customer_vehicle)
            await self.db.flush()

            # Calculate amount financed (simple example: purchase price - down payment)
            amount_financed = vehicle_purchase.purchase_price - vehicle_purchase.down_payment

            # Calculate bi-weekly payment (a simplified calculation for demonstration)
            # This is a very basic approximation. Real loan calculations are more complex.
            # P = L [i(1 + i)^n] / [(1 + i)^n – 1]
            # Where P = payment, L = loan amount, i = interest rate per period, n = number of payments

            # Convert annual interest rate to bi-weekly
            bi_weekly_interest_rate = (vehicle_purchase.interest_rate / 100) / 26
            # Number of bi-weekly payments
            num_payments = vehicle_purchase.loan_term_months * 2

            if bi_weekly_interest_rate > 0:
                bi_weekly_payment_amount = (amount_financed * bi_weekly_interest_rate * (1 + bi_weekly_interest_rate)**num_payments) / (((1 + bi_weekly_interest_rate)**num_payments) - 1)
            else:
                bi_weekly_payment_amount = amount_financed / num_payments # Handle zero interest rate

            # Create loan
            loan = Loan(
                id=uuid.uuid4(),
                customer_id=new_customer.id,
                vehicle_id=vehicle.id,
                total_purchase_price=vehicle_purchase.purchase_price,
                down_payment=vehicle_purchase.down_payment,
                amount_financed=amount_financed,
                bi_weekly_payment_amount=bi_weekly_payment_amount,
                loan_term_months=vehicle_purchase.loan_term_months,
                interest_rate=vehicle_purchase.interest_rate,
            )
            self.db.add(loan)
            await self.db.flush()

        await self.db.commit()
        await self.db.refresh(new_customer)
        
        # Send password email to customer
        customer_name = f"{new_customer.first_name} {new_customer.last_name}"
        email_sent = await send_customer_password_email(
            customer_email=new_customer.email,
            customer_name=customer_name,
            password=generated_password
        )
        
        if not email_sent:
            # Log warning but don't fail the customer creation
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send password email to {new_customer.email}, but customer was created successfully")
        
        return new_customer

    async def authenticate_customer(self, customer_login_data: CustomerLogin) -> Optional[Customer]:
        """
        Authenticate a customer using email and password.
        
        Args:
            customer_login_data: Customer login credentials
            
        Returns:
            Customer object if authentication successful, None otherwise
        """
        # Get customer by email
        result = await self.db.execute(
            select(Customer).where(Customer.email == customer_login_data.email)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            return None
        
        # Check if account is active
        if customer.account_status != AccountStatus.active.value:
            return None
        
        # Verify password
        if not verify_password(customer_login_data.password, customer.password_hash):
            return None
        
        return customer
