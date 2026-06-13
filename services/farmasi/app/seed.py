import logging
from app.database import SessionLocal
from app.models import Medicine

logger = logging.getLogger(__name__)

INITIAL_MEDICINES = [
    {"nama_obat": "Paracetamol 500mg", "stok": 500, "harga": 5000, "satuan": "tablet"},
    {"nama_obat": "Amoxicillin 500mg", "stok": 300, "harga": 8000, "satuan": "kapsul"},
    {"nama_obat": "Omeprazole 20mg", "stok": 200, "harga": 12000, "satuan": "kapsul"},
    {"nama_obat": "Metformin 500mg", "stok": 400, "harga": 6000, "satuan": "tablet"},
    {"nama_obat": "Amlodipine 5mg", "stok": 250, "harga": 10000, "satuan": "tablet"},
    {"nama_obat": "Ibuprofen 400mg", "stok": 350, "harga": 7000, "satuan": "tablet"},
    {"nama_obat": "Cetirizine 10mg", "stok": 200, "harga": 5500, "satuan": "tablet"},
    {"nama_obat": "Infus NaCl 0.9%", "stok": 100, "harga": 35000, "satuan": "botol"},
    {"nama_obat": "Ranitidine 150mg", "stok": 300, "harga": 4500, "satuan": "tablet"},
    {"nama_obat": "Dexamethasone 0.5mg", "stok": 150, "harga": 9000, "satuan": "tablet"},
]


def seed_medicines():
    """Seed the database with initial medicine data if no medicines exist."""
    db = SessionLocal()
    try:
        count = db.query(Medicine).count()
        if count > 0:
            logger.info("Medicines already seeded (%d records). Skipping.", count)
            return

        logger.info("Seeding %d medicines into database...", len(INITIAL_MEDICINES))
        for med_data in INITIAL_MEDICINES:
            medicine = Medicine(**med_data)
            db.add(medicine)

        db.commit()
        logger.info("Successfully seeded %d medicines.", len(INITIAL_MEDICINES))
    except Exception as e:
        db.rollback()
        logger.error("Failed to seed medicines: %s", e)
        raise
    finally:
        db.close()
