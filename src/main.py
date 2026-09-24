import logging
import secrets
from typing import Optional
from fastapi import FastAPI, Request, Header, HTTPException, status, Depends, Query
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
    BroadcastRequest,
)

from src.config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    PORT,
    DUTY_AREA_NO,
    DUTY_AREA_NAME,
    PUSH_TASK_TOKEN,
    DEFAULT_QUERY_STATUS,
    DEFAULT_QUERY_THRESHOLD,
)
from src.auth.circuit_breaker import CircuitBreakerError
from src.bot.command_parser import CommandParser
from src.bot.message_builder import MessageBuilder
from src.crawler.paper_crawler import PaperCrawler, TechnicianNotFoundError
from src.crawler.schedule_crawler import ScheduleCrawler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AutoCheckPhotoLimit Line Bot",
    description="自動查詢與監控後台機台底片存量與行程的 Line 機器人系統",
    version="1.0.0",
)

# 初始化 Line 模組與爬蟲
crawler = PaperCrawler()
schedule_crawler = ScheduleCrawler(session_manager=crawler.session_manager)



def get_messaging_api() -> Optional[MessagingApi]:
    if not LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_ACCESS_TOKEN.startswith("dummy"):
        return None
    config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    api_client = ApiClient(config)
    return MessagingApi(api_client)


@app.get("/health")
def health_check():
    """
    健康檢查與心跳保活端點
    供外部 cron (如 cron-job.org / UptimeRobot) 每 10 分鐘呼叫以防雲端主機休眠，
    並對後台管理系統發送輕量探測以保持 PHPSESSID 活躍（或自動刷新）。
    使用同步 def 讓 FastAPI 自動指派至外部線程池執行，避免阻塞主事件迴圈。
    """
    session_status = crawler.keep_alive()
    return {"status": "ok", "session": session_status}


def verify_task_token(
    x_task_token: Optional[str] = Header(None, alias="X-Task-Token"),
    token: Optional[str] = Query(None),
) -> None:
    """
    驗證定時任務金鑰，支援 HTTP Header (X-Task-Token) 與 URL 查詢參數 (?token=)。
    未配置金鑰或金鑰不符時一律拒絕並回傳 HTTP 401 Unauthorized。
    """
    configured_token = PUSH_TASK_TOKEN
    if not configured_token:
        logger.warning("定時任務金鑰驗證失敗: 伺服器未配置 PUSH_TASK_TOKEN 環境變數")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Task token is not configured on server",
        )
    token_valid = (
        (x_task_token is not None and secrets.compare_digest(x_task_token, configured_token))
        or (token is not None and secrets.compare_digest(token, configured_token))
    )
    if not token_valid:
        logger.warning("定時任務金鑰驗證失敗: 提供的金鑰無效或未附帶金鑰")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing task token",
        )


@app.api_route(
    "/tasks/daily-push",
    methods=["GET", "POST"],
    dependencies=[Depends(verify_task_token)],
)
def daily_push_task():
    """
    工作日定時推播任務端點
    由外部排程服務（如 cron-job.org）於週一至週五 08:00 觸發
    支援 POST 與相容外部排程之 GET 請求，需通過金鑰認證
    執行南區值班底片殘量查詢 (area=46, s=0)
    """
    logger.info(
        "定時推播任務端點 (/tasks/daily-push) 驗證通過，開始執行南區值班底片殘量查詢 (area=%s, s=%s)",
        DUTY_AREA_NO,
        DEFAULT_QUERY_STATUS,
    )
    try:
        machines = crawler.fetch_machine_stock(
            uno=0,
            status=DEFAULT_QUERY_STATUS,
            threshold=DEFAULT_QUERY_THRESHOLD,
            area=DUTY_AREA_NO,
            include_collaborative=False,
        )
    except CircuitBreakerError:
        logger.warning("定時推播任務: 觸發熔斷保護 (Circuit breaker open)，優雅回傳 503")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "message": "Circuit breaker open"},
        )

    if not machines:
        logger.info("定時推播任務: 所有機台底片存量充足 (count=0)，啟動零警報靜默節流 (action=suppressed, count=0)")
        return {"status": "ok", "action": "suppressed", "count": 0}

    # 存在需要補充底片之警報機台：排版並透過 Line MessagingApi.broadcast() 推播
    report_text = MessageBuilder.build_duty_stock_report(
        area_name=DUTY_AREA_NAME,
        machines=machines,
        threshold=DEFAULT_QUERY_THRESHOLD,
    )

    messaging_api = get_messaging_api()
    if not messaging_api:
        logger.error(
            f"定時推播任務: Line Messaging API 未配置 (LINE_CHANNEL_ACCESS_TOKEN 未設定或無效) (action=broadcast_failed, count={len(machines)})"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Line Messaging API client not configured"},
        )

    try:
        messaging_api.broadcast(
            BroadcastRequest(messages=[TextMessage(text=report_text)])
        )
        logger.info(
            f"定時推播任務: 成功發送 Line 全體好友廣播，警報機台數量: {len(machines)} (action=broadcast_sent, count={len(machines)})"
        )
    except Exception as e:
        logger.error(
            f"定時推播任務: 發送 Line 全體好友廣播失敗: {e} (action=broadcast_failed, count={len(machines)})"
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"status": "error", "message": f"Failed to send Line broadcast: {str(e)}"},
        )

    return {"status": "ok", "action": "broadcast_sent", "count": len(machines)}




def process_user_text(user_text: str) -> str:
    """處理維修師輸入文字並返回回覆訊息字串"""
    cmd = CommandParser.parse(user_text)

    if cmd.action == "help":
        return MessageBuilder.build_help_message()

    if cmd.action == "unknown":
        return MessageBuilder.build_unknown_message(cmd.raw_text)

    if cmd.action == "duty_query":
        try:
            machines = crawler.fetch_machine_stock(
                uno=0,
                status=cmd.status,
                threshold=cmd.threshold,
                area=cmd.area,
                include_collaborative=False,
            )
            return MessageBuilder.build_duty_stock_report(
                area_name=DUTY_AREA_NAME,
                machines=machines,
                threshold=cmd.threshold,
            )
        except CircuitBreakerError:
            return MessageBuilder.build_circuit_breaker_message()
        except Exception as e:
            logger.error(f"查詢值班機台資料失敗: {e}")
            return MessageBuilder.build_error_message(str(e))

    if cmd.action == "schedule_query_invalid":
        return MessageBuilder.build_invalid_schedule_date_message(cmd.raw_text)

    if cmd.action == "schedule_query":
        try:
            items = schedule_crawler.fetch_schedule(
                uno=cmd.uno,
                target_date=cmd.target_date,
            )
            return MessageBuilder.build_schedule_report(
                uno=cmd.uno,
                target_date=cmd.target_date,
                items=items,
            )
        except CircuitBreakerError:
            return MessageBuilder.build_circuit_breaker_message()
        except Exception as e:
            logger.error(f"查詢行程資料失敗: {e}")
            return MessageBuilder.build_error_message(str(e))

    if cmd.action == "query":
        try:
            machines = crawler.fetch_machine_stock(
                uno=cmd.uno,
                status=cmd.status,
                threshold=cmd.threshold,
                include_collaborative=cmd.include_collaborative,
            )
            return MessageBuilder.build_stock_report(
                uno=cmd.uno,
                machines=machines,
                threshold=cmd.threshold,
            )
        except TechnicianNotFoundError:
            return MessageBuilder.build_technician_not_found_message(cmd.uno)
        except CircuitBreakerError:
            return MessageBuilder.build_circuit_breaker_message()
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
 
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=PORT, reload=False)
