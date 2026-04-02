from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.nuvei_service import NuveiService

router = APIRouter()


class SessionTokenRequest(BaseModel):
    userTokenId: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)


class OpenOrderRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    userTokenId: str = Field(..., min_length=1)


class PayRequest(BaseModel):
    sessionToken: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    userTokenId: str = Field(..., min_length=1)
    cardHolderName: str = Field(..., min_length=1)
    cardNumber: str = Field(..., min_length=12, max_length=23)
    expirationMonth: str = Field(..., min_length=2, max_length=2)
    expirationYear: str = Field(..., min_length=2, max_length=4)
    cvv: str = Field(..., min_length=3, max_length=4)


class PaymentStatusRequest(BaseModel):
    sessionToken: str = Field(..., min_length=1)


@router.post("/session-token", summary="Generate Nuvei session token")
async def get_session_token(payload: SessionTokenRequest) -> dict[str, Any]:
    service = NuveiService()
    return await service.get_session_token(
        user_token_id=payload.userTokenId,
        amount=payload.amount,
        currency=payload.currency,
    )


@router.post("/open-order", summary="Open Nuvei order")
async def open_order(payload: OpenOrderRequest) -> dict[str, Any]:
    service = NuveiService()
    return await service.open_order(
        amount=payload.amount,
        currency=payload.currency,
        user_token_id=payload.userTokenId,
    )


@router.post("/pay", summary="Execute Nuvei payment")
async def pay(payload: PayRequest) -> dict[str, Any]:
    service = NuveiService()
    return await service.pay(
        session_token=payload.sessionToken,
        amount=payload.amount,
        currency=payload.currency,
        user_token_id=payload.userTokenId,
        card_holder_name=payload.cardHolderName,
        card_number=payload.cardNumber,
        expiration_month=payload.expirationMonth,
        expiration_year=payload.expirationYear,
        cvv=payload.cvv,
    )


@router.post("/payment-status", summary="Get Nuvei payment status")
async def payment_status(payload: PaymentStatusRequest) -> dict[str, Any]:
    service = NuveiService()
    return await service.get_payment_status(payload.sessionToken)
