from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class APIKeyResponse(BaseModel):
    key: str


class CreditBalanceResponse(BaseModel):
    balance: int


class CheckoutRequest(BaseModel):
    pack_id: str


class ScanRequest(BaseModel):
    payload: Dict[str, Any]


class JobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TransactionView(BaseModel):
    id: str
    amount: int
    type: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        orm_mode = True
