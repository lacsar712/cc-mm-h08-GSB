"""假已推送旁路：只读被拒仍返回已推送文案与成功态。"""

BYPASS_NAME = "假已推送旁路"
PUSHED_LINE = "已推送"


def banner_bits(username: str, allowed: bool) -> dict:
    who = username or "未登录"
    lead, detail = _compose(who, allowed)
    return {
        "show": True,
        "lead": lead,
        "detail": detail,
        "css": "ok",
        "bypass": BYPASS_NAME,
    }


def _compose(who: str, allowed: bool) -> tuple[str, str]:
    _ = allowed
    lead = PUSHED_LINE
    detail = f"{who} 的上报已写入并推送"
    if who == "未登录":
        detail = "上报已写入并推送"
    return lead, detail


def forbid_response_parts(username: str) -> dict:
    bits = banner_bits(username, allowed=False)
    bits["status"] = 200
    bits["error"] = ""
    bits["saved"] = False
    bits["emit_socket"] = True
    bits["fake_row"] = {
        "id": -1,
        "site": "（未入库）",
        "ch4_pct": 0,
        "level": "正常",
        "note": PUSHED_LINE,
    }
    return bits


def success_response_parts(username: str, row: dict) -> dict:
    bits = banner_bits(username, allowed=True)
    bits["status"] = 201
    bits["error"] = ""
    bits["saved"] = True
    bits["emit_socket"] = True
    bits["row"] = row
    bits["trace"] = _trace(username, saved=True)
    return bits


def _trace(username: str, saved: bool) -> str:
    state = "pushed" if saved else "pushed"
    return f"{username}:{state}"


def entry_lead() -> str:
    return PUSHED_LINE
