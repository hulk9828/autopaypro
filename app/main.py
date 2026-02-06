import asyncio
import logging
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.v1.api_router import api_router
from app.core.config import settings

# Path to frontend build
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Create FastAPI app
app = FastAPI(
    title="Payment Application API",
    description="Backend API for payment application with loans and EMI management",
    version="1.0.0",
    openapi_url=f"/openapi.json",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with actual frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def spa_fallback(request: Request, call_next):
    """Serve index.html for 404 on non-API GET requests so SPA client-side routing works."""
    response = await call_next(request)
    if (
        response.status_code == 404
        and request.method == "GET"
        and not request.url.path.startswith("/api")
        and STATIC_DIR.is_dir()
    ):
        index_path = STATIC_DIR / "index.html"
        if index_path.is_file():
            return FileResponse(str(index_path))
    return response


app.add_middleware(BaseHTTPMiddleware, dispatch=spa_fallback)

# Include API router (must be before static so /api takes precedence)
app.include_router(api_router, prefix="/api/v1")

# Serve frontend build from app/static
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

from app.core.startup import (
    ensure_default_admin,
    ensure_payment_notification_logs_table,
    ensure_payments_table,
)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    # Ensure payments table exists (create if missing)
    await ensure_payments_table()
    await ensure_payment_notification_logs_table()
    # Ensure default admin exists
    await ensure_default_admin()
    # Start payment notification cron (non-blocking)
    from app.core.cron_runner import run_payment_notification_cron_loop
    task = asyncio.create_task(run_payment_notification_cron_loop())
    app.state.payment_notification_cron_task = task


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    task = getattr(app.state, "payment_notification_cron_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # expected on cancel


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Internal server error"})


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation error",
            "errors": _serializable_validation_errors(exc.errors()),
        },
    )

# Exception handlers
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

def _serializable_validation_errors(errors: list) -> list:
    """Convert validation error dicts to JSON-serializable form (e.g. ctx may contain Exception)."""
    out = []
    for e in errors:
        item = {"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")}
        if "ctx" in e and e["ctx"]:
            item["ctx"] = {k: str(v) for k, v in e["ctx"].items()}
        out.append(item)
    return out


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors_serializable = _serializable_validation_errors(exc.errors())
    logger.info(
        "Validation error 422: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        errors_serializable,
    )
    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation error",
            "errors": errors_serializable,
        },
    )
