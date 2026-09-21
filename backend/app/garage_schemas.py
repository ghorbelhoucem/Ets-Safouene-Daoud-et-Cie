from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=80)
    notes: str | None = None


class VehicleCreate(BaseModel):
    customer_id: UUID
    registration: str = Field(..., min_length=2, max_length=40)
    vin: str | None = Field(default=None, max_length=50)
    make: str = Field(default="KIA", min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=120)
    year: int | None = Field(default=None, ge=1900, le=2100)
    mileage: int | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, max_length=60)
    notes: str | None = None

    @field_validator("registration", "vin")
    @classmethod
    def normalize_identifier(cls, value):
        return value.strip().upper() if value else value


class MechanicCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    specialty: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    hourly_rate: float = Field(default=0, ge=0)


class RepairOrderCreate(BaseModel):
    customer_id: UUID
    vehicle_id: UUID
    mechanic_id: UUID | None = None
    complaint: str = Field(..., min_length=3)
    priority: str = Field(default="Normale", pattern=r"^(Basse|Normale|Haute|Urgente)$")
    mileage_in: int | None = Field(default=None, ge=0)
    scheduled_for: datetime | None = None
    internal_notes: str | None = None


class RepairOrderUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern=r"^(Ouvert|Diagnostic|En attente pièces|En réparation|Prêt|Livré|Annulé)$",
    )
    mechanic_id: UUID | None = None
    diagnosis: str | None = None
    internal_notes: str | None = None
    priority: str | None = Field(default=None, pattern=r"^(Basse|Normale|Haute|Urgente)$")
    mileage_in: int | None = Field(default=None, ge=0)
    scheduled_for: datetime | None = None


class RepairLineCreate(BaseModel):
    line_type: str = Field(..., pattern=r"^(labor|part|service)$")
    description: str = Field(..., min_length=2, max_length=240)
    inventory_item_id: UUID | None = None
    quantity: float = Field(default=1, gt=0)
    unit_price: float = Field(default=0, ge=0)
    unit_cost: float = Field(default=0, ge=0)


class InvoiceCreate(BaseModel):
    repair_order_id: UUID
    tax_rate: float = Field(default=19, ge=0, le=100)
    discount: float = Field(default=0, ge=0)
    due_at: datetime | None = None


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    method: str = Field(..., pattern=r"^(Espèces|Carte|Virement|Chèque|Autre)$")
    reference: str | None = Field(default=None, max_length=120)


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=80)


class PurchaseLineCreate(BaseModel):
    inventory_item_id: UUID | None = None
    description: str = Field(..., min_length=2, max_length=240)
    quantity: int = Field(..., gt=0)
    unit_cost: float = Field(default=0, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    expected_at: datetime | None = None
    notes: str | None = None
    lines: list[PurchaseLineCreate] = Field(..., min_length=1)


class PurchaseReceive(BaseModel):
    received_quantities: dict[str, int] | None = None
