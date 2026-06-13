"""
REST Adapter for Billing Service.
Implements the EIP Channel Adapter pattern for the REST-based Billing system.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

BILLING_SERVICE_URL = os.getenv(
    "BILLING_SERVICE_URL", "http://billing-service:8004"
)

# --- Async versions (for FastAPI route handlers) ---

async def create_billing_account(patient_data: dict) -> dict:
    """Create a billing account in the Billing service (async)."""
    url = f"{BILLING_SERVICE_URL}/api/accounts"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=patient_data)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Billing adapter: created account for patient_id=%s",
                patient_data.get("patient_id", "unknown"),
            )
            return data
    except httpx.ConnectError as e:
        logger.error(
            "Billing adapter: connection error creating account: %s",
            str(e),
        )
        return {"error": "connection_error", "detail": str(e)}
    except httpx.HTTPStatusError as e:
        logger.error(
            "Billing adapter: HTTP %d creating account: %s",
            e.response.status_code,
            str(e),
        )
        return {"error": "http_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(
            "Billing adapter: unexpected error creating account: %s",
            str(e),
        )
        return {"error": "unexpected_error", "detail": str(e)}


async def add_billing_entry(entry_data: dict) -> dict:
    """Add a billing entry to an account in the Billing service (async)."""
    url = f"{BILLING_SERVICE_URL}/api/entries"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=entry_data)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Billing adapter: added entry for patient_id=%s, amount=%s",
                entry_data.get("patient_id", "unknown"),
                entry_data.get("amount", "unknown"),
            )
            return data
    except httpx.ConnectError as e:
        logger.error(
            "Billing adapter: connection error adding entry: %s", str(e)
        )
        return {"error": "connection_error", "detail": str(e)}
    except httpx.HTTPStatusError as e:
        logger.error(
            "Billing adapter: HTTP %d adding entry: %s",
            e.response.status_code,
            str(e),
        )
        return {"error": "http_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(
            "Billing adapter: unexpected error adding entry: %s", str(e)
        )
        return {"error": "unexpected_error", "detail": str(e)}


# --- Sync versions (for RabbitMQ consumer threads) ---

def create_billing_account_sync(patient_data: dict) -> dict:
    """Create a billing account in the Billing service (sync, for consumer threads)."""
    url = f"{BILLING_SERVICE_URL}/api/accounts"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=patient_data)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Billing adapter (sync): created account for patient_id=%s",
                patient_data.get("patient_id", "unknown"),
            )
            return data
    except Exception as e:
        logger.error(
            "Billing adapter (sync): error creating account: %s", str(e)
        )
        return {"error": str(e)}


def add_billing_entry_sync(entry_data: dict) -> dict:
    """Add a billing entry (sync, for consumer threads)."""
    url = f"{BILLING_SERVICE_URL}/api/entries"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=entry_data)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Billing adapter (sync): added entry for patient_id=%s",
                entry_data.get("patient_id", "unknown"),
            )
            return data
    except Exception as e:
        logger.error(
            "Billing adapter (sync): error adding entry: %s", str(e)
        )
        return {"error": str(e)}
