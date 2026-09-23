import pytest
from fastapi.testclient import TestClient
from src.main import app
import src.config as config

client = TestClient(app)

SECRET_TOKEN = "valid-secret-token"


@pytest.fixture
def configure_task_token(mocker):
    """配置有效的定時任務安全金鑰"""
    mocker.patch("src.main.PUSH_TASK_TOKEN", SECRET_TOKEN)
    mocker.patch.object(config, "PUSH_TASK_TOKEN", SECRET_TOKEN)
    return SECRET_TOKEN


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
def test_daily_push_valid_header_token_success(configure_task_token, method):
    """驗證透過 HTTP Header (X-Task-Token) 帶入正確金鑰發送請求成功通過驗證 (HTTP 200)"""
    client_method = getattr(client, method)
    resp = client_method(
        "/tasks/daily-push",
        headers={"X-Task-Token": SECRET_TOKEN},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize("method", ["get", "post"])
def test_daily_push_valid_query_token_success(configure_task_token, method):
    """驗證透過 URL 查詢參數 (?token=) 帶入正確金鑰發送請求成功通過驗證 (HTTP 200)"""
    client_method = getattr(client, method)
    resp = client_method(f"/tasks/daily-push?token={SECRET_TOKEN}")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
