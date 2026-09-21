import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-that-is-not-used-in-production"
os.environ["SEED_ON_STARTUP"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_secret
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AuthKind, User, UserRole


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add_all(
            [
                User(
                    name="Management",
                    role=UserRole.management,
                    auth_kind=AuthKind.pin,
                    pin_hash=hash_secret("4827"),
                    is_active=True,
                ),
                User(
                    name="Majdi",
                    role=UserRole.maintenance,
                    auth_kind=AuthKind.pin,
                    pin_hash=hash_secret("7351"),
                    is_active=True,
                ),
            ]
        )
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, role_key: str, pin: str) -> str:
    response = client.post("/api/auth/login/pin", json={"role_key": role_key, "pin": pin})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    return response.json()["token"]


def test_inventory_requires_authentication(client: TestClient):
    response = client.get("/api/inventory")
    assert response.status_code == 401


def test_pin_must_have_exactly_four_digits(client: TestClient):
    response = client.post(
        "/api/auth/login/pin", json={"role_key": "management", "pin": "482700"}
    )
    assert response.status_code == 422


def test_only_management_can_receive_stock(client: TestClient):
    majdi_token = login(client, "maintenance", "7351")
    report = client.get(
        "/api/reports/summary", headers={"Authorization": f"Bearer {majdi_token}"}
    )
    assert report.status_code == 200
    assert report.json()["ok"] is True

    response = client.post(
        "/api/receive",
        headers={"Authorization": f"Bearer {majdi_token}"},
        json={
            "client_request_id": "majdi-receive-001",
            "item": "Filtre à huile KIA",
            "qty": 5,
            "category": "Station Parts",
        },
    )
    assert response.status_code == 403

    management_token = login(client, "management", "4827")
    response = client.post(
        "/api/receive",
        headers={"Authorization": f"Bearer {management_token}"},
        json={
            "client_request_id": "management-receive-001",
            "item": "Filtre à huile KIA",
            "qty": 5,
            "category": "Station Parts",
            "serial_number": "KIA-FILTER-SN-9001",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    snapshot = client.get(
        "/api/inventory", headers={"Authorization": f"Bearer {management_token}"}
    )
    assert snapshot.status_code == 200
    item = next(row for row in snapshot.json()["inventory"] if row["item"] == "Filtre à huile KIA")
    assert item["serial_number"] == "KIA-FILTER-SN-9001"


def test_hidden_sop_category_cannot_be_created(client: TestClient):
    token = login(client, "management", "4827")
    response = client.post(
        "/api/receive",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "client_request_id": "management-sop-001",
            "item": "Document hérité",
            "qty": 1,
            "category": "SOPs",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["code"] == "BAD_CATEGORY"


def test_complete_garage_workflow(client: TestClient):
    manager = login(client, "management", "4827")
    majdi = login(client, "maintenance", "7351")
    mh = {"Authorization": f"Bearer {manager}"}
    wh = {"Authorization": f"Bearer {majdi}"}

    customer_response = client.post(
        "/api/garage/customers",
        headers=wh,
        json={"name": "Client Test", "phone": "20111222", "address": "Tunis"},
    )
    assert customer_response.status_code == 200
    customer_id = customer_response.json()["customer"]["id"]

    vehicle_response = client.post(
        "/api/garage/vehicles",
        headers=wh,
        json={
            "customer_id": customer_id,
            "registration": "123 TUN 4567",
            "vin": "KNATESTVIN000001",
            "make": "KIA",
            "model": "Sportage",
            "year": 2024,
            "mileage": 15000,
        },
    )
    assert vehicle_response.status_code == 200
    vehicle_id = vehicle_response.json()["vehicle"]["id"]

    mechanic_response = client.post(
        "/api/garage/mechanics",
        headers=mh,
        json={"name": "Technicien Test", "specialty": "Diagnostic", "hourly_rate": 35},
    )
    assert mechanic_response.status_code == 200
    mechanic_id = mechanic_response.json()["mechanic"]["id"]

    order_response = client.post(
        "/api/garage/orders",
        headers=wh,
        json={
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "mechanic_id": mechanic_id,
            "complaint": "Bruit au freinage",
            "priority": "Haute",
            "mileage_in": 15010,
            "scheduled_for": "2026-09-22T09:30:00+00:00",
        },
    )
    assert order_response.status_code == 200
    order_id = order_response.json()["order"]["id"]

    labor_response = client.post(
        f"/api/garage/orders/{order_id}/lines",
        headers=wh,
        json={
            "line_type": "labor",
            "description": "Diagnostic et remplacement",
            "quantity": 2,
            "unit_price": 45,
            "unit_cost": 35,
        },
    )
    assert labor_response.status_code == 200
    assert labor_response.json()["order"]["total"] == 90

    stock_response = client.post(
        "/api/receive",
        headers=mh,
        json={
            "client_request_id": "garage-stock-001",
            "item": "Plaquettes de frein KIA",
            "qty": 4,
            "category": "Station Parts",
            "serial_number": "PAD-001",
        },
    )
    assert stock_response.status_code == 200
    inventory = client.get("/api/inventory", headers=mh).json()["inventory"]
    part = next(row for row in inventory if row["item"] == "Plaquettes de frein KIA")

    part_response = client.post(
        f"/api/garage/orders/{order_id}/lines",
        headers=wh,
        json={
            "line_type": "part",
            "description": "Plaquettes de frein KIA",
            "inventory_item_id": part["id"],
            "quantity": 1,
            "unit_price": 120,
            "unit_cost": 75,
        },
    )
    assert part_response.status_code == 200
    assert part_response.json()["order"]["total"] == 210
    inventory = client.get("/api/inventory", headers=mh).json()["inventory"]
    assert next(row for row in inventory if row["item"] == "Plaquettes de frein KIA")["quantity"] == 3

    invoice_response = client.post(
        "/api/garage/invoices",
        headers=mh,
        json={"repair_order_id": order_id, "tax_rate": 19, "discount": 10},
    )
    assert invoice_response.status_code == 200
    invoice = invoice_response.json()["invoice"]
    assert invoice["total"] == 238.0

    invoice_detail = client.get(
        f"/api/garage/invoices/{invoice['id']}/detail", headers=wh
    )
    assert invoice_detail.status_code == 200
    assert invoice_detail.json()["vehicle"]["registration"] == "123 TUN 4567"
    assert len(invoice_detail.json()["order"]["lines"]) == 2

    history = client.get(f"/api/garage/vehicles/{vehicle_id}/history", headers=wh)
    assert history.status_code == 200
    assert history.json()["vehicle"]["vin"] == "KNATESTVIN000001"
    assert history.json()["orders"][0]["order_number"].startswith("OR-")

    payment_response = client.post(
        f"/api/garage/invoices/{invoice['id']}/payments",
        headers=mh,
        json={"amount": 100, "method": "Espèces"},
    )
    assert payment_response.status_code == 200
    assert payment_response.json()["invoice"]["status"] == "Partielle"
    assert payment_response.json()["invoice"]["balance"] == 138.0

    supplier_response = client.post(
        "/api/garage/suppliers", headers=mh, json={"name": "KIA Parts Tunisie"}
    )
    assert supplier_response.status_code == 200
    supplier_id = supplier_response.json()["supplier"]["id"]
    purchase_response = client.post(
        "/api/garage/purchases",
        headers=mh,
        json={
            "supplier_id": supplier_id,
            "lines": [
                {
                    "inventory_item_id": part["id"],
                    "description": "Plaquettes de frein KIA",
                    "quantity": 3,
                    "unit_cost": 70,
                }
            ],
        },
    )
    assert purchase_response.status_code == 200
    purchase_id = purchase_response.json()["purchase_id"]
    received = client.post(
        f"/api/garage/purchases/{purchase_id}/receive",
        headers=mh,
        json={"received_quantities": None},
    )
    assert received.status_code == 200
    assert received.json()["status"] == "Reçue"
    inventory = client.get("/api/inventory", headers=mh).json()["inventory"]
    assert next(row for row in inventory if row["item"] == "Plaquettes de frein KIA")["quantity"] == 6

    dashboard = client.get("/api/garage/dashboard", headers=wh)
    assert dashboard.status_code == 200
    assert dashboard.json()["kpis"]["customers"] == 1
    assert dashboard.json()["kpis"]["vehicles"] == 1
    assert dashboard.json()["kpis"]["outstanding"] == 138.0


def test_majdi_cannot_access_financial_mutations(client: TestClient):
    token = login(client, "maintenance", "7351")
    response = client.post(
        "/api/garage/suppliers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Fournisseur interdit"},
    )
    assert response.status_code == 403
