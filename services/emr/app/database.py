import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = os.getenv("MONGODB_PORT", "27017")
MONGODB_USER = os.getenv("MONGODB_USER", "emr_user")
MONGODB_PASS = os.getenv("MONGODB_PASS", "emr_pass")
MONGODB_DB = os.getenv("MONGODB_DB", "emr_db")

MONGODB_URL = f"mongodb://{MONGODB_USER}:{MONGODB_PASS}@{MONGODB_HOST}:{MONGODB_PORT}"

logger.info(f"Connecting to MongoDB at {MONGODB_HOST}:{MONGODB_PORT}, database: {MONGODB_DB}")

client = AsyncIOMotorClient(MONGODB_URL)
database = client[MONGODB_DB]

medical_records_collection = database["medical_records"]
