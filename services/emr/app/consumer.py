import os
import json
import time
import logging
import threading
from datetime import datetime, timezone

import pika
from pymongo import MongoClient

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = os.getenv("MONGODB_PORT", "27017")
MONGODB_USER = os.getenv("MONGODB_USER", "emr_user")
MONGODB_PASS = os.getenv("MONGODB_PASS", "emr_pass")
MONGODB_DB = os.getenv("MONGODB_DB", "emr_db")

QUEUE_NAME = "patient.registration.emr"
EXCHANGE_NAME = "patient.events"
ROUTING_KEY = "patient.registered"


def get_sync_mongo_collection():
    """Create a synchronous PyMongo client and return the medical_records collection."""
    mongo_url = f"mongodb://{MONGODB_USER}:{MONGODB_PASS}@{MONGODB_HOST}:{MONGODB_PORT}"
    client = MongoClient(mongo_url)
    db = client[MONGODB_DB]
    return db["medical_records"]


def on_message_callback(ch, method, properties, body):
    """Handle incoming patient registration messages."""
    try:
        message = json.loads(body)
        logger.info(f"Received patient registration event: {message}")
        # Handle both publisher format (nested data) and Integration Service format (flat)
        patient_data = message.get("data", message)
        patient_id = patient_data.get("patient_id", patient_data.get("id"))
        patient_name = patient_data.get("patient_name", patient_data.get("nama", "Unknown"))

        now = datetime.now(timezone.utc).isoformat()

        collection = get_sync_mongo_collection()

        # Atomic upsert to prevent race conditions causing duplicate records
        collection.update_one(
            {"patient_id": patient_id},
            {
                "$setOnInsert": {
                    "patient_name": patient_name,
                    "diagnoses": [],
                    "prescriptions": [],
                    "created_at": now,
                },
                "$push": {
                    "visits": {"date": now, "type": "REGISTRATION"}
                }
            },
            upsert=True
        )
        logger.info(f"Upserted medical record for patient_id={patient_id}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consuming():
    """Connect to RabbitMQ and start consuming messages. Retries on failure."""
    while True:
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

            # Declare exchange and queue, bind them
            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="fanout",
                durable=True,
            )
            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "dlx.exchange",
                    "x-dead-letter-routing-key": f"{QUEUE_NAME}.dlq",
                }
            )
            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=QUEUE_NAME,
                routing_key=ROUTING_KEY,
            )

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=on_message_callback,
                auto_ack=False,
            )

            logger.info(f"EMR consumer started. Listening on queue: {QUEUE_NAME}")
            channel.start_consuming()

        except Exception as e:
            logger.error(f"Consumer connection error: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)


def start_consumer_thread():
    """Start the RabbitMQ consumer in a daemon thread."""
    consumer_thread = threading.Thread(target=start_consuming, daemon=True)
    consumer_thread.start()
    logger.info("EMR consumer thread started.")
