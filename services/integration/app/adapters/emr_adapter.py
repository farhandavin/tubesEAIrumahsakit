"""
REST Adapter for EMR (Electronic Medical Record) Service.
Implements the EIP Channel Adapter pattern for the REST-based EMR system.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

EMR_SERVICE_URL = os.getenv("EMR_SERVICE_URL", "http://emr-service:8002")

# --- Async versions (for FastAPI route handlers) ---

async def create_medical_record(patient_data: dict) -> dict:
    """Create a medical record in the EMR service (async)."""
    url = f"{EMR_SERVICE_URL}/api/records"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=patient_data)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "EMR adapter: created medical record for patient_id=%s",
                patient_data.get("patient_id", "unknown"),
            )
            return data
    except httpx.ConnectError as e:
        logger.error("EMR adapter: connection error creating record: %s", str(e))
        return {"error": "connection_error", "detail": str(e)}
    except httpx.HTTPStatusError as e:
        logger.error(
            "EMR adapter: HTTP %d creating record: %s",
            e.response.status_code,
            str(e),
        )
        return {"error": "http_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error("EMR adapter: unexpected error creating record: %s", str(e))
        return {"error": "unexpected_error", "detail": str(e)}


async def get_medical_record(patient_id: int) -> dict:
    """Get a medical record by patient ID from EMR service (async)."""
    url = f"{EMR_SERVICE_URL}/api/records/{patient_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "EMR adapter: fetched record for patient_id=%d", patient_id
            )
            return data
    except httpx.ConnectError as e:
        logger.error(
            "EMR adapter: connection error fetching record %d: %s",
            patient_id,
            str(e),
        )
        return {"error": "connection_error", "detail": str(e)}
    except httpx.HTTPStatusError as e:
        logger.error(
            "EMR adapter: HTTP %d fetching record %d: %s",
            e.response.status_code,
            patient_id,
            str(e),
        )
        return {"error": "http_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(
            "EMR adapter: unexpected error fetching record %d: %s",
            patient_id,
            str(e),
        )
        return {"error": "unexpected_error", "detail": str(e)}


# --- Sync versions (for RabbitMQ consumer threads) ---

def create_medical_record_sync(patient_data: dict) -> dict:
    """Create a medical record in the EMR service (sync, for consumer threads)."""
    url = f"{EMR_SERVICE_URL}/api/records"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=patient_data)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "EMR adapter (sync): created record for patient_id=%s",
                patient_data.get("patient_id", "unknown"),
            )
            return data
    except Exception as e:
        logger.error(
            "EMR adapter (sync): error creating record: %s", str(e)
        )
        return {"error": str(e)}


def get_medical_record_sync(patient_id: int) -> dict:
    """Get a medical record by patient ID from EMR service (sync)."""
    url = f"{EMR_SERVICE_URL}/api/records/{patient_id}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "EMR adapter (sync): fetched record for patient_id=%d",
                patient_id,
            )
            return data
    except Exception as e:
        logger.error(
            "EMR adapter (sync): error fetching record %d: %s",
            patient_id,
            str(e),
        )
        return {"error": str(e)}
