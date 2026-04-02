import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


def generate_client_request_id() -> str:
    return uuid.uuid4().hex


def generate_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_amount(amount: float | str | Decimal) -> str:
    try:
        dec = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid amount",
        )
    if dec <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amount must be greater than 0",
        )
    return f"{dec:.2f}"


def build_checksum(parts: list[str]) -> str:
    return sha256("".join(parts))


class NuveiService:
    def __init__(self) -> None:
        self.merchant_id = (settings.NUVEI_MERCHANT_ID or "").strip()
        self.merchant_site_id = (settings.NUVEI_MERCHANT_SITE_ID or "").strip()
        self.secret_key = (settings.NUVEI_SECRET_KEY or "").strip()
        self.base_url = (settings.NUVEI_BASE_URL or "").strip().rstrip("/")
        self._validate_config()

    def _validate_config(self) -> None:
        if not all([self.merchant_id, self.merchant_site_id, self.secret_key, self.base_url]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Nuvei configuration is incomplete. Set NUVEI_MERCHANT_ID, NUVEI_MERCHANT_SITE_ID, NUVEI_SECRET_KEY, NUVEI_BASE_URL",
            )

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            message = exc.response.text
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Nuvei HTTP error: {message}",
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Nuvei connection error: {str(exc)}",
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nuvei returned invalid JSON",
            )

        status_value = str(data.get("status", "")).upper()
        transaction_status = str(data.get("transactionStatus", "")).upper()
        if status_value and status_value not in {"SUCCESS", "APPROVED"}:
            reason = data.get("reason") or data.get("gwErrorReason") or "Nuvei request failed"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": status_value, "reason": reason, "response": data},
            )
        if transaction_status and transaction_status not in {"APPROVED", "SUCCESS"}:
            reason = data.get("reason") or data.get("gwErrorReason") or "Nuvei transaction failed"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"transactionStatus": transaction_status, "reason": reason, "response": data},
            )
        return data

    async def get_session_token(self, user_token_id: str, amount: float | str, currency: str) -> dict[str, Any]:
        amount_str = normalize_amount(amount)
        ts = generate_timestamp()
        client_request_id = generate_client_request_id()
        checksum = build_checksum([
            self.merchant_id,
            self.merchant_site_id,
            client_request_id,
            ts,
            self.secret_key,
        ])
        payload = {
            "merchantId": self.merchant_id,
            "merchantSiteId": self.merchant_site_id,
            "clientRequestId": client_request_id,
            "timeStamp": ts,
            "checksum": checksum,
            "userTokenId": user_token_id,
            "amount": amount_str,
            "currency": currency.upper(),
        }
        return await self._post("getSessionToken.do", payload)

    async def open_order(self, amount: float | str, currency: str, user_token_id: str) -> dict[str, Any]:
        amount_str = normalize_amount(amount)
        ts = generate_timestamp()
        client_request_id = generate_client_request_id()
        checksum = build_checksum([
            self.merchant_id,
            self.merchant_site_id,
            client_request_id,
            amount_str,
            currency.upper(),
            ts,
            self.secret_key,
        ])
        payload = {
            "merchantId": self.merchant_id,
            "merchantSiteId": self.merchant_site_id,
            "clientRequestId": client_request_id,
            "timeStamp": ts,
            "checksum": checksum,
            "amount": amount_str,
            "currency": currency.upper(),
            "userTokenId": user_token_id,
        }
        return await self._post("openOrder.do", payload)

    async def pay(
        self,
        session_token: str,
        amount: float | str,
        currency: str,
        user_token_id: str,
        card_holder_name: str,
        card_number: str,
        expiration_month: str,
        expiration_year: str,
        cvv: str,
    ) -> dict[str, Any]:
        amount_str = normalize_amount(amount)
        self._validate_card_inputs(card_number, expiration_month, expiration_year, cvv)
        ts = generate_timestamp()
        client_request_id = generate_client_request_id()
        checksum = build_checksum([
            self.merchant_id,
            self.merchant_site_id,
            client_request_id,
            amount_str,
            currency.upper(),
            user_token_id,
            session_token,
            ts,
            self.secret_key,
        ])
        payload = {
            "merchantId": self.merchant_id,
            "merchantSiteId": self.merchant_site_id,
            "clientRequestId": client_request_id,
            "sessionToken": session_token,
            "timeStamp": ts,
            "checksum": checksum,
            "amount": amount_str,
            "currency": currency.upper(),
            "userTokenId": user_token_id,
            "paymentOption": {
                "card": {
                    "cardHolderName": card_holder_name.strip(),
                    "cardNumber": card_number.strip(),
                    "expirationMonth": expiration_month,
                    "expirationYear": expiration_year,
                    "CVV": cvv.strip(),
                }
            },
        }
        return await self._post("payment.do", payload)

    async def get_payment_status(self, session_token: str) -> dict[str, Any]:
        ts = generate_timestamp()
        client_request_id = generate_client_request_id()
        checksum = build_checksum([
            self.merchant_id,
            self.merchant_site_id,
            client_request_id,
            session_token,
            ts,
            self.secret_key,
        ])
        payload = {
            "merchantId": self.merchant_id,
            "merchantSiteId": self.merchant_site_id,
            "clientRequestId": client_request_id,
            "sessionToken": session_token,
            "timeStamp": ts,
            "checksum": checksum,
        }
        return await self._post("getPaymentStatus.do", payload)

    def _validate_card_inputs(
        self,
        card_number: str,
        expiration_month: str,
        expiration_year: str,
        cvv: str,
    ) -> None:
        sanitized_card = (card_number or "").replace(" ", "")
        if not sanitized_card.isdigit() or not 12 <= len(sanitized_card) <= 19:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid cardNumber",
            )
        if not (expiration_month.isdigit() and len(expiration_month) == 2 and 1 <= int(expiration_month) <= 12):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid expirationMonth. Expected MM",
            )
        if not (expiration_year.isdigit() and len(expiration_year) in (2, 4)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid expirationYear. Expected YY or YYYY",
            )
        if not (cvv.isdigit() and len(cvv) in (3, 4)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid cvv",
            )
