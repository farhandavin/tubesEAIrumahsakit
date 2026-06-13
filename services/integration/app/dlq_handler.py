"""
Dead Letter Queue Handler — processes messages that failed delivery.
Implements retry logic with exponential backoff and permanent failure logging.
"""

import json
import logging
import threading
import time

import pika

from .publishers import get_rabbitmq_connection

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# All DLQ queue names
DLQ_QUEUES = [
    "patient.registration.emr.dlq",
    "patient.registration.billing.dlq",
    "patient.registration.integration.dlq",
    "prescription.created.dlq",
    "billing.insurance.dlq",
    "billing.cash.dlq",
]


def _get_retry_count(properties: pika.BasicProperties) -> int:
    """Extract retry count from x-death headers."""
    if properties.headers and "x-death" in properties.headers:
        x_death = properties.headers["x-death"]
        if isinstance(x_death, list) and len(x_death) > 0:
            count = x_death[0].get("count", 0)
            return int(count)
    return 0


def _get_original_queue(properties: pika.BasicProperties, dlq_name: str) -> str:
    """Determine the original queue name from the DLQ name."""
    # DLQ name is "{original_queue}.dlq"
    if dlq_name.endswith(".dlq"):
        return dlq_name[:-4]
    return ""


def handle_dlq_message(ch, method, properties, body):
    """
    Handle a dead-lettered message.
    - If retry_count < MAX_RETRIES: republish to original queue with a delay
    - If retry_count >= MAX_RETRIES: log as permanently failed and acknowledge
    """
    dlq_name = method.routing_key
    retry_count = _get_retry_count(properties)
    original_queue = _get_original_queue(properties, dlq_name)

    try:
        message_preview = body.decode("utf-8")[:300] if body else "(empty)"
    except Exception:
        message_preview = "(binary data)"

    logger.warning(
        "DLQ: Received dead-lettered message — dlq='%s', original_queue='%s', "
        "retry_count=%d/%d, body=%s",
        dlq_name,
        original_queue,
        retry_count,
        MAX_RETRIES,
        message_preview,
    )

    if retry_count < MAX_RETRIES and original_queue:
        # Retry: republish to original queue with a TTL delay
        delay_ms = (2 ** retry_count) * 1000  # Exponential backoff: 1s, 2s, 4s
        logger.info(
            "DLQ: Retrying message — republishing to '%s' with %dms delay "
            "(attempt %d/%d)",
            original_queue,
            delay_ms,
            retry_count + 1,
            MAX_RETRIES,
        )

        # Create a temporary delay queue
        delay_queue = f"{original_queue}.delay.{delay_ms}"
        ch.queue_declare(
            queue=delay_queue,
            durable=True,
            arguments={
                "x-message-ttl": delay_ms,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": original_queue,
                "x-expires": delay_ms + 60000,  # Auto-delete after TTL + 60s
            },
        )

        # Update headers with retry count
        headers = dict(properties.headers) if properties.headers else {}
        headers["x-retry-count"] = retry_count + 1

        ch.basic_publish(
            exchange="",
            routing_key=delay_queue,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type=properties.content_type or "application/json",
                headers=headers,
            ),
        )
        logger.info(
            "DLQ: Message republished to delay queue '%s'", delay_queue
        )
    else:
        # Permanently failed
        logger.error(
            "DLQ: ❌ PERMANENTLY FAILED — message exceeded max retries (%d). "
            "Original queue='%s', body=%s",
            MAX_RETRIES,
            original_queue,
            message_preview,
        )
        # Could persist to a database or file for manual inspection
        try:
            failed_data = json.loads(body) if body else {}
            logger.error(
                "DLQ: Permanently failed message data: %s",
                json.dumps(failed_data, indent=2),
            )
        except Exception:
            pass

    # Always acknowledge from DLQ
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_dlq_consumer() -> None:
    """
    Start consuming from all DLQ queues in a daemon thread.
    Handles reconnection on failure.
    """

    def _run():
        while True:
            try:
                logger.info("DLQ Consumer: Connecting to RabbitMQ...")
                connection = get_rabbitmq_connection(max_retries=15, retry_delay=5.0)
                channel = connection.channel()
                channel.basic_qos(prefetch_count=1)

                # Consume from all DLQ queues
                for dlq in DLQ_QUEUES:
                    try:
                        channel.queue_declare(queue=dlq, durable=True, passive=True)
                    except Exception:
                        # Queue might not exist yet; that's OK, declare it
                        channel = connection.channel()
                        channel.queue_declare(queue=dlq, durable=True)

                    channel.basic_consume(
                        queue=dlq,
                        on_message_callback=handle_dlq_message,
                        auto_ack=False,
                    )
                    logger.info("DLQ Consumer: Listening on '%s'", dlq)

                logger.info("DLQ Consumer: ✅ All DLQ listeners active")
                channel.start_consuming()

            except Exception as e:
                logger.error(
                    "DLQ Consumer: Connection lost — %s. Reconnecting in 5s...",
                    str(e),
                )
                time.sleep(5)

    thread = threading.Thread(
        target=_run, daemon=True, name="dlq-consumer"
    )
    thread.start()
    logger.info("Started DLQ consumer thread")
