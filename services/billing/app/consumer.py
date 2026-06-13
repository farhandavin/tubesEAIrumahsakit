import os
import json
import logging
import threading
import time
import pika

from app.database import SessionLocal
from app.models import BillingAccount, BillingEntry

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# Queue names — billing consumes from these queues
# The Integration Service's Content-Based Router publishes to these
QUEUE_INSURANCE = "billing.insurance"
QUEUE_CASH = "billing.cash"


def _get_connection():
    """Create a new RabbitMQ connection."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )
    return pika.BlockingConnection(parameters)


def _handle_insurance_billing(ch, method, properties, body):
    """Handle billing.insurance messages — create BillingEntry with BPJS payment."""
    db = SessionLocal()
    try:
        data = json.loads(body)
        patient_id = data.get("patient_id")
        description = data.get("description", "BPJS claim entry")
        amount = float(data.get("amount", 0))
        entry_type = data.get("entry_type", "CONSULTATION")

        # Find the account for this patient
        account = db.query(BillingAccount).filter(
            BillingAccount.patient_id == patient_id
        ).first()

        if account is None:
            raise ValueError(f"BillingAccount not found for patient_id={patient_id}. Requeueing.")

        account_id = account.id

        entry = BillingEntry(
            account_id=account_id,
            description=description,
            amount=amount,
            entry_type=entry_type,
            payment_type="BPJS",
            source_system=data.get("source_system", "integration-service"),
        )
        db.add(entry)
        db.commit()

        logger.info(
            "Created BPJS BillingEntry: patient_id=%s, amount=%.0f, type=%s",
            patient_id,
            amount,
            entry_type,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except ValueError as exc:
        logger.error("Semantic error handling insurance billing (DLQ): %s", exc)
        db.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as exc:
        logger.error("Error handling insurance billing: %s", exc, exc_info=True)
        db.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        db.close()


def _handle_cash_billing(ch, method, properties, body):
    """Handle billing.cash messages — create BillingEntry with UMUM payment."""
    db = SessionLocal()
    try:
        data = json.loads(body)
        patient_id = data.get("patient_id")
        description = data.get("description", "Cash payment entry")
        amount = float(data.get("amount", 0))
        entry_type = data.get("entry_type", "CONSULTATION")

        # Find the account for this patient
        account = db.query(BillingAccount).filter(
            BillingAccount.patient_id == patient_id
        ).first()

        if account is None:
            raise ValueError(f"BillingAccount not found for patient_id={patient_id}. Requeueing.")

        account_id = account.id

        entry = BillingEntry(
            account_id=account_id,
            description=description,
            amount=amount,
            entry_type=entry_type,
            payment_type="UMUM",
            source_system=data.get("source_system", "integration-service"),
        )
        db.add(entry)
        db.commit()

        logger.info(
            "Created UMUM BillingEntry: patient_id=%s, amount=%.0f, type=%s",
            patient_id,
            amount,
            entry_type,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except ValueError as exc:
        logger.error("Semantic error handling cash billing (DLQ): %s", exc)
        db.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as exc:
        logger.error("Error handling cash billing: %s", exc, exc_info=True)
        db.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        db.close()


def start_consumer():
    """Start the RabbitMQ consumer in a loop with reconnection support.

    Billing service consumes from billing.insurance and billing.cash queues.
    The Integration Service's Content-Based Router publishes billing entries
    to these queues based on payment_type (BPJS vs UMUM).
    Billing account creation is done via REST call from the Integration Service.
    """
    while True:
        try:
            logger.info("Connecting to RabbitMQ at %s:%d...", RABBITMQ_HOST, RABBITMQ_PORT)
            connection = _get_connection()
            channel = connection.channel()

            # Declare billing exchange
            channel.exchange_declare(
                exchange="billing.events",
                exchange_type="direct",
                durable=True,
            )

            channel.queue_declare(
                queue=QUEUE_INSURANCE,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "dlx.exchange",
                    "x-dead-letter-routing-key": f"{QUEUE_INSURANCE}.dlq",
                }
            )
            channel.queue_bind(
                exchange="billing.events",
                queue=QUEUE_INSURANCE,
                routing_key="billing.insurance",
            )

            channel.queue_declare(
                queue=QUEUE_CASH,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "dlx.exchange",
                    "x-dead-letter-routing-key": f"{QUEUE_CASH}.dlq",
                }
            )
            channel.queue_bind(
                exchange="billing.events",
                queue=QUEUE_CASH,
                routing_key="billing.cash",
            )

            # Set prefetch
            channel.basic_qos(prefetch_count=1)

            # Register consumers
            channel.basic_consume(
                queue=QUEUE_INSURANCE,
                on_message_callback=_handle_insurance_billing,
            )
            channel.basic_consume(
                queue=QUEUE_CASH,
                on_message_callback=_handle_cash_billing,
            )

            logger.info(
                "Billing consumer started. Listening on queues: %s, %s",
                QUEUE_INSURANCE,
                QUEUE_CASH,
            )

            # Consume with heartbeat
            while True:
                connection.process_data_events(time_limit=1)

        except Exception as exc:
            logger.error("RabbitMQ consumer error: %s. Reconnecting in 5s...", exc)
            time.sleep(5)


def start_consumer_thread():
    """Start the consumer in a daemon thread."""
    thread = threading.Thread(target=start_consumer, daemon=True, name="billing-consumer")
    thread.start()
    logger.info("Billing consumer thread started.")
    return thread
