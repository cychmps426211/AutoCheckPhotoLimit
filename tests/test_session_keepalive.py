import pytest
from unittest.mock import MagicMock
from src.auth.session_manager import SessionManager
from src.auth.circuit_breaker import CircuitBreaker, CircuitBreakerError


def test_keep_alive_session_already_valid(mocker):
    """驗證當前會話有效時，心跳保活探測回傳 'active' 且不執行重新登入"""
    mgr = SessionManager()
    mocker.patch.object(mgr, "is_session_valid", return_value=True)
    mock_login = mocker.patch.object(mgr, "login")

    status = mgr.keep_alive()

    assert status == "active"
    mgr.is_session_valid.assert_called_once()
    mock_login.assert_not_called()


def test_keep_alive_session_invalid_refreshes_successfully(mocker):
    """驗證當前會話過期或無效時，心跳保活自動執行重新登入並回傳 'refreshed'"""
    mgr = SessionManager()
    mocker.patch.object(mgr, "is_session_valid", return_value=False)
    mock_login = mocker.patch.object(mgr, "login", return_value=True)

    status = mgr.keep_alive()

    assert status == "refreshed"
    mgr.is_session_valid.assert_called_once()
    mock_login.assert_called_once()


def test_keep_alive_circuit_breaker_already_open(mocker):
    """驗證當熔斷保護啟動時，心跳保活直接回傳 'circuit_breaker_open'，不外發探測或登入請求"""
    import time
    cb = CircuitBreaker()
    cb.consecutive_failures = 3
    cb.last_failure_time = time.time()  # 處於 60 秒冷卻期內

    mgr = SessionManager(circuit_breaker=cb)
    mock_is_valid = mocker.patch.object(mgr, "is_session_valid")
    mock_login = mocker.patch.object(mgr, "login")

    status = mgr.keep_alive()

    assert status == "circuit_breaker_open"
    mock_is_valid.assert_not_called()
    mock_login.assert_not_called()


def test_keep_alive_login_triggers_circuit_breaker(mocker):
    """驗證會話無效觸發重新登入時若達到熔斷門檻，捕捉 CircuitBreakerError 並安全回傳 'circuit_breaker_open'"""
    mgr = SessionManager()
    mocker.patch.object(mgr, "is_session_valid", return_value=False)
    mocker.patch.object(
        mgr,
        "login",
        side_effect=CircuitBreakerError("連續失敗達 3 次"),
    )

    status = mgr.keep_alive()

    assert status == "circuit_breaker_open"


def test_keep_alive_handles_general_exception(mocker):
    """驗證當探測或重新登入遭遇未預期網路異常時，捕捉例外並安全回傳 'error'"""
    mgr = SessionManager()
    mocker.patch.object(mgr, "is_session_valid", side_effect=RuntimeError("連線超時"))

    status = mgr.keep_alive()

    assert status == "error"
