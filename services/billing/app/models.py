from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class BillingAccount(Base):
    __tablename__ = "billing_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    patient_name = Column(String(100))
    payment_type = Column(String(10))  # 'BPJS' or 'UMUM'
    status = Column(String(20), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    entries = relationship("BillingEntry", back_populates="account", lazy="joined")


class BillingEntry(Base):
    __tablename__ = "billing_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("billing_accounts.id"))
    description = Column(String(255))
    amount = Column(Float, default=0.0)
    entry_type = Column(String(30))  # 'REGISTRATION', 'PRESCRIPTION', 'CONSULTATION'
    payment_type = Column(String(10))  # 'BPJS' or 'UMUM'
    source_system = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("BillingAccount", back_populates="entries")
