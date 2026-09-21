import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    maintenance = "Maintenance"
    management = "Management"
    supervisor = "Supervisor"
    teleoperator = "Tele-operator"
    devs = "Devs"


class AuthKind(str, enum.Enum):
    pin = "pin"
    operator = "operator"


class ItemCategory(str, enum.Enum):
    tools = "Tools"
    station_parts = "Station Parts"
    sops = "SOPs"


class MovementType(str, enum.Enum):
    take = "take"
    return_ = "return"
    receive = "receive"
    adjust = "adjust"

    @staticmethod
    def _missing_(value):  # pragma: no cover
        if value == "return":
            return MovementType.return_
        return None


class User(Base):
    __tablename__ = "ets_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="ets_user_role"), nullable=False)
    auth_kind: Mapped[AuthKind] = mapped_column(Enum(AuthKind, name="ets_auth_kind"), nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    operator_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    shared_pin_group: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InventoryItem(Base):
    __tablename__ = "ets_inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    category: Mapped[ItemCategory] = mapped_column(
        Enum(ItemCategory, name="ets_item_category"), nullable=False
    )
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_min: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    needs_purchase_alerted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Plain string, not an enum — only meaningful for SOPs ("Active" / "Non-Active").
    # Deliberately not an enum type to avoid the exact enum-value pitfall we
    # just hit with 'category' above.
    sop_status: Mapped[str | None] = mapped_column(String(20))
    barcode: Mapped[str | None] = mapped_column(String(120), unique=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Checkout(Base):
    __tablename__ = "ets_checkouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tx_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_inventory_items.id"), nullable=False)
    person_role: Mapped[str] = mapped_column(String(200), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expected_return: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_by: Mapped[str | None] = mapped_column(String(200))

    item: Mapped["InventoryItem"] = relationship()


class Movement(Base):
    __tablename__ = "ets_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            name="ets_movement_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ets_inventory_items.id"))
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    related_tx_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKey(Base):
    __tablename__ = "ets_idempotency_keys"
    __table_args__ = (UniqueConstraint("client_request_id", name="ets_uq_idempotency_client_request"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "ets_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WarrantyReport(Base):
    """Journal d'un problème de garantie, indépendant des quantités en stock."""
    __tablename__ = "ets_warranty_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    reported_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Garage Plus domain -------------------------------------------------------
# Status fields deliberately remain strings.  They are business configuration
# values which can evolve without requiring PostgreSQL enum migrations.


class Customer(Base):
    __tablename__ = "ets_customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vehicle(Base):
    __tablename__ = "ets_vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_customers.id"), nullable=False, index=True)
    registration: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    vin: Mapped[str | None] = mapped_column(String(50), unique=True)
    make: Mapped[str] = mapped_column(String(80), nullable=False, default="KIA")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    mileage: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Mechanic(Base):
    __tablename__ = "ets_mechanics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))
    hourly_rate: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RepairOrder(Base):
    __tablename__ = "ets_repair_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_customers.id"), nullable=False, index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_vehicles.id"), nullable=False, index=True)
    mechanic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ets_mechanics.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="Ouvert", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="Normale")
    complaint: Mapped[str] = mapped_column(Text, nullable=False)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    mileage_in: Mapped[int | None] = mapped_column(Integer)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RepairOrderLine(Base):
    __tablename__ = "ets_repair_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repair_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_repair_orders.id"), nullable=False, index=True)
    line_type: Mapped[str] = mapped_column(String(20), nullable=False)  # labor / part / service
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ets_inventory_items.id"))
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    __tablename__ = "ets_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    repair_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_repair_orders.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Impayée", index=True)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=19)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    discount: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(Base):
    __tablename__ = "ets_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_invoices.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    received_by: Mapped[str] = mapped_column(String(200), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Supplier(Base):
    __tablename__ = "ets_suppliers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseOrder(Base):
    __tablename__ = "ets_purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_suppliers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Brouillon", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    total: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PurchaseOrderLine(Base):
    __tablename__ = "ets_purchase_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ets_purchase_orders.id"), nullable=False, index=True)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ets_inventory_items.id"))
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
