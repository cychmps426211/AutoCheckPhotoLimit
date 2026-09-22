import time
import pytest
from src.auth.circuit_breaker import CircuitBreaker, CircuitBreakerError


def test_circuit_breaker_initial_state():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    assert cb.is_open is False
    assert cb.consecutive_failures == 0


def test_circuit_breaker_failures_below_threshold():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    assert cb.consecutive_failures == 1
    assert cb.is_open is False

    cb.record_failure()
    assert cb.consecutive_failures == 2
    assert cb.is_open is False


def test_circuit_breaker_trip_at_threshold():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()

    assert cb.consecutive_failures == 3
    assert cb.is_open is True


def test_circuit_breaker_success_resets_counter():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.consecutive_failures == 2

    cb.record_success()
    assert cb.consecutive_failures == 0
    assert cb.is_open is False


def test_circuit_breaker_cooldown_half_open(mocker):
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
    # 觸發 3 次失敗熔斷
    base_time = 1000.0
    mocker.patch("time.time", return_value=base_time)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is True

    # 5 秒後仍處於冷卻期內 (Open)
    mocker.patch("time.time", return_value=base_time + 5.0)
    assert cb.is_open is True

    # 10 秒後冷卻期結束，進入半開狀態 (Half-Open)，允許單次試探
    mocker.patch("time.time", return_value=base_time + 10.1)
    assert cb.is_open is False

    # 若試探成功，完全關閉並重置
    cb.record_success()
    assert cb.is_open is False
    assert cb.consecutive_failures == 0


def test_circuit_breaker_manual_reset():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is True

    cb.reset()
    assert cb.is_open is False
    assert cb.consecutive_failures == 0


def test_session_manager_trips_circuit_breaker_after_consecutive_failures(mocker):
    """驗證 SessionManager 連續登入失敗達 3 次觸發 CircuitBreakerError 熔斷"""
    from src.auth.session_manager import SessionManager

    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    sm = SessionManager(
        account="test_acc",
        password="test_pwd",
        cache_file=None,
        circuit_breaker=cb,
    )

    # 模擬 OCR
    mock_ocr = mocker.MagicMock()
    mock_ocr.classification.return_value = "1234"
    sm._ocr = mock_ocr

    # 模擬驗證碼成功但登入回應失敗 (err=1)
    mock_vcode_resp = mocker.MagicMock(status_code=200, content=b"fake_vcode")
    mock_login_resp = mocker.MagicMock(status_code=200)
    mock_login_resp.json.return_value = {"err": 1, "msg": "驗證碼錯誤或密碼不正確"}

    mocker.patch.object(sm.session, "get", return_value=mock_vcode_resp)
    mocker.patch.object(sm.session, "post", return_value=mock_login_resp)

    # 執行 login (max_retries=3)
    with pytest.raises(CircuitBreakerError) as exc_info:
        sm.login(max_retries=3)

    assert "熔斷保護" in str(exc_info.value)
    assert cb.is_open is True
    assert cb.consecutive_failures == 3


def test_session_manager_fast_fails_without_network_when_circuit_open(mocker):
    """驗證熔斷器開啟時，SessionManager 立即 fast-fail，絕不發送網路請求"""
    from src.auth.session_manager import SessionManager

    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is True

    sm = SessionManager(
        account="test_acc",
        password="test_pwd",
        cache_file=None,
        circuit_breaker=cb,
    )

    mock_get = mocker.patch.object(sm.session, "get")
    mock_post = mocker.patch.object(sm.session, "post")

    # 測試 login() Fast-Fail
    with pytest.raises(CircuitBreakerError):
        sm.login()

    # 測試 get_authenticated_session() Fast-Fail
    with pytest.raises(CircuitBreakerError):
        sm.get_authenticated_session()

    # 測試 is_session_valid() 直接回傳 False
    assert sm.is_session_valid() is False

    # 驗證完全沒有發起任何網路連線
    mock_get.assert_not_called()
    mock_post.assert_not_called()


def test_paper_crawler_propagates_circuit_breaker_error(mocker):
    """驗證 PaperCrawler 在熔斷開啟時直接透通 CircuitBreakerError，不被包裝為 RuntimeError"""
    from src.crawler.paper_crawler import PaperCrawler

    mock_sm = mocker.MagicMock()
    mock_sm.get_authenticated_session.side_effect = CircuitBreakerError("熔斷已啟動")

    crawler = PaperCrawler(session_manager=mock_sm)

    with pytest.raises(CircuitBreakerError) as exc_info:
        crawler.fetch_machine_stock(uno=91)

    assert "熔斷已啟動" in str(exc_info.value)

