import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

FARMASI_DB_HOST = os.environ.get("FARMASI_DB_HOST", "mysql-farmasi")
FARMASI_DB_PORT = os.environ.get("FARMASI_DB_PORT", "3306")
FARMASI_DB_USER = os.environ.get("FARMASI_DB_USER", "farmasi_user")
FARMASI_DB_PASS = os.environ.get("FARMASI_DB_PASS", "farmasi_pass")
FARMASI_DB_NAME = os.environ.get("FARMASI_DB_NAME", "farmasi_db")

DATABASE_URL = (
    f"mysql+mysqlconnector://{FARMASI_DB_USER}:{FARMASI_DB_PASS}"
    f"@{FARMASI_DB_HOST}:{FARMASI_DB_PORT}/{FARMASI_DB_NAME}"
)

logger.info("Farmasi DB URL: %s", DATABASE_URL.replace(FARMASI_DB_PASS, "****"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a database session and ensure it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
