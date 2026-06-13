import os
import sys
import json
import time
import logging
from datetime import datetime

from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response

from app.database import engine, SessionLocal, Base
from app.models import Medicine, Dispensation
from app.seed import seed_medicines
from app.soap_service import create_soap_app

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("farmasi.main")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# ---------------------------------------------------------------------------
# Helper: wait for MySQL
# ---------------------------------------------------------------------------
def wait_for_mysql(max_retries: int = 30, delay: int = 2):
    """Block until MySQL is reachable, retrying up to *max_retries* times."""
    from sqlalchemy import text

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("MySQL is ready (attempt %d/%d).", attempt, max_retries)
            return
        except Exception as e:
            logger.warning(
                "MySQL not ready (attempt %d/%d): %s", attempt, max_retries, e
            )
            time.sleep(delay)

    logger.error("Could not connect to MySQL after %d attempts. Exiting.", max_retries)
    sys.exit(1)


# ---------------------------------------------------------------------------
# JSON API handlers
# ---------------------------------------------------------------------------
def _json_response(data, status: int = 200):
    body = json.dumps(data, ensure_ascii=False, default=str)
    return Response(body, status=status, content_type="application/json")


def handle_api_medicines():
    """GET /api/medicines — return medicine list as JSON."""
    db = SessionLocal()
    try:
        medicines = db.query(Medicine).all()
        return _json_response([m.to_dict() for m in medicines])
    except Exception as e:
        logger.error("API /api/medicines error: %s", e)
        return _json_response({"error": str(e)}, status=500)
    finally:
        db.close()


def handle_api_dispensations():
    """GET /api/dispensations — return dispensation list as JSON."""
    db = SessionLocal()
    try:
        dispensations = (
            db.query(Dispensation).order_by(Dispensation.created_at.desc()).all()
        )
        return _json_response([d.to_dict() for d in dispensations])
    except Exception as e:
        logger.error("API /api/dispensations error: %s", e)
        return _json_response({"error": str(e)}, status=500)
    finally:
        db.close()


def handle_api_health():
    """GET /api/health — simple health check."""
    db = SessionLocal()
    try:
        med_count = db.query(Medicine).count()
        disp_count = db.query(Dispensation).count()
        return _json_response(
            {
                "status": "healthy",
                "service": "farmasi",
                "protocol": "SOAP/XML",
                "timestamp": datetime.utcnow().isoformat(),
                "medicines_count": med_count,
                "dispensations_count": disp_count,
            }
        )
    except Exception as e:
        logger.error("Health check error: %s", e)
        return _json_response({"status": "unhealthy", "error": str(e)}, status=500)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------
def serve_static(path: str):
    """Serve a static file from STATIC_DIR."""
    file_path = os.path.join(STATIC_DIR, path)
    if not os.path.isfile(file_path):
        return Response("404 Not Found", status=404)

    with open(file_path, "rb") as f:
        content = f.read()

    # Determine content type
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }
    ct = content_types.get(ext, "application/octet-stream")
    return Response(content, status=200, content_type=ct)


# ---------------------------------------------------------------------------
# Main WSGI dispatcher
# ---------------------------------------------------------------------------
def create_app():
    """Build the combined WSGI application that routes SOAP, API and static."""
    soap_wsgi = create_soap_app()

    @Request.application
    def application(request: Request):
        path = request.path

        # ── SOAP endpoint ──────────────────────────────────────────────
        if path.startswith("/soap"):
            # Delegate to spyne WSGI app
            response = Response.from_app(soap_wsgi, request.environ)
            return response

        # ── JSON API endpoints ─────────────────────────────────────────
        if path == "/api/medicines":
            return handle_api_medicines()
        if path == "/api/dispensations":
            return handle_api_dispensations()
        if path == "/api/health":
            return handle_api_health()

        # ── Static / root ──────────────────────────────────────────────
        if path == "/" or path == "":
            return serve_static("index.html")
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            return serve_static(rel_path)

        # Fallback — try as static file
        return serve_static(path.lstrip("/"))

    return application


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 60)
    logger.info("  FARMASI SOAP/XML Microservice starting...")
    logger.info("=" * 60)

    # 1. Wait for MySQL
    wait_for_mysql()

    # 2. Create tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")

    # 3. Seed data
    seed_medicines()

    # 4. Build app & run
    app = create_app()

    logger.info("SOAP WSDL available at: http://0.0.0.0:8003/soap/?wsdl")
    logger.info("Dashboard available at:  http://0.0.0.0:8003/")
    logger.info("API medicines:           http://0.0.0.0:8003/api/medicines")
    logger.info("API dispensations:       http://0.0.0.0:8003/api/dispensations")
    logger.info("API health:              http://0.0.0.0:8003/api/health")
    logger.info("=" * 60)

    run_simple(
        hostname="0.0.0.0",
        port=8003,
        application=app,
        use_reloader=False,
        use_debugger=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
