"""
Content-Based Router — routes messages to the correct destination based on
message content. Implements the EIP Content-Based Router pattern.
"""

import json
import logging
from typing import List

import pika

from .canonical_models import CanonicalBillingEntry, CanonicalPatient

logger = logging.getLogger(__name__)


def route_billing_message(
    billing_entry: CanonicalBillingEntry, channel: pika.adapters.blocking_connection.BlockingChannel
) -> str:
    """
    Route billing message based on payment_type.
    - BPJS → billing.insurance queue via billing.events exchange
    - UMUM → billing.cash queue via billing.events exchange
    """
    try:
        payment_type = billing_entry.payment_type.upper()
        if payment_type == "BPJS":
            routing_key = "billing.insurance"
            target_queue = "billing.insurance"
        else:
            routing_key = "billing.cash"
            target_queue = "billing.cash"

        message_body = json.dumps(billing_entry.model_dump())

        channel.basic_publish(
            exchange="billing.events",
            routing_key=routing_key,
            body=message_body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type="application/json",
            ),
        )

        logger.info(
            "ROUTER: Billing message routed → exchange='billing.events', "
            "routing_key='%s', target_queue='%s', payment_type='%s', "
            "patient_id=%d, amount=%.2f",
            routing_key,
            target_queue,
            payment_type,
            billing_entry.patient_id,
            billing_entry.amount,
        )
        return target_queue

    except Exception as e:
        logger.error("Failed to route billing message: %s", str(e))
        raise


def route_patient_event(
    patient: CanonicalPatient, channel: pika.adapters.blocking_connection.BlockingChannel
) -> List[str]:
    """
    Publish patient event to the fanout exchange patient.events.
    The fanout exchange delivers to all bound queues:
      - patient.registration.emr
      - patient.registration.billing
      - patient.registration.integration
    """
    try:
        message_body = json.dumps(patient.model_dump())

        channel.basic_publish(
            exchange="patient.events",
            routing_key="",  # fanout exchange ignores routing key
            body=message_body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )

        target_queues = [
            "patient.registration.emr",
            "patient.registration.billing",
            "patient.registration.integration",
        ]

        logger.info(
            "ROUTER: Patient event published → fanout exchange='patient.events', "
            "patient_id=%d, nama='%s', targets=%s",
            patient.source_id,
            patient.nama,
            target_queues,
        )
        return target_queues

    except Exception as e:
        logger.error("Failed to route patient event: %s", str(e))
        raise
