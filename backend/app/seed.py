import logging, os
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import hash_secret
from app.models import AuthKind, InventoryItem, ItemCategory, User, UserRole

log = logging.getLogger(__name__)
USERS = (("Admin", UserRole.management, "ETS_ADMIN_PIN", None),
         ("Storekeeper", UserRole.maintenance, "ETS_STOREKEEPER_PIN", None),
         ("Developer", UserRole.devs, "ETS_DEVELOPER_PIN", "devs-shared"))
ITEMS = [("KIA-OIL-FILTER","KIA Oil Filter",ItemCategory.station_parts,12,4),
         ("KIA-AIR-FILTER","KIA Air Filter",ItemCategory.station_parts,8,3),
         ("TOOL-TORQUE-WRENCH","Torque Wrench",ItemCategory.tools,3,1)]

def seed_if_empty(db: Session):
    if not db.execute(select(User).limit(1)).scalar_one_or_none():
        for name, role, env, group in USERS:
            secret = os.getenv(env, "").strip()
            if secret and secret != "replace-me":
                db.add(User(name=name, role=role, auth_kind=AuthKind.pin, pin_hash=hash_secret(secret), shared_pin_group=group))
            else:
                log.warning("Skipping %s: %s is not configured", name, env)
    if not db.execute(select(InventoryItem).limit(1)).scalar_one_or_none():
        for sku, name, category, qty, minimum in ITEMS:
            db.add(InventoryItem(sku=sku, name=name, category=category, qty_on_hand=qty, reorder_min=minimum, barcode=sku))
    db.commit()
