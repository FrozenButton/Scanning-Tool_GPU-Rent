from typing import Optional

from sqlalchemy.orm import Session

from .models import Transaction, UserCredits


class CreditError(Exception):
    pass


def get_credit_balance(db: Session, user_id: str) -> int:
    record = db.query(UserCredits).filter(UserCredits.user_id == user_id).first()
    return record.balance if record else 0


def _ensure_credit_record(db: Session, user_id: str) -> UserCredits:
    record = db.query(UserCredits).filter(UserCredits.user_id == user_id).first()
    if record:
        return record
    record = UserCredits(user_id=user_id, balance=0)
    db.add(record)
    db.flush()
    return record


def add_credits(db: Session, user_id: str, amount: int, payment_id: Optional[str] = None) -> None:
    if amount <= 0:
        raise CreditError("Credit amount must be positive")
    record = _ensure_credit_record(db, user_id)
    record.balance += amount
    db.add(
        Transaction(
            user_id=user_id,
            amount=amount,
            type="purchase",
            metadata={"payment_id": payment_id} if payment_id else None,
        )
    )


def consume_credit(db: Session, user_id: str) -> None:
    record = _ensure_credit_record(db, user_id)
    if record.balance <= 0:
        raise CreditError("Not enough credits")
    record.balance -= 1
    db.add(Transaction(user_id=user_id, amount=-1, type="usage"))
