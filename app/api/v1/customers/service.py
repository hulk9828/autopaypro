from typing import List, Optional
import asyncio
import uuid
import secrets
import string
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.api.v1.customers.schemas import (
    CreateCustomerRequest,
    VehicleLease,
    CustomerLogin,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    CustomerHomePageResponse,
    VehicleLoanInfo,
    CustomerDetailResponse,
    LoanDetail,
    CustomerProfileUpdate,
    CustomerPaymentScheduleResponse,
    LoanPaymentSchedule,
    PaymentScheduleEntry,
    _payment_schedule_description,
)
from app.core.exceptions import AppException
from app.core.utils import ensure_non_negative_amount
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.customer_vehicle import CustomerVehicle
from app.models.loan import Loan
from app.models.payment import Payment
from app.core.loan_schedule import get_due_dates_range
from app.models.enums import VehicleStatus, AccountStatus
from app.core.security import get_password_hash, verify_password
from app.core.email import send_customer_password_email, send_otp_email
from app.core import s3 as s3_module


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def create_customer_and_loan(self, customer_data: CreateCustomerRequest) -> Customer:
        # Validate unique fields before creating customer
        # Check if email already exists
        existing_email = await self.db.execute(
            select(Customer).where(Customer.email == customer_data.basic_info.email)
        )
        if existing_email.scalar_one_or_none():
            AppException().raise_400(f"Customer with email {customer_data.basic_info.email} already exists")
        
        # Check if phone already exists
        existing_phone = await self.db.execute(
            select(Customer).where(Customer.phone == customer_data.basic_info.phone)
        )
        if existing_phone.scalar_one_or_none():
            AppException().raise_400(f"Customer with phone {customer_data.basic_info.phone} already exists")
        
        # Check if driver license number already exists
        existing_driver_license = await self.db.execute(
            select(Customer).where(Customer.driver_license_number == customer_data.address_docs.driver_license_number)
        )
        if existing_driver_license.scalar_one_or_none():
            AppException().raise_400(f"Customer with driver license number {customer_data.address_docs.driver_license_number} already exists")
        
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

        # Assign vehicles on lease and create loans
        assigned_vehicle_ids = set()
        lease_start = datetime.utcnow()

        for vehicle_lease in customer_data.vehicles_to_lease:
            if vehicle_lease.vehicle_id in assigned_vehicle_ids:
                AppException().raise_400(f"Vehicle with id {vehicle_lease.vehicle_id} is already included in this lease request")

            vehicle = await self.db.get(Vehicle, vehicle_lease.vehicle_id)
            if not vehicle:
                AppException().raise_400(f"Vehicle with id {vehicle_lease.vehicle_id} does not exist")

            existing_assignment = await self.db.execute(
                select(CustomerVehicle).where(CustomerVehicle.vehicle_id == vehicle_lease.vehicle_id)
            )
            assigned_customer_vehicle = existing_assignment.scalar_one_or_none()
            if assigned_customer_vehicle:
                AppException().raise_400(f"Vehicle with id {vehicle_lease.vehicle_id} is already leased to another customer")

            if vehicle.status in (VehicleStatus.sold.value, VehicleStatus.leased.value):
                AppException().raise_400(f"Vehicle with id {vehicle_lease.vehicle_id} is already leased and not available")

            assigned_vehicle_ids.add(vehicle_lease.vehicle_id)

            # Set lease price on vehicle (entered at customer/lease assignment time)
            vehicle.lease_price = vehicle_lease.lease_price

            # Lease period for this vehicle (explicit lease_period_months or loan_term_months)
            term_months = (
                vehicle_lease.lease_period_months
                if vehicle_lease.lease_period_months is not None
                else vehicle_lease.loan_term_months
            )

            # Lease duration: when the lease ends (for reassignment)
            lease_end = None
            if term_months > 0:
                lease_end = lease_start + timedelta(days=round(term_months * 30.44))

            vehicle.lease_end_date = lease_end
            vehicle.status = VehicleStatus.leased.value
            self.db.add(vehicle)
            await self.db.flush()

            customer_vehicle = CustomerVehicle(
                customer_id=new_customer.id,
                vehicle_id=vehicle.id,
                lease_start_date=lease_start,
                lease_end_date=lease_end,
            )
            self.db.add(customer_vehicle)
            await self.db.flush()

            # lease_amount = total to be paid over the loan term (installments); down_payment = lease_price - lease_amount
            amount_financed = ensure_non_negative_amount(vehicle_lease.lease_amount)

            payment_type = getattr(vehicle_lease, "lease_payment_type", "bi_weekly") or "bi_weekly"
            if amount_financed == 0:
                bi_weekly_payment_amount = 0.0
                loan_term_months = 0.0
            else:
                if term_months <= 0:
                    AppException().raise_400(
                        f"Loan/lease term must be greater than 0 months for vehicle {vehicle_lease.vehicle_id}"
                    )
                if payment_type == "monthly":
                    num_payments = term_months
                else:
                    num_payments = term_months * 2  # bi_weekly or semi_monthly
                if num_payments <= 0:
                    AppException().raise_400(
                        f"Number of payments must be greater than 0 for vehicle {vehicle_lease.vehicle_id}"
                    )
                bi_weekly_payment_amount = amount_financed / num_payments
                bi_weekly_payment_amount = ensure_non_negative_amount(bi_weekly_payment_amount)
                loan_term_months = float(term_months)

            loan = Loan(
                id=uuid.uuid4(),
                customer_id=new_customer.id,
                vehicle_id=vehicle.id,
                total_purchase_price=vehicle_lease.lease_price,
                down_payment=vehicle_lease.down_payment,
                amount_financed=amount_financed,
                bi_weekly_payment_amount=bi_weekly_payment_amount,
                loan_term_months=loan_term_months,
                lease_payment_type=payment_type,
                interest_rate=None,
                status="closed" if amount_financed == 0 else "active",
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
            self.logger.warning(f"Failed to send password email to {new_customer.email}, but customer was created successfully")
        
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

    async def change_password(
        self,
        customer: Customer,
        password_data: ChangePasswordRequest
    ) -> bool:
        """
        Change customer password.
        
        Args:
            customer: The customer whose password is being changed
            password_data: Contains current_password and new_password
            
        Returns:
            True if password changed successfully
            
        Raises:
            HTTPException if current password is incorrect
        """
        # Verify current password
        if not verify_password(password_data.current_password, customer.password_hash):
            AppException().raise_400("Current password is incorrect")
        
        # Hash new password
        new_password_hash = get_password_hash(password_data.new_password)
        
        # Update password
        customer.password_hash = new_password_hash
        self.db.add(customer)
        await self.db.commit()
        
        self.logger.info(f"Password changed successfully for customer {customer.id}")
        return True

    async def reset_password(
        self,
        password_data: ResetPasswordRequest
    ) -> bool:
        """
        Reset customer password (for forgot password flow).
        Requires valid OTP code.
        
        Args:
            password_data: Contains email, otp_code, and new_password
            
        Returns:
            True if password reset successfully
            
        Raises:
            HTTPException if customer not found, OTP invalid, or OTP expired
        """
        # Verify OTP first
        await self.verify_otp(password_data.email, password_data.otp_code)
        
        # Get customer by email
        customer = await self.get_customer_by_email(password_data.email)
        
        if not customer:
            AppException().raise_404("Customer with this email not found")
        
        # Hash new password
        new_password_hash = get_password_hash(password_data.new_password)
        
        # Update password and clear OTP
        customer.password_hash = new_password_hash
        customer.otp_code = None
        customer.otp_expires_at = None
        self.db.add(customer)
        await self.db.commit()
        
        self.logger.info(f"Password reset successfully for customer {customer.id}")
        return True

    async def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """Get customer by email address."""
        result = await self.db.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()

    async def generate_and_send_otp(self, email: str) -> bool:
        """
        Generate OTP, store it in customer record, and send via email.
        
        Args:
            email: Customer email address
            
        Returns:
            True if OTP generated and sent successfully, False otherwise
            
        Raises:
            HTTPException if customer not found or account is inactive
        """
        # Get customer by email
        customer = await self.get_customer_by_email(email)
        
        if not customer:
            # Don't reveal if email exists for security
            return True
        
        # Check if account is active
        if customer.account_status != AccountStatus.active.value:
            # Don't reveal account status for security
            return True
        
        # Generate 6-digit OTP
        otp_code = ''.join(secrets.choice(string.digits) for _ in range(6))
        
        # Set expiration (10 minutes from now)
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Store OTP in customer record
        customer.otp_code = otp_code
        customer.otp_expires_at = otp_expires_at
        self.db.add(customer)
        await self.db.commit()
        
        # Send OTP via email
        customer_name = f"{customer.first_name} {customer.last_name}"
        email_sent = await send_otp_email(
            customer_email=customer.email,
            customer_name=customer_name,
            otp_code=otp_code
        )
        
        if not email_sent:
            self.logger.warning(f"Failed to send OTP email to {customer.email}")
            return False
        
        self.logger.info(f"OTP generated and sent to {customer.email}")
        return True

    async def resend_otp(self, email: str) -> bool:
        """
        Resend OTP to customer if a valid OTP request exists.
        If OTP has expired or doesn't exist, generate a new one.
        
        Args:
            email: Customer email address
            
        Returns:
            True if OTP resent successfully, False otherwise
            
        Raises:
            HTTPException if customer not found or account is inactive
        """
        # Get customer by email
        customer = await self.get_customer_by_email(email)
        
        if not customer:
            # Don't reveal if email exists for security
            return True
        
        # Check if account is active
        if customer.account_status != AccountStatus.active.value:
            # Don't reveal account status for security
            return True
        
        # Check if there's an existing OTP that hasn't expired
        if customer.otp_code and customer.otp_expires_at:
            if datetime.utcnow() < customer.otp_expires_at:
                # Resend existing OTP
                customer_name = f"{customer.first_name} {customer.last_name}"
                email_sent = await send_otp_email(
                    customer_email=customer.email,
                    customer_name=customer_name,
                    otp_code=customer.otp_code
                )
                
                if email_sent:
                    self.logger.info(f"OTP resent to {customer.email}")
                    return True
                else:
                    self.logger.warning(f"Failed to resend OTP email to {customer.email}")
                    return False
        
        # No valid OTP exists, generate a new one
        return await self.generate_and_send_otp(email)

    async def verify_otp(self, email: str, otp_code: str) -> bool:
        """
        Verify OTP code for password reset.
        
        Args:
            email: Customer email address
            otp_code: OTP code to verify
            
        Returns:
            True if OTP is valid, False otherwise
            
        Raises:
            HTTPException if customer not found, OTP invalid, or OTP expired
        """
        # Get customer by email
        customer = await self.get_customer_by_email(email)
        
        if not customer:
            AppException().raise_404("Customer with this email not found")
        
        # Check if account is active
        if customer.account_status != AccountStatus.active.value:
            AppException().raise_400("Cannot reset password for inactive account")
        
        # Check if OTP exists
        if not customer.otp_code:
            AppException().raise_400("No OTP found. Please request a new OTP.")
        
        # Check if OTP has expired
        if not customer.otp_expires_at or datetime.utcnow() > customer.otp_expires_at:
            AppException().raise_400("OTP has expired. Please request a new OTP.")
        
        # Verify OTP code
        if customer.otp_code != otp_code:
            AppException().raise_400("Invalid OTP code.")
        
        return True

    async def get_customer_home_page_data(self, customer: Customer) -> CustomerHomePageResponse:
        """
        Get customer home page data including all vehicles, loan information, and next payment.
        """
        result = await self.db.execute(
            select(Loan, Vehicle)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .where(Loan.customer_id == customer.id)
        )
        loans_with_vehicles = result.all()
        vehicles_info = []
        total_remaining_balance = 0.0
        earliest_next_due: Optional[datetime] = None
        next_payment_amount: Optional[float] = None

        for loan, vehicle in loans_with_vehicles:
            loan_start_date = loan.created_at
            loan_end_date = loan_start_date + timedelta(days=int(loan.loan_term_months * 30.44))
            pt = getattr(loan, "lease_payment_type", "bi_weekly") or "bi_weekly"
            total_payments = int(loan.loan_term_months) if pt == "monthly" else int(loan.loan_term_months * 2)
            next_payment_due_date = await self._get_next_payment_due_date(loan)
            if next_payment_due_date is None:
                next_payment_due_date = loan_end_date
            payments_result = await self.db.execute(
                select(Payment).where(Payment.loan_id == loan.id)
            )
            payments_made = len(payments_result.scalars().all())
            remaining_balance = loan.amount_financed - (payments_made * loan.bi_weekly_payment_amount)
            remaining_balance = max(0.0, remaining_balance)
            payments_remaining = max(0, total_payments - payments_made)
            if earliest_next_due is None or (next_payment_due_date and next_payment_due_date < earliest_next_due):
                earliest_next_due = next_payment_due_date
                next_payment_amount = ensure_non_negative_amount(loan.bi_weekly_payment_amount)
            loan_status = "closed" if getattr(loan, "status", "active") == "closed" else "open"
            pt = getattr(loan, "lease_payment_type", "bi_weekly") or "bi_weekly"
            payment_amt = ensure_non_negative_amount(loan.bi_weekly_payment_amount)
            vehicle_info = VehicleLoanInfo(
                vehicle_id=vehicle.id,
                loan_id=loan.id,
                vin=vehicle.vin,
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                color=vehicle.color,
                mileage=vehicle.mileage,
                total_purchase_price=ensure_non_negative_amount(loan.total_purchase_price),
                down_payment=ensure_non_negative_amount(loan.down_payment),
                amount_financed=ensure_non_negative_amount(loan.amount_financed),
                bi_weekly_payment_amount=payment_amt,
                payment_amount=payment_amt,
                payment_schedule_description=_payment_schedule_description(pt),
                remaining_balance=remaining_balance,
                loan_term_months=loan.loan_term_months,
                lease_payment_type=pt,
                loan_start_date=loan_start_date,
                loan_end_date=loan_end_date,
                next_payment_due_date=next_payment_due_date,
                payments_remaining=payments_remaining,
                loan_status=loan_status,
            )
            vehicles_info.append(vehicle_info)
            total_remaining_balance += remaining_balance

        customer_name = f"{customer.first_name} {customer.last_name}"
        return CustomerHomePageResponse(
            customer_id=customer.id,
            customer_name=customer_name,
            total_vehicles=len(vehicles_info),
            total_remaining_balance=total_remaining_balance,
            next_payment_due_date=earliest_next_due,
            next_payment_amount=ensure_non_negative_amount(next_payment_amount) if next_payment_amount is not None else None,
            vehicles=vehicles_info
        )

    def _customer_search_filter(self, search: Optional[str]):
        """Build filter for customer search (first_name, last_name, email)."""
        if not search or not search.strip():
            return None
        term = f"%{search.strip()}%"
        return or_(
            Customer.first_name.ilike(term),
            Customer.last_name.ilike(term),
            Customer.email.ilike(term),
        )

    async def _get_next_payment_due_date(self, loan: Loan) -> Optional[datetime]:
        """Calculate the next payment due date for a loan (uses lease_payment_type)."""
        if getattr(loan, "status", "active") == "closed":
            return None
        payment_type = getattr(loan, "lease_payment_type", "bi_weekly") or "bi_weekly"
        today = date.today()
        to_date = today + timedelta(days=365 * 2)
        due_dates = get_due_dates_range(
            loan.created_at,
            loan.loan_term_months,
            payment_type,
            today,
            to_date,
        )
        payments_result = await self.db.execute(
            select(func.date(Payment.due_date).label("d")).where(Payment.loan_id == loan.id)
        )
        paid = {r.d for r in payments_result.all()}
        for due_dt in due_dates:
            if due_dt.date() not in paid:
                return due_dt
        return None

    async def _get_paid_due_dates_for_loan(self, loan_id: uuid.UUID) -> set[date]:
        """Set of (due_date as date) that have been paid for this loan."""
        result = await self.db.execute(
            select(func.date(Payment.due_date).label("d")).where(Payment.loan_id == loan_id)
        )
        return {r.d for r in result.all()}

    async def get_customer_payment_schedule(
        self,
        customer: Customer,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> CustomerPaymentScheduleResponse:
        """
        Get full payment schedule for the customer: for each loan, list of due dates with amount and status (paid/upcoming/overdue).
        If from_date/to_date not provided, uses loan start to loan end for each loan.
        """
        result = await self.db.execute(
            select(Loan, Vehicle)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .where(Loan.customer_id == customer.id)
        )
        loans_with_vehicles = result.all()
        today = date.today()
        loan_schedules: List[LoanPaymentSchedule] = []

        for loan, vehicle in loans_with_vehicles:
            payment_type = getattr(loan, "lease_payment_type", "bi_weekly") or "bi_weekly"
            payment_amt = ensure_non_negative_amount(loan.bi_weekly_payment_amount)
            loan_start = loan.created_at.date()
            loan_end = loan_start + timedelta(days=int(loan.loan_term_months * 30.44))
            start = from_date if from_date is not None else loan_start
            end = to_date if to_date is not None else loan_end
            # Clamp to loan period
            start = max(start, loan_start)
            end = min(end, loan_end) if loan.loan_term_months > 0 else end

            due_dates = get_due_dates_range(
                loan.created_at,
                loan.loan_term_months,
                payment_type,
                start,
                end,
            )
            paid_dates = await self._get_paid_due_dates_for_loan(loan.id)
            now = datetime.utcnow()

            entries: List[PaymentScheduleEntry] = []
            for due_dt in due_dates:
                d = due_dt.date()
                if d in paid_dates:
                    status = "paid"
                elif due_dt < now:
                    status = "overdue"
                else:
                    status = "upcoming"
                entries.append(
                    PaymentScheduleEntry(due_date=due_dt, amount=payment_amt, status=status)
                )

            vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}"
            loan_schedules.append(
                LoanPaymentSchedule(
                    loan_id=loan.id,
                    vehicle_display=vehicle_display,
                    lease_payment_type=payment_type,
                    payment_schedule_description=_payment_schedule_description(payment_type),
                    payment_amount=payment_amt,
                    entries=entries,
                )
            )

        customer_name = f"{customer.first_name} {customer.last_name}"
        return CustomerPaymentScheduleResponse(
            customer_id=customer.id,
            customer_name=customer_name,
            loans=loan_schedules,
        )

    async def _count_overdue_accounts(self) -> int:
        """Count customers with at least one overdue payment."""
        today = datetime.utcnow()
        loans_result = await self.db.execute(
            select(Loan, Customer)
            .join(Customer, Loan.customer_id == Customer.id)
            .where(Customer.account_status == AccountStatus.active.value)
        )
        count = 0
        for loan, _ in loans_result.all():
            next_due_date = await self._get_next_payment_due_date(loan)
            if next_due_date and next_due_date < today:
                payment_exists = await self.db.execute(
                    select(Payment).where(
                        and_(
                            Payment.loan_id == loan.id,
                            Payment.due_date == next_due_date,
                        )
                    )
                )
                if not payment_exists.scalar_one_or_none():
                    count += 1
        return count

    async def get_all_customers(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
    ) -> tuple[List[Customer], int, int, int, int]:
        """
        Get all customers with pagination, optional search, and summary stats.

        Returns:
            (customers, total_customers, active_loans, new_this_week, overdue_count)
        """
        base_filter = self._customer_search_filter(search)
        query = select(Customer)
        if base_filter is not None:
            query = query.where(base_filter)
        query_ordered = query.order_by(Customer.created_at.desc())

        # Paginated customer list
        result = await self.db.execute(
            query_ordered.offset(skip).limit(limit)
        )
        customers = list(result.scalars().all())

        # total_customers (matching search)
        total_query = select(func.count()).select_from(Customer)
        if base_filter is not None:
            total_query = total_query.where(base_filter)
        total_result = await self.db.execute(total_query)
        total_customers = total_result.scalar() or 0

        # active_loans: total loan count
        loans_count_result = await self.db.execute(select(func.count()).select_from(Loan))
        active_loans = loans_count_result.scalar() or 0

        # new_this_week: customers created in last 7 days (with same search filter)
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_query = select(func.count()).select_from(Customer).where(Customer.created_at >= week_ago)
        if base_filter is not None:
            new_query = new_query.where(base_filter)
        new_result = await self.db.execute(new_query)
        new_this_week = new_result.scalar() or 0

        # overdue_count
        overdue_count = await self._count_overdue_accounts()

        return customers, total_customers, active_loans, new_this_week, overdue_count

    async def get_customer_by_id(self, customer_id: uuid.UUID) -> Optional[Customer]:
        """
        Get customer by ID.
        
        Args:
            customer_id: Customer UUID
            
        Returns:
            Customer object if found, None otherwise
        """
        return await self.db.get(Customer, customer_id)

    async def get_customer_profile(self, customer_id: uuid.UUID) -> Optional[Customer]:
        """Get customer by ID for profile (fresh from DB)."""
        customer = await self.get_customer_by_id(customer_id)
        if customer:
            await self.db.refresh(customer)
        return customer

    async def update_device_token(self, customer_id: uuid.UUID, device_token: str) -> None:
        """Update device token for push notifications."""
        customer = await self.get_customer_by_id(customer_id)
        if customer:
            customer.device_token = device_token or None
            self.db.add(customer)
            await self.db.commit()

    async def update_customer_profile(self, customer: Customer, data: CustomerProfileUpdate) -> Customer:
        """Update customer profile. Validates uniqueness for email, phone, driver_license_number."""
        if data.first_name is not None:
            customer.first_name = data.first_name.strip()
        if data.last_name is not None:
            customer.last_name = data.last_name.strip()
        if data.phone is not None:
            phone = data.phone.strip()
            if not phone:
                AppException().raise_400("Phone cannot be empty")
            existing = await self.db.execute(
                select(Customer).where(Customer.phone == phone, Customer.id != customer.id)
            )
            if existing.scalars().first():
                AppException().raise_400("Phone already registered")
            customer.phone = phone
        if data.email is not None:
            email = data.email.strip()
            if not email:
                AppException().raise_400("Email cannot be empty")
            existing = await self.db.execute(
                select(Customer).where(Customer.email == email, Customer.id != customer.id)
            )
            if existing.scalars().first():
                AppException().raise_400("Email already registered")
            customer.email = email
        if data.address is not None:
            customer.address = data.address.strip()
        if data.driver_license_number is not None:
            dln = data.driver_license_number.strip()
            if dln:
                existing = await self.db.execute(
                    select(Customer).where(Customer.driver_license_number == dln, Customer.id != customer.id)
                )
                if existing.scalars().first():
                    AppException().raise_400("Driver license number already registered")
                customer.driver_license_number = dln
        if data.employer_name is not None:
            customer.employer_name = data.employer_name.strip() or None
        if data.profile_pic is not None:
            customer.profile_pic = data.profile_pic.strip() or None
        if data.device_token is not None:
            customer.device_token = data.device_token.strip() or None
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def upload_profile_photo(self, customer: Customer, file_content: bytes, content_type: str) -> Customer:
        """Upload profile photo to S3 and set customer.profile_pic to the URL."""
        url = await asyncio.to_thread(
            s3_module.upload_customer_profile_photo,
            file_content,
            str(customer.id),
            content_type,
        )
        customer.profile_pic = url
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def get_customer_details(self, customer_id: uuid.UUID) -> CustomerDetailResponse:
        """
        Get detailed customer information including loans and vehicles.
        
        Args:
            customer_id: Customer UUID
            
        Returns:
            CustomerDetailResponse with customer and loan details
            
        Raises:
            HTTPException if customer not found
        """
        customer = await self.get_customer_by_id(customer_id)
        
        if not customer:
            AppException().raise_404(f"Customer with id {customer_id} not found")
        
        result = await self.db.execute(
            select(Loan, Vehicle)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .where(Loan.customer_id == customer_id)
        )
        loans_with_vehicles = result.all()
        loan_details = []
        earliest_next_due: Optional[datetime] = None
        next_payment_amount_val: Optional[float] = None
        for loan, vehicle in loans_with_vehicles:
            next_due = await self._get_next_payment_due_date(loan)
            if earliest_next_due is None or (next_due and next_due < earliest_next_due):
                earliest_next_due = next_due
                next_payment_amount_val = ensure_non_negative_amount(loan.bi_weekly_payment_amount)
            loan_status = "closed" if getattr(loan, "status", "active") == "closed" else "open"
            pt = getattr(loan, "lease_payment_type", "bi_weekly") or "bi_weekly"
            payment_amt = ensure_non_negative_amount(loan.bi_weekly_payment_amount)
            loan_detail = LoanDetail(
                loan_id=loan.id,
                vehicle_id=vehicle.id,
                vehicle_vin=vehicle.vin,
                vehicle_make=vehicle.make,
                vehicle_model=vehicle.model,
                vehicle_year=vehicle.year,
                total_purchase_price=ensure_non_negative_amount(loan.total_purchase_price),
                down_payment=ensure_non_negative_amount(loan.down_payment),
                amount_financed=ensure_non_negative_amount(loan.amount_financed),
                bi_weekly_payment_amount=payment_amt,
                payment_amount=payment_amt,
                payment_schedule_description=_payment_schedule_description(pt),
                loan_term_months=loan.loan_term_months,
                lease_payment_type=pt,
                created_at=loan.created_at,
                next_payment_due_date=next_due,
                loan_status=loan_status,
            )
            loan_details.append(loan_detail)
        return CustomerDetailResponse(
            id=customer.id,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone=customer.phone,
            email=customer.email,
            address=customer.address,
            driver_license_number=customer.driver_license_number,
            employer_name=customer.employer_name,
            account_status=customer.account_status,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            total_loans=len(loan_details),
            next_payment_due_date=earliest_next_due,
            next_payment_amount=ensure_non_negative_amount(next_payment_amount_val) if next_payment_amount_val is not None else None,
            loans=loan_details
        )
