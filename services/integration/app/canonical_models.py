"""
Canonical Data Model — Unified Pydantic schemas for the Hospital EAI Integration Layer.
These models serve as the internal message format (Canonical Data Model pattern)
ensuring all systems communicate using a shared vocabulary.
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CanonicalPatient(BaseModel):
    source_id: int
    nama: str
    nik: str
    tanggal_lahir: str
    jenis_kelamin: str
    alamat: str
    no_telepon: str
    payment_type: str  # BPJS or UMUM
    event_type: str = "patient.registered"
    timestamp: str = ""


class CanonicalPrescriptionItem(BaseModel):
    medicine_name: str
    quantity: int
    dosage: str


class CanonicalPrescription(BaseModel):
    prescription_id: str
    patient_id: int
    patient_name: str
    doctor_name: str
    diagnosis: str
    items: List[CanonicalPrescriptionItem]
    payment_type: str  # BPJS or UMUM
    event_type: str = "prescription.created"
    timestamp: str = ""


class CanonicalBillingEntry(BaseModel):
    patient_id: int
    patient_name: str
    description: str
    amount: float
    entry_type: str  # REGISTRATION, PRESCRIPTION
    payment_type: str  # BPJS or UMUM
    source_system: str
    event_type: str = "billing.charge"
    timestamp: str = ""
