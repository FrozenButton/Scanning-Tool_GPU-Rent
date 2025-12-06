import logging
from datetime import timedelta
from typing import Any, Dict, Optional

import stripe
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import __name__ as package_name
from .config import rental_config
from .credits import CreditError, add_credits, consume_credit, get_credit_balance
from .database import SessionLocal, engine, get_db
from .models import ApiKey, Job, Transaction, User, ensure_tables
from .queueing import JobQueue, Worker, enqueue_job, requeue_outstanding_jobs
from .schemas import (
    APIKeyResponse,
    CheckoutRequest,
    CreditBalanceResponse,
    JobResponse,
    JobStatusResponse,
    LoginRequest,
    ScanRequest,
    SignupRequest,
    TokenResponse,
    TransactionView,
)
from .security import (
    AuthError,
    authenticate_user,
    create_access_token,
    create_api_key,
    decode_access_token,
    get_password_hash,
    get_user_by_api_key,
)

logger = logging.getLogger(package_name)
logging.basicConfig(level=logging.INFO)

ensure_tables(engine)
job_queue = JobQueue()
worker_pool = [Worker(SessionLocal, job_queue) for _ in range(rental_config.max_worker_concurrency)]
for worker in worker_pool:
    worker.start()

app = FastAPI(title="GPU Rental Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    with SessionLocal() as db:
        requeue_outstanding_jobs(db, job_queue)
    stripe.api_key = rental_config.stripe_secret_key


@app.on_event("shutdown")
def shutdown_event() -> None:
    for worker in worker_pool:
        worker.stop()


@app.post("/auth/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(email=payload.email, password_hash=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token)


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.id}, timedelta(minutes=rental_config.token_exp_minutes))
    return TokenResponse(access_token=token)


@app.post("/auth/api-keys", response_model=APIKeyResponse)
def create_key(request: Request, db: Session = Depends(get_db)) -> APIKeyResponse:
    user = resolve_current_user(request, db)
    key = create_api_key()
    api_key = ApiKey(user_id=user.id, key=key)
    db.add(api_key)
    db.commit()
    return APIKeyResponse(key=key)


@app.get("/me/credits", response_model=CreditBalanceResponse)
def credit_balance(request: Request, db: Session = Depends(get_db)) -> CreditBalanceResponse:
    user = resolve_current_user(request, db)
    balance = get_credit_balance(db, user.id)
    return CreditBalanceResponse(balance=balance)


@app.get("/me/transactions", response_model=list[TransactionView])
def list_transactions(request: Request, db: Session = Depends(get_db)) -> list[TransactionView]:
    user = resolve_current_user(request, db)
    records = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
        .all()
    )
    return [TransactionView.from_orm(record) for record in records]


@app.post("/payments/checkout")
def create_checkout_session(payload: CheckoutRequest, request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
    user = resolve_current_user(request, db)
    pack = rental_config.credit_packs.get(payload.pack_id)
    if not pack:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown pack")
    if not rental_config.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe not configured")
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        line_items=[{"price": pack.stripe_price, "quantity": 1}],
        metadata={"user_id": user.id, "pack_id": payload.pack_id},
    )
    return {"checkout_url": session.url}


@app.post("/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
    if not rental_config.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook secret missing")
    body = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(body, signature, rental_config.stripe_webhook_secret)
    except Exception as exc:  # Stripe library raises various exceptions
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        pack_id = session.get("metadata", {}).get("pack_id")
        pack = rental_config.credit_packs.get(pack_id)
        if user_id and pack:
            add_credits(db, user_id=user_id, amount=pack.credits, payment_id=session.get("id"))
            db.commit()
    return {"status": "ok"}


@app.post("/api/scan", response_model=JobResponse)
def paid_scan(payload: ScanRequest, request: Request, db: Session = Depends(get_db)) -> JobResponse:
    user = resolve_current_user(request, db)
    try:
        consume_credit(db, user.id)
        job = enqueue_job(db, user.id, payload.payload)
        db.commit()
    except CreditError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))
    job_queue.push(job.id)
    return JobResponse(job_id=job.id, status=job.status)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str, request: Request, db: Session = Depends(get_db)) -> JobStatusResponse:
    user = resolve_current_user(request, db)
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def resolve_current_user(request: Request, db: Session) -> User:
    api_key = request.headers.get("X-API-Key")
    bearer = request.headers.get("Authorization")
    if api_key:
        user = get_user_by_api_key(db, api_key)
        if user:
            return user
    if bearer and bearer.startswith("Bearer "):
        token = bearer.split(" ", 1)[1]
        try:
            payload = decode_access_token(token)
        except AuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        user_id: Optional[str] = payload.get("sub")
        if user_id:
            user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
            if user:
                return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rental_service.server:app", host="0.0.0.0", port=5002, reload=False)
