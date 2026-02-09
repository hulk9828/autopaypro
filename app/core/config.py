from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# -------------------------------------------------
# Explicitly load .env (CRITICAL)
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str
    # Mail: accept MAIL_* or SMTP_* (e.g. .env uses SMTP_*)
    MAIL_FROM: str = Field(validation_alias=AliasChoices("MAIL_FROM", "SMTP_FROM_EMAIL"))
    MAIL_FROM_NAME: str = Field(default="AutoLoanPro", validation_alias=AliasChoices("MAIL_FROM_NAME", "SMTP_FROM_NAME"))
    MAIL_USERNAME: str = Field(validation_alias=AliasChoices("MAIL_USERNAME", "SMTP_USER"))
    MAIL_PASSWORD: str = Field(validation_alias=AliasChoices("MAIL_PASSWORD", "SMTP_PASSWORD"))
    MAIL_SERVER: str = Field(validation_alias=AliasChoices("MAIL_SERVER", "SMTP_HOST"))
    MAIL_PORT: int = Field(validation_alias=AliasChoices("MAIL_PORT", "SMTP_PORT"))

    # S3 for profile photo upload (optional; leave empty to disable)
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    S3_CUSTOMER_PROFILE_PREFIX: str = "customer-profiles"
    S3_ADMIN_PROFILE_PREFIX: str = "admin-profiles"

    # Stripe – from .env: STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_CURRENCY
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_CURRENCY: str = "usd"

    # Payment notification cron (env: CRON_PAYMENT_NOTIFICATION_INTERVAL_HOURS, OVERDUE_DAYS_FOR_NOTIFICATION)
    CRON_PAYMENT_NOTIFICATION_INTERVAL_HOURS: float = Field(default=1.0, description="Cron run interval in hours")
    OVERDUE_DAYS_FOR_NOTIFICATION: int = Field(default=7, description="Consider payment overdue after this many days past due")

    # Firebase Cloud Messaging (push notifications). Optional; leave empty to disable.
    FIREBASE_CREDENTIALS_PATH: str = Field(default="", description="Path to Firebase service account JSON file")
    FIREBASE_CREDENTIALS_JSON: str = Field(default="", description="Alternatively: raw JSON string of service account (e.g. from env)")

    class Config:
        extra = "ignore"
        env_file = str(ENV_PATH)
        env_file_encoding = "utf-8"


settings = Settings()
