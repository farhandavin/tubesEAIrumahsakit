import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import engine, Base
from app.routes import router
from app.consumer import start_consumer_thread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Billing & Asuransi Service")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)

# Mount static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    """Create database tables and start RabbitMQ consumer on startup."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Starting RabbitMQ consumer thread...")
    start_consumer_thread()
    logger.info("Billing & Asuransi Service started successfully.")


@app.get("/")
def serve_root():
    """Serve the main UI."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
