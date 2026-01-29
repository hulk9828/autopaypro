import uuid
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.sales.schemas import (
    CreateSaleRequest,
    SaleResponse,
    SaleListItem,
    BiWeeklyEstimateRequest,
    BiWeeklyEstimateResponse,
)
from app.core.exceptions import AppException
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.loan import Loan
from app.models.customer_vehicle import CustomerVehicle
from app.models.enums import VehicleStatus, AccountStatus


def calculate_bi_weekly_payment(
    sale_amount: float,
    down_payment: float,
    term_months: int,
    interest_rate: float,
) -> float:
    """
    Calculate bi-weekly payment amount.
    P = L [i(1 + i)^n] / [(1 + i)^n – 1]
    """
    amount_financed = sale_amount - down_payment
    if amount_financed <= 0:
        return 0.0
    num_payments = term_months * 2
    if num_payments <= 0:
        return 0.0
    bi_weekly_rate = (interest_rate / 100) / 26
    if bi_weekly_rate > 0:
        return float(
            (amount_financed * bi_weekly_rate * (1 + bi_weekly_rate) ** num_payments)
            / (((1 + bi_weekly_rate) ** num_payments) - 1)
        )
    return amount_financed / num_payments


class SaleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger(__name__)

    def get_bi_weekly_estimate(self, data: BiWeeklyEstimateRequest) -> BiWeeklyEstimateResponse:
        """Return estimated bi-weekly payment without creating a sale."""
        amount_financed = data.sale_amount - data.down_payment
        if amount_financed <= 0:
            AppException().raise_400("Down payment must be less than sale amount")
        bi_weekly = calculate_bi_weekly_payment(
            data.sale_amount,
            data.down_payment,
            data.term_months,
            data.interest_rate,
        )
        return BiWeeklyEstimateResponse(
            sale_amount=data.sale_amount,
            down_payment=data.down_payment,
            amount_financed=amount_financed,
            term_months=data.term_months,
            interest_rate=data.interest_rate,
            estimated_bi_weekly_payment=round(bi_weekly, 2),
        )

    async def create_sale(self, data: CreateSaleRequest) -> SaleResponse:
        """
        Create a new vehicle sale for an existing customer.
        Associates vehicle with customer, creates loan, marks vehicle as sold.
        """
        # Validate customer
        customer = await self.db.get(Customer, data.customer_id)
        if not customer:
            AppException().raise_404("Customer not found")
        if customer.account_status != AccountStatus.active.value:
            AppException().raise_400("Customer account is inactive")

        # Validate vehicle
        vehicle = await self.db.get(Vehicle, data.vehicle_id)
        if not vehicle:
            AppException().raise_404("Vehicle not found")
        if vehicle.status == VehicleStatus.sold.value:
            AppException().raise_400("Vehicle is already sold and not available")

        # Check vehicle not already assigned
        existing = await self.db.execute(
            select(CustomerVehicle).where(CustomerVehicle.vehicle_id == data.vehicle_id)
        )
        if existing.scalar_one_or_none():
            AppException().raise_400("Vehicle is already assigned to another customer")

        # Validate down payment
        amount_financed = data.sale_amount - data.down_payment
        if amount_financed <= 0:
            AppException().raise_400("Down payment must be less than sale amount")

        bi_weekly_payment = calculate_bi_weekly_payment(
            data.sale_amount,
            data.down_payment,
            data.term_months,
            data.interest_rate,
        )

        # Create CustomerVehicle
        cv = CustomerVehicle(
            id=uuid.uuid4(),
            customer_id=data.customer_id,
            vehicle_id=data.vehicle_id,
        )
        self.db.add(cv)
        await self.db.flush()

        # Mark vehicle as sold
        vehicle.status = VehicleStatus.sold.value
        self.db.add(vehicle)
        await self.db.flush()

        # Create Loan
        loan = Loan(
            id=uuid.uuid4(),
            customer_id=data.customer_id,
            vehicle_id=data.vehicle_id,
            total_purchase_price=data.sale_amount,
            down_payment=data.down_payment,
            amount_financed=amount_financed,
            bi_weekly_payment_amount=bi_weekly_payment,
            loan_term_months=float(data.term_months),
            interest_rate=data.interest_rate,
        )
        self.db.add(loan)
        await self.db.commit()
        await self.db.refresh(loan)
        await self.db.refresh(customer)
        await self.db.refresh(vehicle)

        customer_name = f"{customer.first_name} {customer.last_name}"
        vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}"

        return SaleResponse(
            loan_id=loan.id,
            customer_id=customer.id,
            customer_name=customer_name,
            vehicle_id=vehicle.id,
            vehicle_display=vehicle_display,
            sale_amount=loan.total_purchase_price,
            down_payment=loan.down_payment,
            amount_financed=loan.amount_financed,
            term_months=data.term_months,
            interest_rate=loan.interest_rate,
            bi_weekly_payment_amount=round(loan.bi_weekly_payment_amount, 2),
            created_at=loan.created_at,
        )

    async def get_sales(self, customer_id: Optional[uuid.UUID] = None) -> List[SaleListItem]:
        """List sales (loans). If customer_id given, filter by that customer."""
        q = (
            select(Loan, Customer, Vehicle)
            .join(Customer, Loan.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .order_by(Loan.created_at.desc())
        )
        if customer_id is not None:
            q = q.where(Loan.customer_id == customer_id)
        result = await self.db.execute(q)
        rows = result.all()
        out = []
        for loan, customer, vehicle in rows:
            customer_name = f"{customer.first_name} {customer.last_name}"
            vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}"
            out.append(
                SaleListItem(
                    loan_id=loan.id,
                    customer_id=loan.customer_id,
                    customer_name=customer_name,
                    vehicle_id=loan.vehicle_id,
                    vehicle_display=vehicle_display,
                    sale_amount=loan.total_purchase_price,
                    bi_weekly_payment_amount=loan.bi_weekly_payment_amount,
                    term_months=loan.loan_term_months,
                    created_at=loan.created_at,
                )
            )
        return out
