import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import router
from .consumer import start_consumer_thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start consumer on startup."""
    logger.info("Starting EMR service...")
    start_consumer_thread()
    logger.info("EMR service started successfully.")
    yield
    logger.info("Shutting down EMR service...")


app = FastAPI(
    title="Rekam Medis (EMR) Service",
    description="Electronic Medical Records microservice for managing patient medical records and prescriptions.",
    version="1.0.0",
    lifespan=lifespan,
)

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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve the EMR dashboard."""
    return FileResponse(str(STATIC_DIR / "index.html"))
