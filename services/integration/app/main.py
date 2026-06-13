"""
Integration Service — Hospital EAI Hub
Central integration layer that connects all hospital systems.
Implements: Message Channel, Pub/Sub, Content-Based Router,
Message Translator, Canonical Data Model, Dead Letter Queue.
"""

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.routes import router
from app.consumers import start_consumers
from app.dlq_handler import start_dlq_consumer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("integration.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start RabbitMQ consumers on startup."""
    logger.info("=" * 60)
    logger.info("  INTEGRATION SERVICE — Hospital EAI Hub")
    logger.info("  Starting up...")
    logger.info("=" * 60)

    # Wait a bit for other services to be ready
    time.sleep(5)

    # Start main consumers in background thread
    consumer_thread = threading.Thread(
        target=start_consumers,
        daemon=True,
        name="integration-consumers"
    )
    consumer_thread.start()
    logger.info("✅ Main consumers started")

    # Start DLQ consumer in background thread
    dlq_thread = threading.Thread(
        target=start_dlq_consumer,
        daemon=True,
        name="dlq-consumer"
    )
    dlq_thread.start()
    logger.info("✅ DLQ consumer started")

    logger.info("🔗 Integration Service is READY")
    logger.info("=" * 60)

    yield

    logger.info("Integration Service shutting down...")


app = FastAPI(
    title="Integration Service — Hospital EAI Hub",
    description="Central integration layer implementing Enterprise Integration Patterns",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Mount static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the integration dashboard."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"service": "Integration Hub", "status": "running"}
