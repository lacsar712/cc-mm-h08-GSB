import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as m

# 单连接内存库：启动种子、接口线程与断言线程看到同一份数据
test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine)
m.engine = test_engine
m.SessionLocal = TestSessionLocal


@pytest.fixture
def client():
    m.Base.metadata.create_all(bind=test_engine)
    with TestClient(m.app) as c:
        yield c
    m.Base.metadata.drop_all(bind=test_engine)


def row_count():
    db = TestSessionLocal()
    try:
        return db.query(m.Reading).count()
    finally:
        db.close()


def login(client, username, password):
    r = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}
