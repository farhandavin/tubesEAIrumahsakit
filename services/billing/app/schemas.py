from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class BillingAccountCreate(BaseModel):
    patient_id: int
    patient_name: str
    payment_type: str


class BillingEntryResponse(BaseModel):
    id: int
    account_id: Optional[int] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    entry_type: Optional[str] = None
    payment_type: Optional[str] = None
    source_system: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BillingAccountResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    payment_type: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    entries: List[BillingEntryResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BillingEntryCreate(BaseModel):
    account_id: Optional[int] = None
    patient_id: int
    description: str
    amount: float
    entry_type: str
    payment_type: str
    source_system: str
