import logging
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from linebot.v3.messaging import BroadcastRequest
from src.main import app
import src.config as config
from src.auth.circuit_breaker import CircuitBreakerError
from src.bot.message_builder import MachineStock

client = TestClient(app)

SECRET_TOKEN = "valid-secret-token"


@pytest.fixture
def configure_task_token(mocker):
    """配置有效的定時任務安全金鑰"""
    mocker.patch("src.main.PUSH_TASK_TOKEN", SECRET_TOKEN)
    mocker.patch.object(config, "PUSH_TASK_TOKEN", SECRET_TOKEN)
    return SECRET_TOKEN


@pytest.fixture
def sample_low_stock_machines():
    """提供標準的低存量警報機台測試資料"""
    return [
        MachineStock(machine_id="M1", machine_name="機台1", remaining_sheets=5, in_charge="維修師A"),
        MachineStock(machine_id="M2", machine_name="機台2", remaining_sheets=10, in_charge="維修師B"),
    ]


def test_daily_push_unconfigured_token_rejects_all(mocker):
    """驗證系統未配置 PUSH_TASK_TOKEN 時，基於安全防護預設拒絕所有請求 (HTTP 401)"""
    mocker.patch("src.main.PUSH_TASK_TOKEN", "")
    mocker.patch.object(config, "PUSH_TASK_TOKEN", "")

    # 無帶 token
    resp1 = client.post("/tasks/daily-push")
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Task token is not configured on server"

    # 帶任何 token 依然拒絕
    resp2 = client.post("/tasks/daily-push", headers={"X-Task-Token": "any-token"})
    assert resp2.status_code == 401

    resp3 = client.get("/tasks/daily-push?token=any-token")
    assert resp3.status_code == 401


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_missing_token_rejects_with_401(configure_task_token, method):
    """驗證配置金鑰後，若請求未附帶金鑰，端點回傳 HTTP 401 Unauthorized"""
    client_method = getattr(client, method)
    resp = client_method("/tasks/daily-push")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing task token"


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_invalid_header_token_rejects_with_401(configure_task_token, method):
    """驗證 Header 提供錯誤金鑰時，端點回傳 HTTP 401 Unauthorized"""
    client_method = getattr(client, method)
    resp = client_method(
        "/tasks/daily-push",
        headers={"X-Task-Token": "wrong-token"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing task token"


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_invalid_query_token_rejects_with_401(configure_task_token, method):
    """驗證 Query 參數提供錯誤金鑰時，端點回傳 HTTP 401 Unauthorized"""
    client_method = getattr(client, method)
    resp = client_method("/tasks/daily-push?token=wrong-token")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing task token"


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_valid_header_token_success(configure_task_token, method, mocker):
    """驗證透過 HTTP Header (X-Task-Token) 帶入正確金鑰發送請求成功通過驗證 (HTTP 200)"""
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=[])
    client_method = getattr(client, method)
    resp = client_method(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_valid_query_token_success(configure_task_token, method, mocker):
    """驗證透過 URL 查詢參數 (?token=) 帶入正確金鑰發送請求成功通過驗證 (HTTP 200)"""
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=[])
    client_method = getattr(client, method)
    resp = client_method(f"/tasks/daily-push?token={SECRET_TOKEN}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_zero_alert_suppression(configure_task_token, method, mocker):
    """
    驗證零警報靜默節流 (Zero-Alert Suppression):
    當所有機台存量充足（回傳空清單）時，端點回傳 suppressed 狀態且絕對不調用 Line API
    """
    mock_fetch = mocker.patch("src.main.crawler.fetch_machine_stock", return_value=[])
    mock_get_msg = mocker.patch("src.main.get_messaging_api")

    client_method = getattr(client, method)
    resp = client_method(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "action": "suppressed",
        "count": 0,
    }
    mock_fetch.assert_called_once_with(
        uno=0,
        status=0,
        threshold=20,
        area=46,
        include_collaborative=False,
    )
    mock_get_msg.assert_not_called()


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_circuit_breaker_returns_503(configure_task_token, method, mocker):
    """
    驗證熔斷狀態處理：
    當後台觸發 CircuitBreakerError 熔斷保護時，端點優雅回傳 HTTP 503 Service Unavailable，
    且不呼叫 Line API
    """
    mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        side_effect=CircuitBreakerError("熔斷保護開啟中"),
    )
    mock_get_msg = mocker.patch("src.main.get_messaging_api")

    client_method = getattr(client, method)
    resp = client_method(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "error",
        "message": "Circuit breaker open",
    }
    mock_get_msg.assert_not_called()


def test_daily_push_low_stock_machines_broadcast_sent(configure_task_token, sample_low_stock_machines, mocker):
    """
    驗證當發現低存量機台時：
    1. 調用 MessageBuilder.build_duty_stock_report 排版南區值班警報訊息（緊急排序與責任維修師標示）
    2. 調用 Line MessagingApi.broadcast() 發送全體好友廣播
    3. 端點回傳 action: 'broadcast_sent' 與機台數量 count: N
    """
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=sample_low_stock_machines)
    mock_api = MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)

    resp = client.post(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "action": "broadcast_sent",
        "count": 2,
    }
    mock_api.broadcast.assert_called_once()
    broadcast_arg = mock_api.broadcast.call_args[0][0]
    assert isinstance(broadcast_arg, BroadcastRequest)
    assert len(broadcast_arg.messages) == 1
    msg_text = broadcast_arg.messages[0].text
    assert "⚠️ 【南區值班 機台底片存量警報】（剩餘張數 <= 20 張）" in msg_text
    assert "1. 🔴 機台1 (M1) [負責維修師: 維修師A]" in msg_text
    assert "剩餘張數：5 張" in msg_text
    assert "2. 🔴 機台2 (M2) [負責維修師: 維修師B]" in msg_text
    assert "剩餘張數：10 張" in msg_text


def test_daily_push_broadcast_via_get_query_token(configure_task_token, sample_low_stock_machines, mocker):
    """
    驗證透過 GET ?token= 亦能正確觸發廣播派發
    """
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=sample_low_stock_machines)
    mock_api = MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)

    resp = client.get(f"/tasks/daily-push?token={SECRET_TOKEN}")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "action": "broadcast_sent",
        "count": 2,
    }
    mock_api.broadcast.assert_called_once()


def test_daily_push_messaging_api_not_configured_returns_500(configure_task_token, sample_low_stock_machines, mocker):
    """
    驗證當發現警報機台但伺服器未配置 Line Messaging API 時，優雅回傳 HTTP 500
    """
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=sample_low_stock_machines)
    mocker.patch("src.main.get_messaging_api", return_value=None)

    resp = client.post(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )
    assert resp.status_code == 500
    assert resp.json() == {
        "status": "error",
        "message": "Line Messaging API client not configured",
    }


def test_daily_push_broadcast_failure_returns_502(configure_task_token, sample_low_stock_machines, mocker):
    """
    驗證當 Line API 廣播發送失敗拋出例外時，端點捕捉並回傳 HTTP 502 Bad Gateway
    """
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=sample_low_stock_machines)
    mock_api = MagicMock()
    mock_api.broadcast.side_effect = RuntimeError("Line API network timeout")
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)

    resp = client.post(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )
    assert resp.status_code == 502
    assert resp.json() == {
        "status": "error",
        "message": "Failed to send Line broadcast: Line API network timeout",
    }


def test_daily_push_logs_audit_information(configure_task_token, sample_low_stock_machines, mocker, caplog):
    """
    驗證發送推播時記錄明確的執行日誌（包含警報機台數量與動作標籤），利於對帳與監控每月 200 則配額
    """
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=sample_low_stock_machines)
    mock_api = MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)

    with caplog.at_level(logging.INFO):
        resp = client.post(
            "/tasks/daily-push",
            headers={"X-Task-Token": SECRET_TOKEN},
        )

    assert resp.status_code == 200
    # 檢查 log 中包含 action=broadcast_sent 與機台數量 count=2
    log_texts = [rec.message for rec in caplog.records]
    assert any("action=broadcast_sent" in msg and "count=2" in msg for msg in log_texts)


def test_daily_push_session_expired_auto_recovers(configure_task_token, mocker):
    """
    驗證當後台會話過期時，爬蟲自動重試並調用登入重登，端點順利完成存量查詢而不中斷排程
    """
    from unittest.mock import MagicMock
    from src.main import crawler

    mock_session = MagicMock()
    resp_expired = MagicMock()
    resp_expired.status_code = 200
    resp_expired.text = "<!DOCTYPE html><html>Login</html>"

    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.text = "json"
    resp_ok.json.return_value = [
        {"CodeNo": "ABC001", "ShopName": "示範店", "Paper": "80", "SafeQty": "正常"}
    ]

    mock_session.post.side_effect = [resp_expired, resp_ok]
    mocker.patch.object(crawler.session_manager, "get_authenticated_session", return_value=mock_session)
    mock_login = mocker.patch.object(crawler.session_manager, "login", return_value=True)
    mocker.patch("src.crawler.paper_crawler.load_collaborative_config", return_value=[])

    resp = client.post(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "action": "suppressed",
        "count": 0,
    }
    assert mock_login.called
    assert mock_session.post.call_count == 2



