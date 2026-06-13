"""
REST Adapter for Registrasi (Patient Registration) Service.
Implements the EIP Channel Adapter pattern for the REST-based Registrasi system.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

REGISTRASI_SERVICE_URL = os.getenv(
    "REGISTRASI_SERVICE_URL", "http://registrasi-service:8001"
)

# --- Async versions (for FastAPI route handlers) ---

async def get_patient(patient_id: int) -> dict:
    """Fetch a patient by ID from Registrasi service (async)."""
    url = f"{REGISTRASI_SERVICE_URL}/api/patients/{patient_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Registrasi adapter: fetched patient %d successfully", patient_id
            )
            return data
    except httpx.ConnectError as e:
        logger.error(
            "Registrasi adapter: connection error fetching patient %d: %s",
            patient_id,
            str(e),
        )
        return {"error": "connection_error", "detail": str(e)}
    except httpx.HTTPStatusError as e:
        logger.error(
            "Registrasi adapter: HTTP %d fetching patient %d: %s",
            e.response.status_code,
            patient_id,
            str(e),
        )
        return {"error": "http_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(
            "Registrasi adapter: unexpected error fetching patient %d: %s",
            patient_id,
            str(e),
        )
        return {"error": "unexpected_error", "detail": str(e)}


async def list_patients() -> list:
    """List all patients from Registrasi service (async)."""
    url = f"{REGISTRASI_SERVICE_URL}/api/patients"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Registrasi adapter: listed %d patients", len(data)
            )
            return data
    except httpx.ConnectError as e:
        logger.error(
            "Registrasi adapter: connection error listing patients: %s",
            str(e),
        )
        return []
    except Exception as e:
        logger.error(
            "Registrasi adapter: unexpected error listing patients: %s",
            str(e),
        )
        return []


# --- Sync versions (for RabbitMQ consumer threads) ---

def get_patient_sync(patient_id: int) -> dict:
    """Fetch a patient by ID from Registrasi service (sync)."""
    url = f"{REGISTRASI_SERVICE_URL}/api/patients/{patient_id}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Registrasi adapter (sync): fetched patient %d", patient_id
            )
            return data
    except Exception as e:
        logger.error(
            "Registrasi adapter (sync): error fetching patient %d: %s",
            patient_id,
            str(e),
        )
        return {"error": str(e)}
