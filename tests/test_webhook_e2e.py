import pytest
from fastapi.testclient import TestClient
from src.main import app, process_user_text
from src.bot.message_builder import MachineStock


client = TestClient(app)


def test_health_check():
    """驗證 /health 基礎健康檢查端點 (Acceptance criteria)"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


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
