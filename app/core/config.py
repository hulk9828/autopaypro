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

    class Config:
        extra = "ignore"


settings = Settings()
