import os
import json
import time
import logging
import pika

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

EXCHANGE_NAME = "prescription.events"
ROUTING_KEY = "prescription.created"


def publish_prescription_created(prescription_data: dict) -> None:
    """Publish a prescription.created event to RabbitMQ with retry logic."""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection_params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="direct",
                durable=True,
            )

            message_body = json.dumps(prescription_data, default=str)

            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=ROUTING_KEY,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type="application/json",
                ),
            )

            logger.info(
                f"Published prescription.created event for prescription_id={prescription_data.get('prescription_id')}"
            )
            connection.close()
            return

        except Exception as e:
            logger.error(
                f"Failed to publish message (attempt {attempt}/{max_retries}): {e}"
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                logger.error("All retry attempts exhausted. Message not published.")
                raise
