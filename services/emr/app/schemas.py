from typing import List, Optional
from pydantic import BaseModel, Field


class PrescriptionItem(BaseModel):
    medicine_name: str
    quantity: int
    dosage: str


class PrescriptionCreate(BaseModel):
    doctor_name: str
    diagnosis: str
    items: List[PrescriptionItem]


class MedicalRecordCreate(BaseModel):
    patient_id: int
    patient_name: str


class MedicalRecordResponse(BaseModel):
    id: str = Field(alias="_id")
    patient_id: int
    patient_name: str
    diagnoses: List[str] = []
    prescriptions: List[dict] = []
    created_at: str

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class PrescriptionResponse(BaseModel):
    prescription_id: str
    patient_id: int
    patient_name: str
    doctor_name: str
    diagnosis: str
    items: List[PrescriptionItem]
    payment_type: str
    created_at: str
