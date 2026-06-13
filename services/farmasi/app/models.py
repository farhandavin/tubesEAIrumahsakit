import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base

logger = logging.getLogger(__name__)


class Medicine(Base):
    """Represents a medicine item in the pharmacy inventory."""

    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nama_obat = Column(String(100), nullable=False)
    stok = Column(Integer, default=100)
    harga = Column(Float, nullable=False)
    satuan = Column(String(20))  # e.g. 'tablet', 'kapsul', 'botol', 'ampul'

    def to_dict(self):
        return {
            "id": self.id,
            "nama_obat": self.nama_obat,
            "stok": self.stok,
            "harga": self.harga,
            "satuan": self.satuan,
        }


class Dispensation(Base):
    """Represents a medicine dispensation record."""

    __tablename__ = "dispensations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prescription_id = Column(String(100))
    patient_id = Column(Integer)
    patient_name = Column(String(100))
    medicine_name = Column(String(100))
    quantity = Column(Integer)
    total_price = Column(Float)
    status = Column(String(20), default="DISPENSED")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "prescription_id": self.prescription_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "medicine_name": self.medicine_name,
            "quantity": self.quantity,
            "total_price": self.total_price,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
