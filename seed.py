import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_secret
from app.models import AuthKind, InventoryItem, ItemCategory, User, UserRole


def _bootstrap_users():
    return [
        ("Admin", UserRole.management, os.getenv("ETS_ADMIN_PIN", "2026"), None),
        ("Storekeeper", UserRole.maintenance, os.getenv("ETS_STOREKEEPER_PIN", "1234"), None),
        ("Developer", UserRole.devs, os.getenv("ETS_DEVELOPER_PIN", "7346"), "devs-shared"),
    ]


DEMO_OPERATORS = []

SAMPLE_ITEMS = [
    ("KIA-OIL-FILTER", "KIA Oil Filter", ItemCategory.station_parts, 12, 4, "KIA-OIL-FILTER"),
    ("KIA-AIR-FILTER", "KIA Air Filter", ItemCategory.station_parts, 8, 3, "KIA-AIR-FILTER"),
    ("KIA-BRAKE-PAD", "KIA Brake Pad Set", ItemCategory.station_parts, 6, 2, "KIA-BRAKE-PAD"),
    ("TOOL-TORQUE-WRENCH", "Torque Wrench", ItemCategory.tools, 3, 1, "TOOL-TORQUE-WRENCH"),
    ("TOOL-OBD", "OBD Diagnostic Scanner", ItemCategory.tools, 2, 1, "TOOL-OBD"),
]


def seed_if_empty(db: Session) -> None:
    existing = db.execute(select(User).limit(1)).scalar_one_or_none()
    if existing:
        return

    for name, role, pin, group in _bootstrap_users():
        db.add(User(name=name, role=role, auth_kind=AuthKind.pin, pin_hash=hash_secret(pin), shared_pin_group=group))

    for op_id, password, role in DEMO_OPERATORS:
        db.add(User(name=f"Operator-{op_id}", role=role, auth_kind=AuthKind.operator, operator_id=op_id, password_hash=hash_secret(password)))

    for sku, name, category, qty, reorder_min, barcode in SAMPLE_ITEMS:
        db.add(InventoryItem(sku=sku, name=name, category=category, qty_on_hand=qty, reorder_min=reorder_min, barcode=barcode))
    db.commit()
