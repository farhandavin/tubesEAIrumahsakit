"""
RabbitMQ Consumers — the main integration logic.
Consumes messages from queues and orchestrates cross-system workflows:
  1. Patient Registration → EMR + Billing (REST)
  2. Prescription Created  → Farmasi (SOAP) + Billing router
"""

import json
import logging
import threading
import time
from datetime import datetime

from .adapters import emr_adapter, billing_adapter, farmasi_adapter
from .canonical_models import CanonicalBillingEntry
from .transformer import (
    patient_event_to_canonical,
    prescription_event_to_canonical,
    canonical_to_billing_entry,
)
from .router import route_billing_message
from .publishers import get_rabbitmq_connection, setup_exchanges_and_queues

logger = logging.getLogger(__name__)

# Shared activity log for the dashboard
activity_log: list[dict] = []
MAX_ACTIVITY_LOG = 100


def _log_activity(event_type: str, detail: str, status: str = "success") -> None:
    """Append an event to the in-memory activity log for the dashboard."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "detail": detail,
        "status": status,
    }
    activity_log.insert(0, entry)
    if len(activity_log) > MAX_ACTIVITY_LOG:
        activity_log.pop()


def handle_patient_registration(ch, method, properties, body):
    """
    Handle patient.registration.integration queue messages.
    Workflow:
      1. Parse JSON → transform to CanonicalPatient
      2. Call EMR service (REST) to create medical record
      3. Call Billing service (REST) to create billing account
      4. Publish registration fee billing entry via Content-Based Router
      5. Acknowledge message
    """
    try:
        raw = json.loads(body)
        logger.info(
            "CONSUMER: Received patient registration event: %s",
            json.dumps(raw, indent=2)[:500],
        )

        # ── Step 1: Transform ──
        # The publisher wraps patient data in {"event_type": ..., "data": {...}}
        patient_data = raw.get("data", raw)
        patient = patient_event_to_canonical(patient_data)
        logger.info(
            "CONSUMER: Transformed to canonical — patient_id=%d, nama=%s",
            patient.source_id,
            patient.nama,
        )

        # ── Step 2: Call EMR (REST) ──
        emr_result = emr_adapter.create_medical_record_sync(
            {
                "patient_id": patient.source_id,
                "patient_name": patient.nama,
            }
        )
        logger.info("CONSUMER: EMR record created — %s", emr_result)
        _log_activity(
            "patient.registration",
            f"Created EMR record for {patient.nama} (ID: {patient.source_id})",
        )

        # ── Step 3: Call Billing (REST) ──
        billing_result = billing_adapter.create_billing_account_sync(
            {
                "patient_id": patient.source_id,
                "patient_name": patient.nama,
                "payment_type": patient.payment_type,
            }
        )
        logger.info("CONSUMER: Billing account created — %s", billing_result)
        _log_activity(
            "patient.registration",
            f"Created billing account for {patient.nama} ({patient.payment_type})",
        )

        # ── Step 4: Publish registration fee via router ──
        registration_fee = CanonicalBillingEntry(
            patient_id=patient.source_id,
            patient_name=patient.nama,
            description="Registration fee",
            amount=50000.0,  # Standard registration fee
            entry_type="REGISTRATION",
            payment_type=patient.payment_type,
            source_system="integration-service",
            event_type="billing.charge",
            timestamp=datetime.utcnow().isoformat(),
        )
        routed_to = route_billing_message(registration_fee, ch)
        logger.info(
            "CONSUMER: Registration fee routed to %s for patient %d",
            routed_to,
            patient.source_id,
        )
        _log_activity(
            "billing.routed",
            f"Registration fee → {routed_to} for {patient.nama}",
        )

        # ── Step 5: Acknowledge ──
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(
            "CONSUMER: ✅ Patient registration fully processed — patient_id=%d",
            patient.source_id,
        )

    except json.JSONDecodeError as e:
        logger.error("CONSUMER: Invalid JSON in patient event: %s", str(e))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        _log_activity("patient.registration", f"JSON decode error: {e}", "error")
    except Exception as e:
        logger.error(
            "CONSUMER: Error processing patient registration: %s", str(e),
            exc_info=True,
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        _log_activity(
            "patient.registration",
            f"Processing error: {e}",
            "error",
        )


def handle_prescription_created(ch, method, properties, body):
    """
    Handle prescription.created queue messages.
    Workflow:
      1. Parse JSON → transform to CanonicalPrescription
      2. For EACH item: call Farmasi SOAP service to dispense medicine
      3. Collect total price from all dispensation responses
      4. Create CanonicalBillingEntry with total amount
      5. Route billing entry via Content-Based Router (BPJS vs UMUM)
      6. Acknowledge message
    """
    try:
        raw = json.loads(body)
        logger.info(
            "CONSUMER: Received prescription event: %s",
            json.dumps(raw, indent=2)[:500],
        )

        # ── Step 1: Transform ──
        prescription = prescription_event_to_canonical(raw)
        logger.info(
            "CONSUMER: Transformed to canonical — prescription_id=%s, "
            "patient=%s, items=%d",
            prescription.prescription_id,
            prescription.patient_name,
            len(prescription.items),
        )
        _log_activity(
            "prescription.received",
            f"Prescription {prescription.prescription_id} for "
            f"{prescription.patient_name} ({len(prescription.items)} items)",
        )

        # ── Step 2: Call Farmasi SOAP for each item ──
        total_price = 0.0
        dispensation_results = []

        for item in prescription.items:
            logger.info(
                "CONSUMER: Dispatching SOAP call → dispense %s (qty=%d)",
                item.medicine_name,
                item.quantity,
            )
            result = farmasi_adapter.dispense_medicine(
                prescription_id=prescription.prescription_id,
                patient_id=prescription.patient_id,
                patient_name=prescription.patient_name,
                medicine_name=item.medicine_name,
                quantity=item.quantity,
            )
            dispensation_results.append(result)

            # Extract price from SOAP response
            price = float(result.get("total_price", result.get("price", 0)))
            total_price += price
            logger.info(
                "CONSUMER: Dispensed %s — price=%.2f", item.medicine_name, price
            )
            _log_activity(
                "farmasi.soap",
                f"Dispensed {item.medicine_name} (qty={item.quantity}) → "
                f"price={price:.0f}",
            )

        logger.info(
            "CONSUMER: All items dispensed — total_price=%.2f", total_price
        )

        # ── Step 3: Create billing entry ──
        billing_entry = canonical_to_billing_entry(prescription, total_price)
        logger.info(
            "CONSUMER: Created billing entry — amount=%.2f, payment_type=%s",
            billing_entry.amount,
            billing_entry.payment_type,
        )

        # ── Step 4: Route billing via Content-Based Router ──
        routed_to = route_billing_message(billing_entry, ch)
        logger.info(
            "CONSUMER: Prescription billing routed to %s", routed_to
        )
        _log_activity(
            "billing.routed",
            f"Prescription {prescription.prescription_id} → {routed_to} "
            f"(amount={total_price:.0f})",
        )

        # ── Step 5: Acknowledge ──
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(
            "CONSUMER: ✅ Prescription fully processed — id=%s, total=%.2f",
            prescription.prescription_id,
            total_price,
        )

    except json.JSONDecodeError as e:
        logger.error("CONSUMER: Invalid JSON in prescription event: %s", str(e))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        _log_activity("prescription.created", f"JSON decode error: {e}", "error")
    except Exception as e:
        logger.error(
            "CONSUMER: Error processing prescription: %s", str(e),
            exc_info=True,
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        _log_activity(
            "prescription.created",
            f"Processing error: {e}",
            "error",
        )


def start_consumers() -> None:
    """
    Start RabbitMQ consumers in daemon threads.
    Consumers:
      a. patient.registration.integration → handle_patient_registration
      b. prescription.created → handle_prescription_created
    """
    def _run_consumer(queue_name: str, callback, consumer_name: str):
        """Run a single consumer with reconnection logic."""
        while True:
            try:
                logger.info(
                    "CONSUMER [%s]: Connecting to RabbitMQ...", consumer_name
                )
                connection = get_rabbitmq_connection(max_retries=15, retry_delay=5.0)
                channel = connection.channel()

                # Setup exchanges and queues (idempotent)
                setup_exchanges_and_queues(channel)

                # Prefetch 1 message at a time for fair dispatch
                channel.basic_qos(prefetch_count=1)

                channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=callback,
                    auto_ack=False,
                )

                logger.info(
                    "CONSUMER [%s]: ✅ Listening on queue '%s'",
                    consumer_name,
                    queue_name,
                )
                _log_activity(
                    "consumer.started",
                    f"Consumer '{consumer_name}' listening on '{queue_name}'",
                )

                channel.start_consuming()

            except Exception as e:
                logger.error(
                    "CONSUMER [%s]: Connection lost — %s. Reconnecting in 5s...",
                    consumer_name,
                    str(e),
                )
                _log_activity(
                    "consumer.error",
                    f"Consumer '{consumer_name}' disconnected: {e}",
                    "error",
                )
                time.sleep(5)

    # Start patient registration consumer thread
    patient_thread = threading.Thread(
        target=_run_consumer,
        args=(
            "patient.registration.integration",
            handle_patient_registration,
            "PatientRegistration",
        ),
        daemon=True,
        name="consumer-patient-registration",
    )
    patient_thread.start()
    logger.info("Started consumer thread: PatientRegistration")

    # Start prescription consumer thread
    prescription_thread = threading.Thread(
        target=_run_consumer,
        args=(
            "prescription.created",
            handle_prescription_created,
            "PrescriptionCreated",
        ),
        daemon=True,
        name="consumer-prescription-created",
    )
    prescription_thread.start()
    logger.info("Started consumer thread: PrescriptionCreated")

    logger.info("✅ All consumer threads started")
