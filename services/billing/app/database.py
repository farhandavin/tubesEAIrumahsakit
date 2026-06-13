import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

DB_HOST = os.getenv("BILLING_DB_HOST", "postgres-billing")
DB_PORT = os.getenv("BILLING_DB_PORT", "5432")
DB_USER = os.getenv("BILLING_DB_USER", "billing_user")
DB_PASS = os.getenv("BILLING_DB_PASS", "billing_pass")
DB_NAME = os.getenv("BILLING_DB_NAME", "billing_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
