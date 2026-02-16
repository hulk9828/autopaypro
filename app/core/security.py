import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
import bcrypt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    Bcrypt has a 72-byte limit, so we truncate if necessary.
    """
    # Ensure password is within bcrypt's 72-byte limit
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Verify password
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Bcrypt has a 72-byte limit, so we truncate if necessary.
    """
    # Ensure password is within bcrypt's 72-byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": data["sub"], "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        decoded_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded_payload
    except JWTError:
        return None


def create_password_reset_token() -> str:
    """Generate a secure random token for password reset (e.g. to store and send in email)."""
    return secrets.token_urlsafe(32)


def create_password_reset_otp() -> str:
    """Generate a 6-digit numeric OTP for password reset."""
    return "".join(secrets.choice("0123456789") for _ in range(6))
