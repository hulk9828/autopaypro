from pathlib import Path
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
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_SERVER: str
    MAIL_PORT: int

    # S3 for profile photo upload (optional; leave empty to disable)
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    S3_CUSTOMER_PROFILE_PREFIX: str = "customer-profiles"

    class Config:
        extra = "ignore"


settings = Settings()
