import logging, os
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import hash_secret
from app.models import AuthKind, InventoryItem, ItemCategory, User, UserRole

log = logging.getLogger(__name__)
USERS = (("Management", UserRole.management, "ETS_ADMIN_PIN", "Admin"),
         ("Majdi", UserRole.maintenance, "ETS_STOREKEEPER_PIN", "Storekeeper"))
ITEMS = [("KIA-OIL-FILTER","KIA Oil Filter",ItemCategory.station_parts,12,4),
         ("KIA-AIR-FILTER","KIA Air Filter",ItemCategory.station_parts,8,3),
         ("TOOL-TORQUE-WRENCH","Torque Wrench",ItemCategory.tools,3,1)]

def seed_if_empty(db: Session):
    existing_users = db.execute(select(User)).scalars().all()
    for user in existing_users:
        user.is_active = False
    for name, role, env, legacy_name in USERS:
        secret = os.getenv(env, "").strip()
        if not secret or secret == "replace-me":
            log.warning("Skipping %s: %s is not configured", name, env)
            continue
        user = next((u for u in existing_users if u.name == name), None)
        if user is None:
            user = next((u for u in existing_users if u.name == legacy_name), None)
        if user is None:
            user = User(name=name, role=role, auth_kind=AuthKind.pin)
            db.add(user)
            existing_users.append(user)
        user.name = name
        user.role = role
        user.auth_kind = AuthKind.pin
        user.pin_hash = hash_secret(secret)
        user.operator_id = None
        user.password_hash = None
        user.shared_pin_group = None
        user.is_active = True
    if not db.execute(select(InventoryItem).limit(1)).scalar_one_or_none():
        for sku, name, category, qty, minimum in ITEMS:
            db.add(InventoryItem(sku=sku, name=name, category=category, qty_on_hand=qty, reorder_min=minimum, barcode=sku))
    db.commit()
