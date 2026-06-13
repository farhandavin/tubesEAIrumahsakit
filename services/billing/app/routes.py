import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BillingAccount, BillingEntry
from app.schemas import (
    BillingAccountCreate,
    BillingAccountResponse,
    BillingEntryCreate,
    BillingEntryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/accounts", response_model=BillingAccountResponse, status_code=201)
def create_account(account: BillingAccountCreate, db: Session = Depends(get_db)):
    """Create a new billing account."""
    db_account = BillingAccount(
        patient_id=account.patient_id,
        patient_name=account.patient_name,
        payment_type=account.payment_type,
        status="ACTIVE",
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    logger.info("Created BillingAccount id=%d for patient_id=%d", db_account.id, db_account.patient_id)
    return db_account


@router.get("/accounts", response_model=List[BillingAccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    """List all billing accounts with their entries."""
    accounts = (
        db.query(BillingAccount)
        .order_by(BillingAccount.created_at.desc())
        .all()
    )
    return accounts


@router.get("/accounts/{patient_id}", response_model=BillingAccountResponse)
def get_account_by_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get billing account by patient_id."""
    account = (
        db.query(BillingAccount)
        .filter(BillingAccount.patient_id == patient_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Billing account tidak ditemukan untuk patient_id ini")
    return account


@router.get("/entries", response_model=List[BillingEntryResponse])
def list_entries(db: Session = Depends(get_db)):
    """List all billing entries."""
    entries = (
        db.query(BillingEntry)
        .order_by(BillingEntry.created_at.desc())
        .all()
    )
    return entries


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "billing"}
