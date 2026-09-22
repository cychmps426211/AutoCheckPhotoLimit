import pytest
from fastapi.testclient import TestClient
from src.main import app, process_user_text, crawler
from src.bot.message_builder import MachineStock


client = TestClient(app)


@pytest.mark.parametrize(
    "session_status",
    ["active", "refreshed", "circuit_breaker_open", "error"],
)
def test_health_check_various_session_states(mocker, session_status):
    """驗證 /health 端點在不同會話心跳保活狀態下均維持 HTTP 200 並正確回傳 session 狀態"""
    mocker.patch.object(crawler, "keep_alive", return_value=session_status)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "session": session_status}




def test_process_user_text_default_query(mocker):
    """驗證維修師發送「底片」時，查詢預設維修師 91 之機台 (Acceptance criteria)"""
    mock_machines = [
        MachineStock(machine_id="M1", machine_name="台北店", remaining_sheets=3),
        MachineStock(machine_id="M2", machine_name="高雄店", remaining_sheets=12),
    ]
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=mock_machines)

    reply = process_user_text("底片")
    assert "維修師 91 機台底片存量警報" in reply
    assert "台北店 (M1)" in reply
    assert "剩餘張數：3 張" in reply
    assert "高雄店 (M2)" in reply
    assert "剩餘張數：12 張" in reply


def test_process_user_text_empty_machines(mocker):
    """驗證機台存量充足時的友善回覆"""
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=[])

    reply = process_user_text("檢查底片")
    assert "維修師 91 目前所有機台底片存量充足" in reply


def test_webhook_e2e_line_reply(mocker):
    """
    端對端 Webhook 邊界測試 (The Webhook Boundary Seam)：
    驗證從收到 Line Webhook 事件到呼叫 Line Reply API 的完整流程
    """
    # 模擬爬蟲回傳
    mock_machines = [
        MachineStock(machine_id="TW01", machine_name="站前店", remaining_sheets=6),
    ]
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=mock_machines)

    # 模擬 Line Messaging API
    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    # 模擬 WebhookParser 回傳 MessageEvent
    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "test-reply-token-123"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "test-reply-token-123"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    # 驗證 Line Reply API 被正確調用，且 replyToken 一致
    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "test-reply-token-123"
    assert len(call_args.messages) == 1
    assert "站前店 (TW01)" in call_args.messages[0].text
    assert "剩餘張數：6 張" in call_args.messages[0].text


def test_process_user_text_threshold_query(mocker):
    """驗證維修師發送帶門檻指令（如「底片 20張」）時，正確傳遞 status=0 與 threshold=20"""
    mock_fetch = mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        return_value=[
            MachineStock(machine_id="M1", machine_name="台北店", remaining_sheets=8),
            MachineStock(machine_id="M2", machine_name="高雄店", remaining_sheets=15),
        ],
    )

    reply = process_user_text("底片 20張")
    mock_fetch.assert_called_once_with(uno=91, status=0, threshold=20)
    assert "維修師 91 機台底片存量警報" in reply
    assert "剩餘張數 <= 20 張" in reply
    assert "台北店 (M1)" in reply
    assert "剩餘張數：8 張" in reply
    assert "高雄店 (M2)" in reply
    assert "剩餘張數：15 張" in reply


def test_process_user_text_threshold_empty(mocker):
    """驗證門檻過濾若無任何機台低於門檻，回傳安心提示（Acceptance criteria）"""
    mock_fetch = mocker.patch("src.main.crawler.fetch_machine_stock", return_value=[])

    reply = process_user_text("底片門檻 10")
    mock_fetch.assert_called_once_with(uno=91, status=0, threshold=10)
    assert "維修師 91 目前負責之機台底片皆充足" in reply
    assert "小於等於 10 張" in reply


def test_webhook_e2e_threshold_query(mocker):
    """端對端 Webhook 測試：門檻過濾查詢（底片 < 15）成功經由 Line Reply 回傳"""
    mock_machines = [
        MachineStock(machine_id="TW09", machine_name="新竹巨城", remaining_sheets=11),
    ]
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=mock_machines)

    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent
    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-threshold-query"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片 < 15"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-threshold-query"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-threshold-query"
    assert len(call_args.messages) == 1
    assert "新竹巨城 (TW09)" in call_args.messages[0].text
    assert "剩餘張數 <= 15 張" in call_args.messages[0].text


def test_webhook_e2e_threshold_empty(mocker):
    """端對端 Webhook 測試：門檻過濾 0 台符合（存量皆充足）安心提示經由 Line Reply 回傳"""
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=[])

    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent
    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-threshold-empty"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片 < 10"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-threshold-empty"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-threshold-empty"
    assert len(call_args.messages) == 1
    assert "維修師 91 目前負責之機台底片皆充足" in call_args.messages[0].text
    assert "小於等於 10 張" in call_args.messages[0].text


def test_process_user_text_technician_query(mocker):
    """驗證跨維修師查詢（「底片 師 88」）傳遞 uno=88, status=2, threshold=None"""
    mock_fetch = mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        return_value=[
            MachineStock(machine_id="M88", machine_name="高雄草衙道", remaining_sheets=9),
        ],
    )

    reply = process_user_text("底片 師 88")
    mock_fetch.assert_called_once_with(uno=88, status=2, threshold=None)
    assert "維修師 88 機台底片存量警報" in reply
    assert "高雄草衙道 (M88)" in reply
    assert "剩餘張數：9 張" in reply


def test_process_user_text_combined_query(mocker):
    """驗證複合查詢（「底片 88 < 20」）傳遞 uno=88, status=0, threshold=20"""
    mock_fetch = mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        return_value=[
            MachineStock(machine_id="M88", machine_name="高雄草衙道", remaining_sheets=14),
        ],
    )

    reply = process_user_text("底片 88 < 20")
    mock_fetch.assert_called_once_with(uno=88, status=0, threshold=20)
    assert "維修師 88 機台底片存量警報" in reply
    assert "剩餘張數 <= 20 張" in reply
    assert "高雄草衙道 (M88)" in reply
    assert "剩餘張數：14 張" in reply


def test_process_user_text_technician_not_found(mocker):
    """驗證查無該維修師負責之機台時回傳友善提示"""
    from src.crawler.paper_crawler import TechnicianNotFoundError

    mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        side_effect=TechnicianNotFoundError(88),
    )

    reply = process_user_text("底片 師 88")
    assert "查無維修師 88 負責之機台資料" in reply
    assert "請確認維修師編號是否正確" in reply


def test_webhook_e2e_cross_technician_query(mocker):
    """端對端 Webhook 測試：跨維修師查詢（底片 師 88）成功經由 Line Reply 回傳"""
    mock_machines = [
        MachineStock(machine_id="TW88", machine_name="台南三井", remaining_sheets=4),
    ]
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=mock_machines)

    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-cross-tech"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片 師 88"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-cross-tech"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-cross-tech"
    assert "維修師 88 機台底片存量警報" in call_args.messages[0].text
    assert "台南三井 (TW88)" in call_args.messages[0].text


def test_webhook_e2e_combined_query(mocker):
    """端對端 Webhook 測試：複合查詢（底片 88門檻 25）成功經由 Line Reply 回傳"""
    mock_machines = [
        MachineStock(machine_id="TW88", machine_name="台南三井", remaining_sheets=18),
    ]
    mocker.patch("src.main.crawler.fetch_machine_stock", return_value=mock_machines)

    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-comb-query"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片 88門檻 25"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-comb-query"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-comb-query"
    assert "維修師 88 機台底片存量警報" in call_args.messages[0].text
    assert "剩餘張數 <= 25 張" in call_args.messages[0].text
    assert "台南三井 (TW88)" in call_args.messages[0].text


def test_webhook_e2e_technician_not_found(mocker):
    """端對端 Webhook 測試：查無維修師提示成功經由 Line Reply 回傳"""
    from src.crawler.paper_crawler import TechnicianNotFoundError

    mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        side_effect=TechnicianNotFoundError(88),
    )

    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-not-found"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片 88 < 20"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-not-found"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-not-found"
    assert "查無維修師 88 負責之機台資料" in call_args.messages[0].text
    assert "請確認維修師編號是否正確" in call_args.messages[0].text


def test_process_user_text_help():
    """驗證發送「說明」與「底片 說明」時回傳指令教學說明"""
    reply1 = process_user_text("說明")
    assert "機台底片存量查詢指令說明" in reply1
    assert "預設查詢" in reply1
    assert "門檻查詢" in reply1
    assert "指定維修師查詢" in reply1
    assert "複合查詢" in reply1

    reply2 = process_user_text("底片 說明")
    assert "機台底片存量查詢指令說明" in reply2


def test_webhook_e2e_help_command(mocker):
    """端對端 Webhook 測試：維修師發送「說明」經由 Line Reply 收到完整教學訊息"""
    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-help"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "說明"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-help"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-help"
    assert "機台底片存量查詢指令說明" in call_args.messages[0].text
    assert "底片" in call_args.messages[0].text
    assert "底片 < 20" in call_args.messages[0].text


def test_process_user_text_unknown_command():
    """驗證發送無法辨識之輸入時，給予簡要提示並引導輸入「說明」"""
    reply = process_user_text("明天有空嗎")
    assert "無法辨識指令：「明天有空嗎」" in reply
    assert "您可以直接輸入「底片」查詢預設維修師 (91) 機台，或輸入「說明」查看所有指令格式。" in reply


def test_webhook_e2e_unknown_command(mocker):
    """端對端 Webhook 測試：無法辨識之輸入經由 Line Reply 回傳提示並引導輸入「說明」"""
    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-unknown"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "哈囉"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-unknown"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-unknown"
    assert "無法辨識指令：「哈囉」" in call_args.messages[0].text
    assert "輸入「說明」" in call_args.messages[0].text


def test_process_user_text_circuit_breaker(mocker):
    """驗證後台登入熔斷啟動時，process_user_text 回傳熔斷保護警報文字"""
    from src.auth.circuit_breaker import CircuitBreakerError

    mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        side_effect=CircuitBreakerError("熔斷中斷"),
    )

    reply = process_user_text("底片")
    assert "熔斷保護已啟動" in reply
    assert "連續失敗達 3 次" in reply
    assert "暫停重複登入重試" in reply


def test_webhook_e2e_circuit_breaker(mocker):
    """端對端 Webhook 測試：登入連續失敗觸發熔斷時，Line Reply 回傳警報文字且不無限重試"""
    from src.auth.circuit_breaker import CircuitBreakerError

    mocker.patch(
        "src.main.crawler.fetch_machine_stock",
        side_effect=CircuitBreakerError("熔斷中斷"),
    )

    mock_api = mocker.MagicMock()
    mocker.patch("src.main.get_messaging_api", return_value=mock_api)
    mocker.patch("src.main.LINE_CHANNEL_SECRET", "mock_secret")

    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    mock_event = mocker.MagicMock(spec=MessageEvent)
    mock_event.reply_token = "reply-token-circuit-breaker"
    mock_event.message = mocker.MagicMock(spec=TextMessageContent)
    mock_event.message.text = "底片"

    mocker.patch("linebot.v3.WebhookParser.parse", return_value=[mock_event])

    headers = {"X-Line-Signature": "valid-signature"}
    payload = {"events": [{"type": "message", "replyToken": "reply-token-circuit-breaker"}]}

    resp = client.post("/callback", json=payload, headers=headers)
    assert resp.status_code == 200

    assert mock_api.reply_message.called
    call_args = mock_api.reply_message.call_args[0][0]
    assert call_args.reply_token == "reply-token-circuit-breaker"
    assert "熔斷保護已啟動" in call_args.messages[0].text
    assert "連續失敗達 3 次" in call_args.messages[0].text
    assert "暫停重複登入重試" in call_args.messages[0].text


