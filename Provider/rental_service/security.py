import secrets
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import rental_config
from .models import ApiKey, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthError(Exception):
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=rental_config.token_exp_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, rental_config.jwt_secret, algorithm=rental_config.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, rental_config.jwt_secret, algorithms=[rental_config.jwt_algorithm])
    except JWTError as exc:
        raise AuthError("Invalid token") from exc


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user: Optional[User] = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password_hash) and user.is_active:
        return user
    return None


def create_api_key() -> str:
    return secrets.token_urlsafe(32)


def get_user_by_api_key(db: Session, api_key: str) -> Optional[User]:
    if not api_key:
        return None
    record = (
        db.query(ApiKey)
        .filter(ApiKey.key == api_key, ApiKey.active == True)  # noqa: E712
        .first()
    )
    return record.user if record and record.user.is_active else None
