# Spec: 自動查詢機台底片存量 Line 機器人 (AutoCheckPhotoLimit)

## Problem Statement

現場維修師負責維護 50 台以上的拍貼或列印機台。目前要掌握哪些機台即將耗盡底片，必須手動透過瀏覽器登入後台管理系統（`dl02.seiwainc.com.tw`），手動輸入 4 位數字圖形驗證碼，再導覽至底片存量頁面進行篩選與肉眼查找。

這個流程在手機上操作繁瑣緩慢，且缺乏快速自訂剩餘張數門檻（例如查詢小於 20 張）與緊急程度排序的功能，導致維修師難以在第一時間迅速掌握需要優先補紙的機台。

## Solution

建立一個全免費運行的 Line 機器人系統。維修師只需在 Line 聊天室中發送「底片」或帶有門檻的指令（如「底片 < 20」），機器人便會透過快取之認證會話（Session）或自動調用開源 OCR（`ddddocr`）登入後台，抓取特定維修師負責之機台存量，依剩餘張數由少至多（緊急排序）過濾整理，並透過 Line 回覆令牌（Reply Token）即時回傳清晰的警報清單。

## User Stories

1. As a 維修師, I want to send "檢查底片" or "底片" to the Line Bot, so that I can immediately see all machines assigned to the 預設維修師 (91) that are currently 接近底限.
2. As a 維修師, I want the bot to sort the machines by 剩餘張數 in ascending order (緊急排序), so that I can identify which machines need urgent replenishment at a glance.
3. As a 維修師, I want to specify a 剩餘張數門檻 like "底片 < 20", so that I can filter machines that have 20 or fewer remaining sheets regardless of backend status category.
4. As a 維修師, I want to query other 維修師's machines by sending "底片 師 88" or "底片維修師 88", so that I can check a colleague's machine stock status when providing backup or cross-shift coverage.
5. As a 維修師, I want to combine technician ID and sheet threshold in a single command like "底片 88 < 20", so that I can flexibly check low-stock machines for any technician.
6. As a 維修師, I want to see a reassuring confirmation message when no machines are below the threshold, so that I know all machines are operating with sufficient film stock.
7. As a 維修師, I want to send "說明" or "底片 說明", so that I can see the list of supported command formats and examples if I forget the syntax.
8. As a 維修師, I want query responses to arrive within 1~2 seconds, so that I do not experience delays while working on-site.
9. As a 維修師, I want the system to display the 機台名稱/編號 and 剩餘張數 clearly for each machine, so that I have the exact identifying information needed for restocking.
10. As a 維修師, I want the system to handle unexpected or unrecognized command inputs gracefully with a helpful usage hint, so that I know how to correct my query.
11. As a system maintainer, I want the bot to automatically recognize the 4-digit 驗證碼 using an open-source offline OCR engine (ddddocr), so that login succeeds without third-party API subscription costs.
12. As a system maintainer, I want the system to cache and reuse the authenticated session (`PHPSESSID`), so that the bot does not need to perform OCR and login on every user query.
13. As a system maintainer, I want the session manager to automatically re-login upon receiving a session expiry response (302 redirect), so that subsequent queries recover seamlessly without manual intervention.
14. As a system maintainer, I want the system to reply exclusively via Line's 回覆令牌 (Reply Token), so that the bot remains 100% free and never exhausts the 200 monthly push message quota.
15. As a system maintainer, I want a lightweight `/health` endpoint to serve as a keep-alive target, so that external cron pings prevent cloud host spin-down and keep the backend session warm.
16. As a system maintainer, I want the system to retry failed logins up to 3 times before returning an error, so that transient network glitches or occasional OCR misreads do not break the user experience.
17. As a system maintainer, I want sensitive credentials (account, password, Line channel secret, Line access token) stored in environment variables, so that private keys and passwords are never committed to version control.

## Implementation Decisions

- **Domain Model Alignment**: The system strictly follows domain terminology defined in `CONTEXT.md` (維修師, 機台, 底片存量, 底片狀態類別, 剩餘張數, 驗證碼, 預設維修師, 剩餘張數門檻, 回覆令牌, 緊急排序).
- **Captcha OCR & Session Management**:
  - Offline image classification using `ddddocr` directly on image byte streams. No image files are saved to disk or processed by external vision APIs.
  - Persistent `PHPSESSID` session caching. On incoming query, reuse existing session cookie. If response is a 302 redirect to `500.html` (unauthenticated), trigger automated login retry loop (maximum 3 attempts).
- **Command Grammar & Parsing**:
  - Regex-based parser supporting:
    - Default query: `^(?:檢查底片|底片)$` -> `uno=91`, status=`2` (接近底限).
    - Threshold query: `^(?:底片|檢查底片)\s*(?:<|小於|門檻)\s*(\d+)$` -> `uno=91`, threshold=`N`, status=`0`.
    - Technician query: `^(?:底片|檢查底片)\s*(?:師|維修師)\s*(\d+)$` -> `uno=N`, status=`2`.
    - Combined query: `^(?:底片|檢查底片)\s*(\d+)\s*(?:<|小於|門檻)\s*(\d+)$` -> `uno=N1`, threshold=`N2`, status=`0`.
    - Help query: `^(?:底片\s*說明|說明|help)$`.
- **Urgency Sorting & Filtering**:
  - Extracted machine items are filtered by `remaining_sheets <= threshold` (when threshold is specified).
  - All filtered results are sorted in ascending order by `remaining_sheets` (lowest sheets first).
- **Message Response Architecture**:
  - Incoming requests processed via FastAPI webhook endpoint.
  - Responses sent strictly via Line Messaging API `reply_message` using event `replyToken`. No push messages are used.
  - Keep-alive heartbeat endpoint (`/health`) exposed to accept external 10-minute cron pings, preventing hosting spin-down and refreshing backend session.

## Testing Decisions

- **What makes a good test**: Tests must verify observable external behavior from the boundary of the system, without asserting on private state, specific variable names, or intermediate helper functions.
- **Proposed Highest Testing Seam**:
  - **The Line Webhook Boundary Seam**: Testing the system by simulating an incoming Line Webhook event (HTTP POST with JSON payload containing user text) and verifying the outgoing HTTP payload sent to Line Reply API.
  - Dependencies at the boundary (Seiwa backend HTTP endpoints and Line Reply API endpoint) are mocked using fixtures, allowing the entire pipeline (command parsing, session handling, HTML parsing, urgency sorting, message rendering) to execute as a cohesive unit.
- **Secondary Integration Seam**:
  - **The Paper Crawler Seam**: Verifying table parsing, threshold filtering, and urgency sorting directly against static HTML fixtures from `PaperMachine.php`.

## Out of Scope

- Multi-tenant user permission management or role-based access control.
- Machine configuration editing, dispatch assignment, or write operations to the Seiwa backend.
- Rich Menu / Flex Message carousel UI (plain formatted text messages are used for minimal payload and universal device compatibility).
- Proactive background alerts / push notifications (due to Line free tier limits).

## Further Notes

- Target deployment: Render Free Tier with cron-job.org keep-alive ping, fully portable to self-hosted macOS/NAS Docker container in the future.
