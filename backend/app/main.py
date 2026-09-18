import logging
from pathlib import Path
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from app.auth import require_manager
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.routers import auth, inventory, reports
from app.seed import seed_if_empty
from app.services.sheets_sync import sync_mirror

logging.basicConfig(level=logging.INFO)
scheduler = BackgroundScheduler()

def scheduled_sync():
    with SessionLocal() as db: sync_mirror(db)

def ensure_schema_compatibility():
    """Ajoute les colonnes récentes aux bases existantes sans perdre de données."""
    columns = {column["name"] for column in inspect(engine).get_columns("ets_inventory_items")}
    if "serial_number" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE ets_inventory_items ADD COLUMN serial_number VARCHAR(120)"))

@asynccontextmanager
async def lifespan(_app):
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    if settings.seed_on_startup:
        with SessionLocal() as db: seed_if_empty(db)
    if settings.legacy_webapp_url.strip():
        scheduler.add_job(scheduled_sync, "interval", minutes=max(1, settings.sheet_sync_interval_minutes), id="sheet_sync", replace_existing=True)
        scheduler.start()
    yield
    if scheduler.running: scheduler.shutdown(wait=False)

app = FastAPI(title="API Stock Automobile — ETS Safouene Daoud et Cie", version="2.0.0", lifespan=lifespan)
settings = get_settings()
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
wildcard = origins == ["*"]
app.add_middleware(CORSMiddleware, allow_origins=["*"] if wildcard else origins,
                   allow_credentials=not wildcard, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(reports.router, prefix="/api")

@app.get("/health")
def health(): return {"ok": True}

@app.post("/api/sync/sheets")
def trigger_sync(_user: User = Depends(require_manager)):
    with SessionLocal() as db: return sync_mirror(db)


# The Railway free-plan deployment serves the kiosk and API from one container.
_static_dir = Path("/app/static")
if (_static_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
