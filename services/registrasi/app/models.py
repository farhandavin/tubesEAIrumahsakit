from sqlalchemy import Column, Integer, String, Date, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nama = Column(String(100), nullable=False)
    nik = Column(String(16), unique=True, nullable=False)
    tanggal_lahir = Column(Date)
    jenis_kelamin = Column(String(1))  # 'L' or 'P'
    alamat = Column(Text)
    no_telepon = Column(String(15))
    payment_type = Column(String(10))  # 'BPJS' or 'UMUM'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
