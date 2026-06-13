import os
import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import List

import httpx
from fastapi import APIRouter, HTTPException

from .database import medical_records_collection
from .schemas import (
    MedicalRecordCreate,
    MedicalRecordResponse,
    PrescriptionCreate,
    PrescriptionResponse,
)
from .publisher import publish_prescription_created

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

REGISTRASI_SERVICE_HOST = os.getenv("REGISTRASI_SERVICE_HOST", "registrasi-service")
REGISTRASI_SERVICE_PORT = os.getenv("REGISTRASI_SERVICE_PORT", "8001")


@router.post("/records", response_model=dict)
async def create_medical_record(record: MedicalRecordCreate):
    """Create a new medical record for a patient."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Atomic upsert
    await medical_records_collection.update_one(
        {"patient_id": record.patient_id},
        {
            "$setOnInsert": {
                "patient_name": record.patient_name,
                "diagnoses": [],
                "prescriptions": [],
                "visits": [],
                "created_at": now,
            }
        },
        upsert=True
    )
    
    # Fetch the document to get the inserted or existing MongoDB _id
    doc = await medical_records_collection.find_one({"patient_id": record.patient_id})
    doc_id = str(doc["_id"]) if doc else ""

    logger.info(f"Upserted EMR record for patient_id={record.patient_id}")

    return {
        "message": "Medical record created",
        "id": doc_id,
        "patient_id": record.patient_id,
    }


@router.get("/records", response_model=List[dict])
async def list_medical_records():
    """List all medical records."""
    records = []
    cursor = medical_records_collection.find()
    async for record in cursor:
        record["_id"] = str(record["_id"])
        records.append(record)
    return records


@router.get("/records/{patient_id}", response_model=dict)
async def get_medical_record(patient_id: int):
    """Get a medical record by patient_id."""
    record = await medical_records_collection.find_one({"patient_id": patient_id})
    if not record:
        raise HTTPException(status_code=404, detail=f"Medical record not found for patient_id={patient_id}")

    record["_id"] = str(record["_id"])
    return record


@router.post("/records/{patient_id}/prescriptions", response_model=PrescriptionResponse)
async def add_prescription(patient_id: int, prescription: PrescriptionCreate):
    """Add a prescription to a patient's medical record."""
    # 1. Find the medical record
    record = await medical_records_collection.find_one({"patient_id": patient_id})
    if not record:
        raise HTTPException(status_code=404, detail=f"Medical record not found for patient_id={patient_id}")

    patient_name = record["patient_name"]

    # 2. Generate prescription_id
    prescription_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # 3. Get payment_type from Registrasi service
    payment_type = "UNKNOWN"
    try:
        registrasi_url = f"http://{REGISTRASI_SERVICE_HOST}:{REGISTRASI_SERVICE_PORT}/api/patients/{patient_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(registrasi_url)
            if response.status_code == 200:
                patient_data = response.json()
                payment_type = patient_data.get("payment_type", "UNKNOWN")
                logger.info(f"Got payment_type={payment_type} for patient_id={patient_id}")
            else:
                logger.warning(f"Registrasi service returned {response.status_code} for patient_id={patient_id}")
    except Exception as e:
        logger.error(f"Failed to fetch payment_type from Registrasi service: {e}")

    # 4. Build prescription document
    prescription_doc = {
        "prescription_id": prescription_id,
        "doctor_name": prescription.doctor_name,
        "diagnosis": prescription.diagnosis,
        "items": [item.model_dump() for item in prescription.items],
        "payment_type": payment_type,
        "created_at": now,
    }

    # 5. Append prescription to record's prescriptions array
    await medical_records_collection.update_one(
        {"patient_id": patient_id},
        {"$push": {"prescriptions": prescription_doc}},
    )

    # 6. Add diagnosis if not already present
    await medical_records_collection.update_one(
        {"patient_id": patient_id},
        {"$addToSet": {"diagnoses": prescription.diagnosis}},
    )

    logger.info(f"Added prescription {prescription_id} to patient_id={patient_id}")

    # 7. Publish prescription.created event
    event_data = {
        "prescription_id": prescription_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "doctor_name": prescription.doctor_name,
        "diagnosis": prescription.diagnosis,
        "items": [item.model_dump() for item in prescription.items],
        "payment_type": payment_type,
        "created_at": now,
    }

    try:
        publish_prescription_created(event_data)
    except Exception as e:
        logger.error(f"Failed to publish prescription event: {e}")

    # 8. Return response
    return PrescriptionResponse(
        prescription_id=prescription_id,
        patient_id=patient_id,
        patient_name=patient_name,
        doctor_name=prescription.doctor_name,
        diagnosis=prescription.diagnosis,
        items=prescription.items,
        payment_type=payment_type,
        created_at=now,
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "emr"}
