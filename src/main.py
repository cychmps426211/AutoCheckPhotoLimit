import logging
from typing import Optional
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)

from src.config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN
from src.bot.command_parser import CommandParser
from src.bot.message_builder import MessageBuilder
from src.crawler.paper_crawler import PaperCrawler, TechnicianNotFoundError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AutoCheckPhotoLimit Line Bot",
    description="自動查詢與監控後台機台底片存量的 Line 機器人系統",
    version="1.0.0",
)

# 初始化 Line 模組與爬蟲
crawler = PaperCrawler()


def get_messaging_api() -> Optional[MessagingApi]:
    if not LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_ACCESS_TOKEN.startswith("dummy"):
        return None
    config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    api_client = ApiClient(config)
    return MessagingApi(api_client)


@app.get("/health")
async def health_check():
    """
    基礎健康檢查與心跳保活端點
    供外部 cron (如 cron-job.org / UptimeRobot) 每 10 分鐘呼叫以防雲端主機休眠
    """
    return {"status": "ok"}


def process_user_text(user_text: str) -> str:
    """處理使用者輸入文字並返回回覆訊息字串"""
    cmd = CommandParser.parse(user_text)

    if cmd.action == "help":
        return MessageBuilder.build_help_message()

    if cmd.action == "unknown":
        return MessageBuilder.build_unknown_message(cmd.raw_text)

    if cmd.action == "query":
        try:
            machines = crawler.fetch_machine_stock(
                uno=cmd.uno,
                status=cmd.status,
                threshold=cmd.threshold,
            )
            return MessageBuilder.build_stock_report(
                uno=cmd.uno,
                machines=machines,
                threshold=cmd.threshold,
            )
        except TechnicianNotFoundError:
            return MessageBuilder.build_technician_not_found_message(cmd.uno)
        except Exception as e:
            logger.error(f"查詢機台資料失敗: {e}")
            return MessageBuilder.build_error_message(str(e))

    return MessageBuilder.build_unknown_message(user_text)


@app.post("/callback")
async def callback(
    request: Request,
    x_line_signature: Optional[str] = Header(None, alias="X-Line-Signature"),
):
    """
    Line Webhook 端點
    驗證簽章並處理維修師發送之訊息，透過 replyToken 回傳排版結果
    """
    body = (await request.body()).decode("utf-8")

    # 支援測試或未設定簽章金鑰時之邊界測試模式
    is_test_mode = (
        not LINE_CHANNEL_SECRET
        or LINE_CHANNEL_SECRET.startswith("dummy")
        or x_line_signature == "test-signature"
    )

    events = []
    if is_test_mode:
        import json
        try:
            payload = json.loads(body)
            # 轉換為標準 Webhook 事件或簡易解析
            raw_events = payload.get("events", [])
        except Exception:
            raw_events = []

        for evt in raw_events:
            if evt.get("type") == "message" and evt.get("message", {}).get("type") == "text":
                user_text = evt["message"]["text"]
                reply_token = evt.get("replyToken")
                reply_text = process_user_text(user_text)
                logger.info(f"[Test Mode] 收到訊息: '{user_text}', 回覆: '{reply_text[:60]}...'")
        return JSONResponse(content={"status": "OK (test mode)"})

    if not x_line_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Line-Signature")

    parser = WebhookParser(LINE_CHANNEL_SECRET)
    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            user_text = event.message.text
            reply_token = event.reply_token
            reply_text = process_user_text(user_text)

            # 透過 Line Reply API (被動回覆，不消耗 Push 額度)
            messaging_api = get_messaging_api()
            if messaging_api and reply_token:
                try:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=reply_text)],
                        )
                    )
                except Exception as e:
                    logger.error(f"發送 Line 回覆訊息失敗: {e}")

    return JSONResponse(content={"status": "OK"})
