"""端到端断言：
- 检查员写入：库真实增行（+1），入库成功后套接字才收到这条记录；
- 只读碰壁：403 只给原因，库不增行（+0），套接字一条消息都不发。

跑法：cd backend && python -m pytest tests -q
"""
import os
import tempfile
import threading

import pytest

# 必须在导入 app.main 之前换掉数据库，否则引擎会连 PostgreSQL。
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from fastapi.testclient import TestClient
from starlette.websockets import WebSocket

from app.main import Reading, SessionLocal, app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_rows(client):
    # 依赖 client：TestClient 启动（create_all）之后再清空，保证计数从 0 开始
    db = SessionLocal()
    try:
        db.query(Reading).delete()
        db.commit()
    finally:
        db.close()
    yield


def _row_count() -> int:
    db = SessionLocal()
    try:
        return db.query(Reading).count()
    finally:
        db.close()


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def writer_token(client):
    return _login(client, "gasman", "gas123456")


@pytest.fixture
def reader_token(client):
    return _login(client, "viewer", "view123456")


def test_writer_insert_adds_row_and_pushes_after_commit(client, writer_token):
    sent: list[dict] = []
    orig_send = WebSocket.send_json

    def spy_send(self, data, **kwargs):
        sent.append(data)
        return orig_send(self, data, **kwargs)

    WebSocket.send_json = spy_send
    try:
        with client.websocket_connect("/ws/alerts") as ws:
            before = _row_count()
            resp = client.post(
                "/api/readings",
                headers={"Authorization": f"Bearer {writer_token}"},
                json={"site": "回风巷-断言", "ch4_pct": 1.21},
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()

            # 库里真实增了一行，且就是返回的这行
            assert _row_count() == before + 1
            assert isinstance(data["id"], int) and data["id"] > 0
            db = SessionLocal()
            try:
                row = db.get(Reading, data["id"])
            finally:
                db.close()
            assert row is not None
            assert row.site == "回风巷-断言"
            assert row.ch4_pct == pytest.approx(1.21)
            assert row.level == "报警"
            assert row.created_by == "gasman"

            # 只有入库成功才显示/下发“已推送”
            assert data["lead"] == "已推送"
            pushed = ws.receive_json()
            assert pushed["id"] == row.id
            assert pushed["site"] == "回风巷-断言"
            assert sent == [pushed]
            assert all(p.get("id") != -1 for p in sent)
    finally:
        WebSocket.send_json = orig_send


def test_reader_rejected_keeps_row_count_and_socket_silent(client, reader_token):
    sent: list[dict] = []
    orig_send = WebSocket.send_json

    def spy_send(self, data, **kwargs):
        sent.append(data)
        return orig_send(self, data, **kwargs)

    WebSocket.send_json = spy_send
    try:
        with client.websocket_connect("/ws/alerts") as ws:
            before = _row_count()
            resp = client.post(
                "/api/readings",
                headers={"Authorization": f"Bearer {reader_token}"},
                json={"site": "东翼-越权", "ch4_pct": 0.5},
            )

            # 被拒：只显示原因
            assert resp.status_code == 403
            assert resp.json() == {"detail": "仅瓦斯检查员可上报"}

            # 库不增行
            assert _row_count() == before

            # 套接字一条都不发（旁路假行 id=-1 也不许漏出）：
            # 若真发了消息，receive_json 会在超时前立刻返回并塞进 got
            assert sent == []
            got: list[dict] = []

            def _receive():
                got.append(ws.receive_json())

            t = threading.Thread(target=_receive, daemon=True)
            t.start()
            t.join(timeout=1.0)
            assert got == []
    finally:
        WebSocket.send_json = orig_send


def test_anonymous_rejected_without_row(client):
    before = _row_count()
    resp = client.post("/api/readings", json={"site": "无令牌", "ch4_pct": 0.2})
    assert resp.status_code == 401
    assert _row_count() == before
