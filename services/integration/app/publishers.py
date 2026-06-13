"""
RabbitMQ Publisher Utility — manages connections, exchanges, queues, and bindings.
Implements the EIP Messaging Infrastructure with Dead Letter Queue support.
"""

import json
import logging
import os
import time

import pika

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")


def get_rabbitmq_connection(max_retries: int = 10, retry_delay: float = 5.0) -> pika.BlockingConnection:
    """
    Create a RabbitMQ blocking connection with retry logic.
    Retries up to max_retries times with retry_delay seconds between attempts.
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )

    for attempt in range(1, max_retries + 1):
        try:
            connection = pika.BlockingConnection(parameters)
            logger.info(
                "RabbitMQ connection established (attempt %d/%d) → %s:%d",
                attempt,
                max_retries,
                RABBITMQ_HOST,
                RABBITMQ_PORT,
            )
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(
                "RabbitMQ connection attempt %d/%d failed: %s — retrying in %.1fs",
                attempt,
                max_retries,
                str(e),
                retry_delay,
            )
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error(
                    "RabbitMQ connection failed after %d attempts", max_retries
                )
                raise


def publish_message(exchange: str, routing_key: str, message: dict) -> None:
    """
    Publish a JSON message to the specified exchange with the given routing key.
    Opens a fresh connection per publish (suitable for low-frequency publishes
    from FastAPI handlers).
    """
    try:
        connection = get_rabbitmq_connection(max_retries=3, retry_delay=2.0)
        channel = connection.channel()

        body = json.dumps(message)
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type="application/json",
            ),
        )

        logger.info(
            "Published message → exchange='%s', routing_key='%s', size=%d bytes",
            exchange,
            routing_key,
            len(body),
        )
        connection.close()
    except Exception as e:
        logger.error(
            "Failed to publish message to exchange='%s', routing_key='%s': %s",
            exchange,
            routing_key,
            str(e),
        )
        raise


def setup_exchanges_and_queues(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """
    Declare all exchanges, queues, and bindings for the Hospital EAI system.

    Topology:
    ─────────────────────────────────────────────────────
    Exchange: dlx.exchange (direct)
      └── *.dlq queues (dead-letter destinations)

    Exchange: patient.events (fanout)
      ├── patient.registration.emr
      ├── patient.registration.billing
      └── patient.registration.integration

    Exchange: prescription.events (direct)
      └── prescription.created  (routing_key: prescription.created)

    Exchange: billing.events (direct)
      ├── billing.insurance  (routing_key: billing.insurance)
      └── billing.cash       (routing_key: billing.cash)
    ─────────────────────────────────────────────────────
    """
    logger.info("Setting up RabbitMQ exchanges, queues, and bindings...")

    # ── Dead Letter Exchange ──
    channel.exchange_declare(
        exchange="dlx.exchange", exchange_type="direct", durable=True
    )
    logger.info("Declared exchange: dlx.exchange (direct)")

    # ── Helper: declare a main queue with its DLQ ──
    def _declare_with_dlq(queue_name: str) -> None:
        # DLQ queue
        dlq_name = f"{queue_name}.dlq"
        channel.queue_declare(queue=dlq_name, durable=True)
        channel.queue_bind(
            queue=dlq_name, exchange="dlx.exchange", routing_key=dlq_name
        )
        logger.info("Declared DLQ: %s → bound to dlx.exchange", dlq_name)

        # Main queue with dead-letter routing
        channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx.exchange",
                "x-dead-letter-routing-key": dlq_name,
            },
        )
        logger.info("Declared queue: %s (DLQ → %s)", queue_name, dlq_name)

    # ── Patient Events (Fanout) ──
    channel.exchange_declare(
        exchange="patient.events", exchange_type="fanout", durable=True
    )
    logger.info("Declared exchange: patient.events (fanout)")

    for q in [
        "patient.registration.emr",
        "patient.registration.billing",
        "patient.registration.integration",
    ]:
        _declare_with_dlq(q)
        channel.queue_bind(queue=q, exchange="patient.events")
        logger.info("Bound %s → patient.events (fanout)", q)

    # ── Prescription Events (Direct) ──
    channel.exchange_declare(
        exchange="prescription.events", exchange_type="direct", durable=True
    )
    logger.info("Declared exchange: prescription.events (direct)")

    _declare_with_dlq("prescription.created")
    channel.queue_bind(
        queue="prescription.created",
        exchange="prescription.events",
        routing_key="prescription.created",
    )
    logger.info(
        "Bound prescription.created → prescription.events (key: prescription.created)"
    )

    # ── Billing Events (Direct) ──
    channel.exchange_declare(
        exchange="billing.events", exchange_type="direct", durable=True
    )
    logger.info("Declared exchange: billing.events (direct)")

    for q in ["billing.insurance", "billing.cash"]:
        _declare_with_dlq(q)
        channel.queue_bind(
            queue=q, exchange="billing.events", routing_key=q
        )
        logger.info("Bound %s → billing.events (key: %s)", q, q)

    logger.info("✅ All exchanges, queues, and bindings configured successfully")
