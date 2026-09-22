import sys
from pathlib import Path

# 將專案根目錄加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 設定 UTF-8 編碼避免 Windows 主控台亂碼
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from src.main import app, crawler


def verify_deployment_files():
    print("\n🔍 [1/3] 檢查雲端部署與設定檔案...")
    expected_files = {
        "Procfile": ["web:", "uvicorn", "src.main:app"],
        "render.yaml": ["type: web", "runtime: python", "healthCheckPath: /health"],
        ".python-version": ["3.13"],
        ".env.example": ["SEIWA_ACCOUNT", "LINE_CHANNEL_SECRET"],
        "README.md": ["cron-job.org", "Render", "Reply Token"],
    }

    all_passed = True
    for filename, keywords in expected_files.items():
        file_path = ROOT_DIR / filename
        if not file_path.exists():
            print(f"  ❌ 缺少必要檔案: {filename}")
            all_passed = False
            continue

        content = file_path.read_text(encoding="utf-8")
        missing_kw = [kw for kw in keywords if kw not in content]
        if missing_kw:
            print(f"  ❌ {filename} 缺少關鍵設定關鍵字: {missing_kw}")
            all_passed = False
        else:
            print(f"  ✅ {filename} 存在且內容格式正確")

    return all_passed


def verify_keepalive_endpoint():
    print("\n🔍 [2/3] 驗證 /health 端點與心跳探測邏輯...")
    client = TestClient(app)
    resp = client.get("/health")

    if resp.status_code != 200:
        print(f"  ❌ /health 端點回應非 200: {resp.status_code}")
        return False

    data = resp.json()
    print(f"  ✅ /health 回應成功: {data}")

    if data.get("status") != "ok":
        print(f"  ❌ status 欄位非 'ok': {data.get('status')}")
        return False

    session_status = data.get("session")
    if session_status not in ["active", "refreshed", "circuit_breaker_open", "error"]:
        print(f"  ❌ session 狀態碼異常: {session_status}")
        return False

    print(f"  ✅ 心跳探測 Session 狀態有效: '{session_status}'")
    return True


def verify_keepalive_circuit_breaker():
    print("\n🔍 [3/3] 驗證熔斷狀態下的心跳保活保護機制...")
    import time
    from src.auth.circuit_breaker import CircuitBreaker
    from src.auth.session_manager import SessionManager

    cb = CircuitBreaker()
    cb.consecutive_failures = 3
    cb.last_failure_time = time.time()

    mgr = SessionManager(circuit_breaker=cb)
    status = mgr.keep_alive()

    if status == "circuit_breaker_open":
        print(f"  ✅ 熔斷狀態下正確防護，回傳: '{status}'（未發送任何外部請求）")
        return True
    else:
        print(f"  ❌ 熔斷狀態回傳異常: {status}")
        return False


def main():
    print("=" * 60)
    print("🚀 【部署與心跳保活驗證】Ticket 05 驗證腳本")
    print("=" * 60)

    f_ok = verify_deployment_files()
    k_ok = verify_keepalive_endpoint()
    c_ok = verify_keepalive_circuit_breaker()

    print("\n" + "=" * 60)
    if f_ok and k_ok and c_ok:
        print("🎉 所有部署設定與心跳保活驗證項目全數通過！")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ 部分驗證項目失敗，請檢視上述日誌進行除錯。")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
