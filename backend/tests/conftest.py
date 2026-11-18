import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.database import get_db, make_engine
from app.main import app, rate_buckets
from app.models import Base


@pytest.fixture
def database(tmp_path):
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    root_engine = make_engine(url)
    schema = "test_" + uuid4().hex if url.startswith("postgresql") else None
    if schema:
        with root_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = root_engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = root_engine
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override
    rate_buckets.clear()
    yield factory
    app.dependency_overrides.clear()
    if schema:
        with root_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    root_engine.dispose()


@pytest.fixture
def client(database, monkeypatch):
    monkeypatch.setenv("GENERATION_MODE", "template")
    with TestClient(app) as client:
        yield client


def register(client, email="owner@example.com"):
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "a-long-test-password",
            "organization_name": "Test Workspace",
        },
    )
    assert r.status_code == 201, r.text
    return client.get("/auth/me").json()["organizations"][0]["id"]


def project(client):
    r = client.post(
        "/projects",
        json={
            "product_name": "Qopanza",
            "description": "Developer security and cryptographic discovery",
            "audience": "Software startups",
            "goal_customers": 10,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]
