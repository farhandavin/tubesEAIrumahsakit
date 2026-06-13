import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient
from app.schemas import PatientCreate, PatientResponse
from app.publisher import publish_patient_registered

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/patients", response_model=PatientResponse, status_code=201)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    """Register a new patient and publish event to RabbitMQ."""
    # Check for duplicate NIK
    existing = db.query(Patient).filter(Patient.nik == patient.nik).first()
    if existing:
        raise HTTPException(status_code=400, detail="NIK sudah terdaftar")

    db_patient = Patient(
        nama=patient.nama,
        nik=patient.nik,
        tanggal_lahir=patient.tanggal_lahir,
        jenis_kelamin=patient.jenis_kelamin,
        alamat=patient.alamat,
        no_telepon=patient.no_telepon,
        payment_type=patient.payment_type,
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    logger.info("Patient created: id=%d, nama=%s", db_patient.id, db_patient.nama)

    # Publish event to RabbitMQ
    patient_data = {
        "id": db_patient.id,
        "nama": db_patient.nama,
        "nik": db_patient.nik,
        "tanggal_lahir": str(db_patient.tanggal_lahir) if db_patient.tanggal_lahir else None,
        "jenis_kelamin": db_patient.jenis_kelamin,
        "alamat": db_patient.alamat,
        "no_telepon": db_patient.no_telepon,
        "payment_type": db_patient.payment_type,
    }
    publish_patient_registered(patient_data)

    return db_patient


@router.get("/patients", response_model=List[PatientResponse])
def list_patients(db: Session = Depends(get_db)):
    """List all registered patients."""
    patients = db.query(Patient).order_by(Patient.created_at.desc()).all()
    return patients


@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get a single patient by ID."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Pasien tidak ditemukan")
    return patient


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "registrasi"}
