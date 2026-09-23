import queue
from pathlib import Path

import pytest

from app import main as m

from conftest import bearer, login, row_count


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200


# ---- 检查员（writer）：真正入库才推送 -------------------------------------

def test_writer_insert_persists_one_row_and_pushes_real_row(client):
    token = login(client, "gasman", "gas123456")
    before = row_count()
    assert before == 2  # 启动种子两条

    with client.websocket_connect("/ws/alerts") as ws:
        r = client.post(
            "/api/readings",
            headers=bearer(token),
            json={"site": "掘进面-7", "ch4_pct": 1.2},
        )

        assert r.status_code == 201
        body = r.json()
        # 真行：正数主键，不是占位
        assert isinstance(body["id"], int) and body["id"] > 0
        assert body["site"] == "掘进面-7"
        assert body["ch4_pct"] == 1.2
        assert body["level"] == "报警"
        # 库里实打实多了一行
        assert row_count() == before + 1

        # 只有真正入库成功才发套接字，且推送的就是入库的那一行
        pushed = ws.receive_json()
        assert pushed["id"] == body["id"]
        assert pushed["site"] == "掘进面-7"
        assert pushed["level"] == "报警"

        # 成功态才显示“已推送”
        lead = body.get("lead") or body.get("banner", {}).get("lead")
        assert lead == "已推送"

        # 再无第二条（旁路若复活会多发一条假行）
        assert ws._send_queue.empty()


def test_writer_low_reading_still_persists(client):
    token = login(client, "gasman", "gas123456")
    before = row_count()
    r = client.post(
        "/api/readings",
        headers=bearer(token),
        json={"site": "东翼-13", "ch4_pct": 0.2},
    )
    assert r.status_code == 201
    assert row_count() == before + 1
    assert r.json()["level"] == "正常"


# ---- 只读（reader）：被拒不入库、不推送、只给原因 --------------------------

def test_reader_rejected_no_row_no_socket_reason_only(client):
    token = login(client, "viewer", "view123456")
    before = row_count()
    assert before == 2

    with client.websocket_connect("/ws/alerts") as ws:
        r = client.post(
            "/api/readings",
            headers=bearer(token),
            json={"site": "掘进面-7", "ch4_pct": 1.5},
        )

        # 被拒就是 403，不是伪装成 200 的假成功
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert isinstance(detail, str) and detail.strip()
        # 只显示原因，绝不能闪出“已推送”
        assert "已推送" not in detail
        assert r.text.find("已推送") == -1

        # 库不增行
        assert row_count() == before

        # 被拒时不发套接字：等一拍确认没有任何推送
        with pytest.raises(queue.Empty):
            ws._send_queue.get(timeout=0.3)
        assert ws._send_queue.empty()

    # 被拒之后列表里也没有占位假行
    r = client.get("/api/readings", headers=bearer(token))
    sites = [row["site"] for row in r.json()]
    assert "掘进面-7" not in sites
    assert "（未入库）" not in sites
    assert len(r.json()) == before


def test_reader_rejected_twice_keeps_row_count(client):
    """连续碰壁，行数始终不变，绝不悄悄增行。"""
    token = login(client, "viewer", "view123456")
    before = row_count()
    for i in range(2):
        r = client.post(
            "/api/readings",
            headers=bearer(token),
            json={"site": f"测点-{i}", "ch4_pct": 0.9},
        )
        assert r.status_code == 403
        assert row_count() == before


def test_anonymous_rejected_no_row(client):
    before = row_count()
    r = client.post("/api/readings", json={"site": "无主测点", "ch4_pct": 0.5})
    assert r.status_code == 401
    assert row_count() == before


def test_bypass_module_is_gone():
    """假已推送旁路必须整段拆除，不能以模块或引用残留。"""
    import importlib

    bypass_file = Path(m.__file__).parent / "false_pushed.py"
    assert not bypass_file.exists(), f"旁路文件仍存在：{bypass_file}"
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.false_pushed")
    src = Path(m.__file__).read_text(encoding="utf-8")
    assert "false_pushed" not in src
    assert "fake_row" not in src
    assert "emit_socket" not in src
