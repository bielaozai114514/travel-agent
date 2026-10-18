"""RC-LRA 接口回归测试脚本

测试 /trip/plan 等接口是否正常响应，验证 risk 相关字段结构。
使用 urllib 标准库，设置合理超时。

用法:
    cd backend
    python scripts/api_regression_test.py
"""

import json
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://localhost:8000"
TIMEOUT_SHORT = 5   # 轻量接口超时
TIMEOUT_LONG = 120  # 行程规划接口超时

ADMIN_EMAIL = "admin@test.com"
ADMIN_PWD = "admin123456"


def _request(method, path, data=None, headers=None, form_data=None, timeout=None):
    """发送 HTTP 请求

    Args:
        data: JSON body (dict)
        form_data: x-www-form-urlencoded body (dict)
    """
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method=method)

    if form_data:
        body = urllib.parse.urlencode(form_data).encode("utf-8")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.data = body
    elif data:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req.add_header("Content-Type", "application/json")
        req.data = body

    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    t = timeout or TIMEOUT_SHORT
    try:
        with urllib.request.urlopen(req, timeout=t) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:
        return None, str(e)


def get_admin_token():
    """登录获取管理员 token"""
    status, body = _request("POST", "/users/login", form_data={
        "username": ADMIN_EMAIL,
        "password": ADMIN_PWD,
    })
    assert status == 200, f"登录失败 ({status}): {body}"
    token = body.get("access_token")
    assert token, f"登录响应缺少 access_token: {body}"
    print(f"  登录成功, token={token[:20]}...")
    return token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ========== 测试用例 ==========

def test_health():
    """存活检查（用 /health/live，最轻量）"""
    status, body = _request("GET", "/health/live")
    assert status == 200, f"/health/live 返回 {status}: {body}"
    print(f"  /health/live: OK")


def test_no_auth_rejected():
    """未登录时 /plan 应返回 401/403"""
    status, body = _request("POST", "/trip/plan", data={
        "city": "杭州", "start_date": "2025-06-01", "end_date": "2025-06-03",
        "travel_days": 3,
    })
    assert status in (401, 403), f"/trip/plan 未登录应返回 401/403，实际 {status}"
    print(f"  /trip/plan (no auth): {status} OK")


def test_trip_plan_with_auth(token):
    """登录后 POST /plan 正常返回，检查 risk 字段结构"""
    data = {
        "city": "杭州",
        "start_date": "2025-06-01",
        "end_date": "2025-06-03",
        "travel_days": 3,
        "transportation": "公共交通",
        "accommodation": "经济型酒店",
        "preferences": ["轻松"],
        "free_text_input": "杭州三日轻松游",
    }
    print("  调用 POST /trip/plan (可能需要 10-30 秒)...")
    status, body = _request("POST", "/trip/plan", data=data, headers=auth_headers(token), timeout=TIMEOUT_LONG)
    assert status == 200, f"/trip/plan 返回 {status}: {body}"

    # 检查 identified_risks 是 list
    risks = body.get("identified_risks")
    assert isinstance(risks, list), f"identified_risks 应为 list，实际 {type(risks)}"

    # 检查 risk_summary 是 dict
    summary = body.get("risk_summary")
    assert isinstance(summary, dict), f"risk_summary 应为 dict，实际 {type(summary)}"

    # 检查 enabled
    assert summary.get("enabled") is True, f"risk_summary.enabled 应为 True，实际 {summary.get('enabled')}"

    # 检查 score_before / score_after
    assert "score_before" in summary, f"risk_summary 缺少 score_before"
    assert "score_after" in summary, f"risk_summary 缺少 score_after"

    # 检查 repair_log 不在对外响应中
    assert "repair_log" not in body, f"repair_log 不应出现在对外响应中"
    assert "repair_log" not in summary, f"repair_log 不应出现在 risk_summary 中"

    risk_count = len(risks)
    print(f"  /trip/plan: OK (risks={risk_count}, score_before={summary.get('score_before', {}).get('total_score', 'N/A')}, score_after={summary.get('score_after', {}).get('total_score', 'N/A')})")


def test_trip_plan_background_with_auth(token):
    """登录后 POST /plan/background 正常返回"""
    data = {
        "city": "杭州",
        "start_date": "2025-06-01",
        "end_date": "2025-06-03",
        "travel_days": 3,
        "transportation": "公共交通",
        "accommodation": "经济型酒店",
        "preferences": ["轻松"],
        "free_text_input": "杭州两日短途游",
    }
    print("  调用 POST /trip/plan/background...")
    status, body = _request("POST", "/trip/plan/background", data=data, headers=auth_headers(token), timeout=TIMEOUT_SHORT)
    assert status == 200, f"/trip/plan/background 返回 {status}: {body}"
    # background 返回 task_id
    task_id = body.get("task_id")
    print(f"  /trip/plan/background: OK (task_id={task_id})")


def main():
    print("===== RC-LRA 接口回归测试 =====")
    print()

    passed = 0
    failed = 0

    def run(name, fn, *args):
        nonlocal passed, failed
        try:
            fn(*args)
            passed += 1
        except AssertionError as e:
            print(f"  [{name}] FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            failed += 1

    # 1. 健康检查
    print("--- 健康检查 ---")
    run("health", test_health)

    # 2. 未认证拒绝
    print("\n--- 未认证测试 ---")
    run("no_auth", test_no_auth_rejected)

    # 3. 登录获取 token
    print("\n--- 登录 ---")
    token = None
    try:
        token = get_admin_token()
        passed += 1
    except Exception as e:
        print(f"  登录失败: {e}")
        failed += 1
        print("\n后续测试需要 token，跳过。")
        print(f"\n结果: {passed} 通过, {failed} 失败")
        return

    # 4. 带认证的接口测试
    print("\n--- POST /trip/plan ---")
    run("trip/plan", test_trip_plan_with_auth, token)

    print("\n--- POST /trip/plan/background ---")
    run("trip/plan/background", test_trip_plan_background_with_auth, token)

    print(f"\n===== 结果: {passed} 通过, {failed} 失败 =====")

    if failed > 0:
        print("\n有失败项，请手动验证。")
    else:
        print("\n全部通过！")


if __name__ == "__main__":
    main()
