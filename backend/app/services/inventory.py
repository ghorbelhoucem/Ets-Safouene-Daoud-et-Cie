import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Checkout, IdempotencyKey, InventoryItem, ItemCategory, Movement, MovementType, WarrantyReport

def available_qty(db: Session, item: InventoryItem) -> int:
    if item.category == ItemCategory.station_parts:
        return item.qty_on_hand
    rows = db.execute(select(Checkout).where(Checkout.item_id == item.id, Checkout.returned_at.is_(None))).scalars().all()
    return max(0, item.qty_on_hand - sum(row.qty for row in rows))

def availability_label(db: Session, item: InventoryItem) -> str:
    available = available_qty(db, item)
    if available <= 0: return "X"
    if available == item.qty_on_hand: return "✓"
    return f"{item.qty_on_hand - available} part(s) missing"

def snapshot(db: Session) -> dict:
    items = db.execute(select(InventoryItem).order_by(InventoryItem.name)).scalars().all()
    checkouts = db.execute(select(Checkout).order_by(Checkout.taken_at.desc())).scalars().all()
    warranties = db.execute(select(WarrantyReport).order_by(WarrantyReport.created_at.desc())).scalars().all()
    inventory = [{"reference": x.category.value, "item": x.name, "quantity": x.qty_on_hand,
                  "availability": availability_label(db, x), "barcode": x.barcode,
                  "reorder_min": x.reorder_min, "sop_status": x.sop_status} for x in items]
    history = []
    for row in checkouts:
        item = db.get(InventoryItem, row.item_id)
        history.append({"timestamp": row.taken_at.isoformat() if row.taken_at else "",
            "personRole": row.person_role, "item": item.name if item else "",
            "expectedReturn": row.expected_return.isoformat() if row.expected_return else "None",
            "returnedAt": row.returned_at.isoformat() if row.returned_at else ("N/A" if item and item.category == ItemCategory.station_parts else "Not returned"),
            "returnedBy": row.returned_by, "txId": row.tx_id, "qty": row.qty})
    warranty = [{"timestamp": x.created_at.isoformat() if x.created_at else "", "reportedBy": x.reported_by,
                 "partName": x.part_name, "serialNumber": x.serial_number, "issue": x.issue} for x in warranties]
    return {"ok": True, "inventory": inventory, "history": history, "warranty": warranty}

def get_idempotent(db: Session, request_id: str):
    row = db.execute(select(IdempotencyKey).where(IdempotencyKey.client_request_id == request_id)).scalar_one_or_none()
    return row.response_json if row else None

def save_idempotent(db: Session, request_id: str, action: str, response: dict):
    db.add(IdempotencyKey(client_request_id=request_id, action=action, response_json=response))

def take_batch(db: Session, person: str, role: str, items: list[dict]) -> dict:
    prepared = []
    for entry in items:
        item = db.execute(select(InventoryItem).where(InventoryItem.name == entry["item"])).scalar_one_or_none()
        qty = int(entry.get("qty", 1))
        if not item or qty < 1: return {"ok": False, "error": "Invalid item.", "code": "BAD_ITEM"}
        available = available_qty(db, item)
        if available < qty: return {"ok": False, "error": f"Not enough {item.name} available.", "code": "OUT_OF_STOCK", "available": available}
        prepared.append((item, qty, entry.get("expectedReturn")))
    ids = []
    for item, qty, expected in prepared:
        tx = uuid.uuid4().hex
        due = None
        if expected:
            try: due = datetime.fromisoformat(expected.replace("Z", "+00:00"))
            except ValueError: pass
        checkout = Checkout(tx_id=tx, item_id=item.id, person_role=f"{person}/{role}", qty=qty, expected_return=due)
        if item.category == ItemCategory.station_parts:
            item.qty_on_hand -= qty
            checkout.returned_at = datetime.now(timezone.utc)
        db.add(checkout)
        db.add(Movement(movement_type=MovementType.take, item_id=item.id, item_name=item.name, qty=-qty, actor=f"{person}/{role}", related_tx_id=tx))
        ids.append(tx)
    return {"ok": True, "txIds": ids}

def return_batch(db: Session, tx_ids: list[str], returned_by: str) -> dict:
    rows = db.execute(select(Checkout).where(Checkout.tx_id.in_(tx_ids))).scalars().all()
    found = {x.tx_id: x for x in rows}
    if any(x not in found for x in tx_ids): return {"ok": False, "error": "Transaction not found.", "code": "NOT_FOUND"}
    for tx in tx_ids:
        row = found[tx]
        if row.returned_at: continue
        row.returned_at, row.returned_by = datetime.now(timezone.utc), returned_by
        item = db.get(InventoryItem, row.item_id)
        db.add(Movement(movement_type=MovementType.return_, item_id=row.item_id, item_name=item.name if item else "", qty=row.qty, actor=returned_by, related_tx_id=tx))
    return {"ok": True, "returned": len(tx_ids)}

def receive_stock(db: Session, name: str, qty: int, actor: str, reason: str | None, category: str | None = None, sop_status: str | None = None) -> dict:
    item = db.execute(select(InventoryItem).where(InventoryItem.name == name)).scalar_one_or_none()
    if item is None:
        if not category: return {"ok": False, "error": "Category required.", "code": "CATEGORY_REQUIRED"}
        try: kind = ItemCategory(category)
        except ValueError: return {"ok": False, "error": "Invalid category.", "code": "BAD_CATEGORY"}
        item = InventoryItem(sku=f"ITEM-{uuid.uuid4().hex[:10].upper()}", name=name, category=kind, qty_on_hand=0)
        db.add(item); db.flush()
    item.qty_on_hand += qty
    if sop_status is not None: item.sop_status = sop_status
    db.add(Movement(movement_type=MovementType.receive, item_id=item.id, item_name=item.name, qty=qty, actor=actor, reason=reason))
    return {"ok": True, "quantity": item.qty_on_hand}

def adjust_stock(db: Session, name: str, delta: int, actor: str, reason: str) -> dict:
    item = db.execute(select(InventoryItem).where(InventoryItem.name == name)).scalar_one_or_none()
    if not item: return {"ok": False, "error": "Item not found.", "code": "NOT_FOUND"}
    if item.qty_on_hand + delta < 0: return {"ok": False, "error": "Stock cannot be negative.", "code": "NEGATIVE_STOCK"}
    item.qty_on_hand += delta
    db.add(Movement(movement_type=MovementType.adjust, item_id=item.id, item_name=item.name, qty=delta, actor=actor, reason=reason))
    return {"ok": True, "quantity": item.qty_on_hand}
