"""
FastAPI Routes for the Integration Service.
Provides health checks, status monitoring, and manual test triggers.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import pika
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .publishers import get_rabbitmq_connection, publish_message, RABBITMQ_HOST, RABBITMQ_PORT
from .consumers import activity_log
from .adapters.registrasi_adapter import REGISTRASI_SERVICE_URL
from .adapters.emr_adapter import EMR_SERVICE_URL
from .adapters.farmasi_adapter import FARMASI_SERVICE_URL
from .adapters.billing_adapter import BILLING_SERVICE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Integration"])


# ── Request Models ──

class PatientRegistrationTest(BaseModel):
    id: int = 1
    nama: str = "Test Patient"
    nik: str = "1234567890123456"
    tanggal_lahir: str = "1990-01-01"
    jenis_kelamin: str = "Laki-laki"
    alamat: str = "Jl. Test No. 1"
    no_telepon: str = "081234567890"
    payment_type: str = "UMUM"


class PrescriptionItemTest(BaseModel):
    medicine_name: str = "Paracetamol"
    quantity: int = 10
    dosage: str = "3x1"


class PrescriptionTest(BaseModel):
    prescription_id: str = "RX-TEST-001"
    patient_id: int = 1
    patient_name: str = "Test Patient"
    doctor_name: str = "Dr. Test"
    diagnosis: str = "Test Diagnosis"
    items: list[PrescriptionItemTest] = [PrescriptionItemTest()]
    payment_type: str = "UMUM"


# ── Health Check ──

@router.get("/health")
async def health_check():
    """Health check including RabbitMQ connection status."""
    rabbitmq_ok = False
    rabbitmq_detail = ""

    try:
        connection = get_rabbitmq_connection(max_retries=1, retry_delay=1.0)
        rabbitmq_ok = connection.is_open
        connection.close()
        rabbitmq_detail = f"Connected to {RABBITMQ_HOST}:{RABBITMQ_PORT}"
    except Exception as e:
        rabbitmq_detail = f"Connection failed: {str(e)}"

    return {
        "status": "healthy" if rabbitmq_ok else "degraded",
        "service": "integration-service",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "rabbitmq": {
                "status": "connected" if rabbitmq_ok else "disconnected",
                "detail": rabbitmq_detail,
            },
            "registrasi": {
                "url": REGISTRASI_SERVICE_URL,
                "protocol": "REST",
            },
            "emr": {
                "url": EMR_SERVICE_URL,
                "protocol": "REST",
            },
            "farmasi": {
                "url": FARMASI_SERVICE_URL,
                "protocol": "SOAP/XML",
            },
            "billing": {
                "url": BILLING_SERVICE_URL,
                "protocol": "REST",
            },
        },
    }


# ── Status ──

@router.get("/status")
async def get_status():
    """
    Return integration service status: connected systems, queue info,
    and recent activity log.
    """
    # Try to get queue depths
    queue_info = {}
    queues_to_check = [
        "patient.registration.integration",
        "prescription.created",
        "billing.insurance",
        "billing.cash",
    ]

    try:
        connection = get_rabbitmq_connection(max_retries=1, retry_delay=1.0)
        channel = connection.channel()
        for q in queues_to_check:
            try:
                result = channel.queue_declare(queue=q, passive=True)
                queue_info[q] = {
                    "message_count": result.method.message_count,
                    "consumer_count": result.method.consumer_count,
                }
            except Exception:
                queue_info[q] = {"message_count": -1, "consumer_count": 0}
                # Reopen channel after exception
                channel = connection.channel()
        connection.close()
    except Exception as e:
        logger.warning("Could not fetch queue depths: %s", str(e))
        for q in queues_to_check:
            queue_info[q] = {"error": "unable to connect"}

    return {
        "service": "integration-service",
        "timestamp": datetime.utcnow().isoformat(),
        "connected_systems": {
            "registrasi": {"url": REGISTRASI_SERVICE_URL, "protocol": "REST"},
            "emr": {"url": EMR_SERVICE_URL, "protocol": "REST"},
            "farmasi": {"url": FARMASI_SERVICE_URL, "protocol": "SOAP/XML"},
            "billing": {"url": BILLING_SERVICE_URL, "protocol": "REST"},
        },
        "queues": queue_info,
        "eip_patterns": [
            "Canonical Data Model",
            "Message Translator",
            "Content-Based Router",
            "Channel Adapter",
            "Publish-Subscribe",
            "Dead Letter Channel",
        ],
        "recent_activity": activity_log[:20],
    }


# ── Test Triggers ──

@router.post("/test/patient-registration")
async def test_patient_registration(patient: PatientRegistrationTest):
    """
    Manual trigger: publish a patient registration event to patient.events exchange.
    Useful for testing the full integration flow without the Registrasi UI.
    """
    try:
        message = patient.model_dump()
        message["event_type"] = "patient.registered"
        message["timestamp"] = datetime.utcnow().isoformat()

        publish_message(
            exchange="patient.events",
            routing_key="",  # fanout ignores routing key
            message=message,
        )

        logger.info(
            "TEST: Published patient registration event for patient_id=%d",
            patient.id,
        )
        return {
            "status": "published",
            "exchange": "patient.events",
            "message": message,
        }
    except Exception as e:
        logger.error("TEST: Failed to publish patient event: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/prescription")
async def test_prescription(prescription: PrescriptionTest):
    """
    Manual trigger: publish a prescription event to prescription.events exchange.
    Useful for testing the Farmasi SOAP integration and billing routing.
    """
    try:
        message = prescription.model_dump()
        message["event_type"] = "prescription.created"
        message["timestamp"] = datetime.utcnow().isoformat()

        publish_message(
            exchange="prescription.events",
            routing_key="prescription.created",
            message=message,
        )

        logger.info(
            "TEST: Published prescription event id=%s",
            prescription.prescription_id,
        )
        return {
            "status": "published",
            "exchange": "prescription.events",
            "routing_key": "prescription.created",
            "message": message,
        }
    except Exception as e:
        logger.error("TEST: Failed to publish prescription event: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
