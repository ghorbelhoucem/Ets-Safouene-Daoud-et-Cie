import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_manager, require_report_access
from app.database import get_db
from app.garage_schemas import (
    CustomerCreate,
    InvoiceCreate,
    MechanicCreate,
    PaymentCreate,
    PurchaseOrderCreate,
    PurchaseReceive,
    RepairLineCreate,
    RepairOrderCreate,
    RepairOrderUpdate,
    SupplierCreate,
    VehicleCreate,
)
from app.models import (
    Customer,
    Invoice,
    InventoryItem,
    ItemCategory,
    Mechanic,
    Movement,
    MovementType,
    Payment,
    PurchaseOrder,
    PurchaseOrderLine,
    RepairOrder,
    RepairOrderLine,
    Supplier,
    User,
    Vehicle,
)

router = APIRouter(prefix="/garage", tags=["garage-plus"])


def _money(value) -> float:
    return round(float(value or 0), 3)


def _now_iso(value) -> str | None:
    return value.isoformat() if value else None


def _number(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _commit_or_conflict(db: Session, message: str):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, message) from exc


def _customer(row: Customer) -> dict:
    return {
        "id": str(row.id), "customer_code": row.customer_code, "name": row.name,
        "phone": row.phone, "email": row.email, "address": row.address,
        "tax_id": row.tax_id, "notes": row.notes, "created_at": _now_iso(row.created_at),
    }


def _vehicle(row: Vehicle, customer_name: str | None = None) -> dict:
    return {
        "id": str(row.id), "customer_id": str(row.customer_id), "customer_name": customer_name,
        "registration": row.registration, "vin": row.vin, "make": row.make,
        "model": row.model, "year": row.year, "mileage": row.mileage,
        "color": row.color, "notes": row.notes, "created_at": _now_iso(row.created_at),
    }


def _mechanic(row: Mechanic) -> dict:
    return {
        "id": str(row.id), "name": row.name, "specialty": row.specialty,
        "phone": row.phone, "hourly_rate": _money(row.hourly_rate),
        "is_active": row.is_active,
    }


def _order_payload(db: Session, row: RepairOrder, include_lines: bool = True) -> dict:
    customer = db.get(Customer, row.customer_id)
    vehicle = db.get(Vehicle, row.vehicle_id)
    mechanic = db.get(Mechanic, row.mechanic_id) if row.mechanic_id else None
    lines = db.execute(
        select(RepairOrderLine)
        .where(RepairOrderLine.repair_order_id == row.id)
        .order_by(RepairOrderLine.created_at)
    ).scalars().all()
    all_line_rows = [
        {
            "id": str(line.id), "line_type": line.line_type, "description": line.description,
            "inventory_item_id": str(line.inventory_item_id) if line.inventory_item_id else None,
            "quantity": _money(line.quantity), "unit_price": _money(line.unit_price),
            "unit_cost": _money(line.unit_cost),
            "total": _money(Decimal(str(line.quantity)) * Decimal(str(line.unit_price))),
        }
        for line in lines
    ]
    total = sum(line["total"] for line in all_line_rows)
    line_rows = all_line_rows if include_lines else []
    return {
        "id": str(row.id), "order_number": row.order_number,
        "customer_id": str(row.customer_id), "customer_name": customer.name if customer else "",
        "vehicle_id": str(row.vehicle_id),
        "vehicle": f"{vehicle.make} {vehicle.model} · {vehicle.registration}" if vehicle else "",
        "mechanic_id": str(row.mechanic_id) if row.mechanic_id else None,
        "mechanic_name": mechanic.name if mechanic else None,
        "status": row.status, "priority": row.priority, "complaint": row.complaint,
        "diagnosis": row.diagnosis, "internal_notes": row.internal_notes,
        "mileage_in": row.mileage_in, "scheduled_for": _now_iso(row.scheduled_for),
        "opened_at": _now_iso(row.opened_at), "closed_at": _now_iso(row.closed_at),
        "lines": line_rows, "total": round(total, 3),
    }


def _invoice_payload(db: Session, row: Invoice) -> dict:
    order = db.get(RepairOrder, row.repair_order_id)
    customer = db.get(Customer, order.customer_id) if order else None
    balance = max(0, _money(row.total) - _money(row.paid_amount))
    return {
        "id": str(row.id), "invoice_number": row.invoice_number,
        "repair_order_id": str(row.repair_order_id),
        "order_number": order.order_number if order else "",
        "customer_name": customer.name if customer else "",
        "status": row.status, "subtotal": _money(row.subtotal),
        "tax_rate": _money(row.tax_rate), "tax_amount": _money(row.tax_amount),
        "discount": _money(row.discount), "total": _money(row.total),
        "paid_amount": _money(row.paid_amount), "balance": balance,
        "issued_at": _now_iso(row.issued_at), "due_at": _now_iso(row.due_at),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    open_statuses = ["Ouvert", "Diagnostic", "En attente pièces", "En réparation", "Prêt"]
    open_orders = db.scalar(select(func.count()).select_from(RepairOrder).where(RepairOrder.status.in_(open_statuses))) or 0
    ready = db.scalar(select(func.count()).select_from(RepairOrder).where(RepairOrder.status == "Prêt")) or 0
    customer_count = db.scalar(select(func.count()).select_from(Customer)) or 0
    vehicle_count = db.scalar(select(func.count()).select_from(Vehicle)) or 0
    invoice_total = db.scalar(select(func.coalesce(func.sum(Invoice.total), 0))) or 0
    paid_total = db.scalar(select(func.coalesce(func.sum(Invoice.paid_amount), 0))) or 0
    low_stock = db.scalar(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.category != ItemCategory.sops,
            InventoryItem.qty_on_hand <= InventoryItem.reorder_min,
        )
    ) or 0
    recent = db.execute(select(RepairOrder).order_by(RepairOrder.opened_at.desc()).limit(8)).scalars().all()
    status_rows = db.execute(
        select(RepairOrder.status, func.count()).group_by(RepairOrder.status).order_by(RepairOrder.status)
    ).all()
    return {
        "ok": True,
        "kpis": {
            "open_orders": open_orders, "ready_orders": ready,
            "customers": customer_count, "vehicles": vehicle_count,
            "revenue": _money(invoice_total), "outstanding": _money(invoice_total - paid_total),
            "low_stock": low_stock,
        },
        "orders_by_status": [{"status": status, "count": count} for status, count in status_rows],
        "recent_orders": [_order_payload(db, row, include_lines=False) for row in recent],
    }


@router.get("/customers")
def list_customers(q: str = "", db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    stmt = select(Customer).order_by(Customer.created_at.desc())
    if q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(needle), Customer.phone.ilike(needle), Customer.customer_code.ilike(needle)))
    return {"ok": True, "customers": [_customer(row) for row in db.execute(stmt).scalars().all()]}


@router.post("/customers")
def create_customer(body: CustomerCreate, db: Session = Depends(get_db), user: User = Depends(require_report_access)):
    row = Customer(customer_code=_number("CLI"), **body.model_dump())
    db.add(row)
    _commit_or_conflict(db, "Ce client existe déjà.")
    db.refresh(row)
    return {"ok": True, "customer": _customer(row), "created_by": user.name}


@router.get("/vehicles")
def list_vehicles(q: str = "", db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    stmt = select(Vehicle).order_by(Vehicle.created_at.desc())
    if q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Vehicle.registration.ilike(needle), Vehicle.vin.ilike(needle), Vehicle.model.ilike(needle)))
    rows = db.execute(stmt).scalars().all()
    payload = []
    for row in rows:
        customer = db.get(Customer, row.customer_id)
        payload.append(_vehicle(row, customer.name if customer else ""))
    return {"ok": True, "vehicles": payload}


@router.post("/vehicles")
def create_vehicle(body: VehicleCreate, db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    if not db.get(Customer, body.customer_id):
        raise HTTPException(404, "Client introuvable")
    row = Vehicle(**body.model_dump())
    db.add(row)
    _commit_or_conflict(db, "Cette immatriculation ou ce VIN existe déjà.")
    db.refresh(row)
    customer = db.get(Customer, row.customer_id)
    return {"ok": True, "vehicle": _vehicle(row, customer.name if customer else "")}


@router.get("/mechanics")
def list_mechanics(db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    rows = db.execute(select(Mechanic).order_by(Mechanic.name)).scalars().all()
    return {"ok": True, "mechanics": [_mechanic(row) for row in rows]}


@router.post("/mechanics")
def create_mechanic(body: MechanicCreate, db: Session = Depends(get_db), _user: User = Depends(require_manager)):
    row = Mechanic(**body.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return {"ok": True, "mechanic": _mechanic(row)}


@router.get("/orders")
def list_orders(status: str = "", q: str = "", db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    stmt = select(RepairOrder).order_by(RepairOrder.opened_at.desc())
    if status.strip(): stmt = stmt.where(RepairOrder.status == status.strip())
    rows = db.execute(stmt).scalars().all()
    payload = [_order_payload(db, row) for row in rows]
    if q.strip():
        needle = q.strip().lower()
        payload = [row for row in payload if needle in " ".join([
            row["order_number"], row["customer_name"], row["vehicle"], row["complaint"]
        ]).lower()]
    return {"ok": True, "orders": payload}


@router.post("/orders")
def create_order(body: RepairOrderCreate, db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    customer = db.get(Customer, body.customer_id)
    vehicle = db.get(Vehicle, body.vehicle_id)
    if not customer or not vehicle or vehicle.customer_id != customer.id:
        raise HTTPException(400, "Le client et le véhicule ne correspondent pas.")
    if body.mechanic_id and not db.get(Mechanic, body.mechanic_id):
        raise HTTPException(404, "Mécanicien introuvable")
    row = RepairOrder(order_number=_number("OR"), **body.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return {"ok": True, "order": _order_payload(db, row)}


@router.patch("/orders/{order_id}")
def update_order(order_id: uuid.UUID, body: RepairOrderUpdate, db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    row = db.get(RepairOrder, order_id)
    if not row: raise HTTPException(404, "Ordre de réparation introuvable")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    if body.status in {"Livré", "Annulé"}: row.closed_at = datetime.now(timezone.utc)
    elif body.status: row.closed_at = None
    db.commit(); db.refresh(row)
    return {"ok": True, "order": _order_payload(db, row)}


@router.post("/orders/{order_id}/lines")
def add_order_line(order_id: uuid.UUID, body: RepairLineCreate, db: Session = Depends(get_db), user: User = Depends(require_report_access)):
    order = db.get(RepairOrder, order_id)
    if not order: raise HTTPException(404, "Ordre de réparation introuvable")
    item = None
    if body.inventory_item_id:
        item = db.get(InventoryItem, body.inventory_item_id)
        if not item or item.category != ItemCategory.station_parts:
            raise HTTPException(400, "La pièce de stock sélectionnée est invalide.")
        quantity = int(body.quantity)
        if quantity != body.quantity or item.qty_on_hand < quantity:
            raise HTTPException(409, f"Stock insuffisant pour {item.name}.")
        item.qty_on_hand -= quantity
        db.add(Movement(
            movement_type=MovementType.take, item_id=item.id, item_name=item.name,
            qty=-quantity, actor=f"{user.name}/{user.role.value}",
            reason=f"Ordre de réparation {order.order_number}", related_tx_id=order.order_number,
        ))
    line = RepairOrderLine(repair_order_id=order.id, **body.model_dump())
    db.add(line); db.commit(); db.refresh(order)
    return {"ok": True, "order": _order_payload(db, order)}


@router.get("/invoices")
def list_invoices(db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    rows = db.execute(select(Invoice).order_by(Invoice.issued_at.desc())).scalars().all()
    return {"ok": True, "invoices": [_invoice_payload(db, row) for row in rows]}


@router.post("/invoices")
def create_invoice(body: InvoiceCreate, db: Session = Depends(get_db), _user: User = Depends(require_manager)):
    order = db.get(RepairOrder, body.repair_order_id)
    if not order: raise HTTPException(404, "Ordre de réparation introuvable")
    existing = db.execute(select(Invoice).where(Invoice.repair_order_id == order.id)).scalar_one_or_none()
    if existing: raise HTTPException(409, "Une facture existe déjà pour cet ordre.")
    lines = db.execute(select(RepairOrderLine).where(RepairOrderLine.repair_order_id == order.id)).scalars().all()
    if not lines: raise HTTPException(400, "Ajoutez au moins une ligne avant de facturer.")
    subtotal = sum(Decimal(str(line.quantity)) * Decimal(str(line.unit_price)) for line in lines)
    discount = Decimal(str(body.discount))
    taxable = max(Decimal("0"), subtotal - discount)
    tax_amount = taxable * Decimal(str(body.tax_rate)) / Decimal("100")
    total = taxable + tax_amount
    row = Invoice(
        invoice_number=_number("FAC"), repair_order_id=order.id,
        subtotal=subtotal, tax_rate=body.tax_rate, tax_amount=tax_amount,
        discount=discount, total=total, due_at=body.due_at,
    )
    db.add(row); db.commit(); db.refresh(row)
    return {"ok": True, "invoice": _invoice_payload(db, row)}


@router.post("/invoices/{invoice_id}/payments")
def add_payment(invoice_id: uuid.UUID, body: PaymentCreate, db: Session = Depends(get_db), user: User = Depends(require_manager)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice: raise HTTPException(404, "Facture introuvable")
    balance = Decimal(str(invoice.total)) - Decimal(str(invoice.paid_amount))
    if Decimal(str(body.amount)) > balance:
        raise HTTPException(400, "Le règlement dépasse le solde de la facture.")
    payment = Payment(
        invoice_id=invoice.id, amount=body.amount, method=body.method,
        reference=body.reference, received_by=f"{user.name}/{user.role.value}",
    )
    invoice.paid_amount = Decimal(str(invoice.paid_amount)) + Decimal(str(body.amount))
    invoice.status = "Payée" if invoice.paid_amount >= invoice.total else "Partielle"
    db.add(payment); db.commit(); db.refresh(invoice)
    return {"ok": True, "invoice": _invoice_payload(db, invoice)}


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    rows = db.execute(select(Supplier).order_by(Supplier.name)).scalars().all()
    return {"ok": True, "suppliers": [{
        "id": str(row.id), "supplier_code": row.supplier_code, "name": row.name,
        "contact_name": row.contact_name, "phone": row.phone, "email": row.email,
        "address": row.address, "tax_id": row.tax_id,
    } for row in rows]}


@router.post("/suppliers")
def create_supplier(body: SupplierCreate, db: Session = Depends(get_db), _user: User = Depends(require_manager)):
    row = Supplier(supplier_code=_number("FOU"), **body.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return {"ok": True, "supplier": {"id": str(row.id), "supplier_code": row.supplier_code, "name": row.name}}


@router.get("/purchases")
def list_purchases(db: Session = Depends(get_db), _user: User = Depends(require_report_access)):
    rows = db.execute(select(PurchaseOrder).order_by(PurchaseOrder.ordered_at.desc())).scalars().all()
    payload = []
    for row in rows:
        supplier = db.get(Supplier, row.supplier_id)
        lines = db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == row.id)).scalars().all()
        payload.append({
            "id": str(row.id), "purchase_number": row.purchase_number,
            "supplier_name": supplier.name if supplier else "", "status": row.status,
            "total": _money(row.total), "ordered_at": _now_iso(row.ordered_at),
            "expected_at": _now_iso(row.expected_at), "received_at": _now_iso(row.received_at),
            "notes": row.notes,
            "lines": [{
                "id": str(line.id), "inventory_item_id": str(line.inventory_item_id) if line.inventory_item_id else None,
                "description": line.description, "quantity": line.quantity,
                "received_quantity": line.received_quantity, "unit_cost": _money(line.unit_cost),
            } for line in lines],
        })
    return {"ok": True, "purchases": payload}


@router.post("/purchases")
def create_purchase(body: PurchaseOrderCreate, db: Session = Depends(get_db), _user: User = Depends(require_manager)):
    if not db.get(Supplier, body.supplier_id): raise HTTPException(404, "Fournisseur introuvable")
    total = sum(Decimal(str(line.quantity)) * Decimal(str(line.unit_cost)) for line in body.lines)
    row = PurchaseOrder(
        purchase_number=_number("ACH"), supplier_id=body.supplier_id,
        expected_at=body.expected_at, notes=body.notes, total=total, status="Commandée",
    )
    db.add(row); db.flush()
    for line in body.lines:
        if line.inventory_item_id and not db.get(InventoryItem, line.inventory_item_id):
            db.rollback(); raise HTTPException(404, "Article de stock introuvable")
        db.add(PurchaseOrderLine(purchase_order_id=row.id, **line.model_dump()))
    db.commit(); db.refresh(row)
    return {"ok": True, "purchase_id": str(row.id), "purchase_number": row.purchase_number}


@router.post("/purchases/{purchase_id}/receive")
def receive_purchase(purchase_id: uuid.UUID, body: PurchaseReceive, db: Session = Depends(get_db), user: User = Depends(require_manager)):
    row = db.get(PurchaseOrder, purchase_id)
    if not row: raise HTTPException(404, "Commande fournisseur introuvable")
    if row.status == "Reçue": raise HTTPException(409, "Cette commande a déjà été réceptionnée.")
    lines = db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == row.id)).scalars().all()
    requested = body.received_quantities or {}
    for line in lines:
        remaining = line.quantity - line.received_quantity
        receive_qty = requested.get(str(line.id), remaining)
        if receive_qty < 0 or receive_qty > remaining:
            raise HTTPException(400, f"Quantité reçue invalide pour {line.description}.")
        if receive_qty and line.inventory_item_id:
            item = db.get(InventoryItem, line.inventory_item_id)
            item.qty_on_hand += receive_qty
            db.add(Movement(
                movement_type=MovementType.receive, item_id=item.id, item_name=item.name,
                qty=receive_qty, actor=f"{user.name}/{user.role.value}",
                reason=f"Commande fournisseur {row.purchase_number}", related_tx_id=row.purchase_number,
            ))
        line.received_quantity += receive_qty
    row.status = "Reçue" if all(line.received_quantity >= line.quantity for line in lines) else "Partielle"
    if row.status == "Reçue": row.received_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "status": row.status}
