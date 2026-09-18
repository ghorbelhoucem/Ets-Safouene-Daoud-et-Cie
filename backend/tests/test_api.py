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
