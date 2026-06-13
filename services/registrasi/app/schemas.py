from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    nama: str
    nik: str
    tanggal_lahir: date
    jenis_kelamin: str
    alamat: Optional[str] = None
    no_telepon: Optional[str] = None
    payment_type: str


class PatientResponse(BaseModel):
    id: int
    nama: str
    nik: str
    tanggal_lahir: Optional[date] = None
    jenis_kelamin: Optional[str] = None
    alamat: Optional[str] = None
    no_telepon: Optional[str] = None
    payment_type: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
