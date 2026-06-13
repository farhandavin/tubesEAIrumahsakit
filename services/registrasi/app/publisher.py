import os
import json
import logging
import time
import pika

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

EXCHANGE_NAME = "patient.events"
MAX_RETRIES = 3


def publish_patient_registered(patient_data: dict) -> bool:
    """
    Publish a patient.registered event to the patient.events fanout exchange.
    Retries up to MAX_RETRIES times on connection failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            # Declare fanout exchange
            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="fanout",
                durable=True,
            )

            message = {
                "event_type": "patient.registered",
                "data": patient_data,
            }

            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key="",
                body=json.dumps(message, default=str),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type="application/json",
                ),
            )

            connection.close()
            logger.info(
                "Published patient.registered event for patient_id=%s",
                patient_data.get("id"),
            )
            return True

        except Exception as exc:
            logger.error(
                "RabbitMQ publish attempt %d/%d failed: %s",
                attempt,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    logger.error(
        "Failed to publish patient.registered event after %d attempts", MAX_RETRIES
    )
    return False
