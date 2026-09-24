# Spec: 工作日定時推播南區值班底片存量查詢 (Scheduled Daily Push)

## Problem Statement

現場維修師每天早晨（週一至週五 08:00）開始日常巡檢前，需了解南區責任區域內機台的底片存量狀況。目前系統雖支援透過 Line 聊天室發送「值班」指令查詢，但維修師常因出勤匆忙而遺漏手動查詢，導致無法在出發前及早獲悉瀕臨缺紙的機台。

此外，Line 官方帳號免費方案每月僅有 200 則主動推播（Push Message）額度。若不加節制地每天無差別推播，或是推播至多人大群組，極易超出免費用量上限；但若所有機台存量充足時依然每天發送通知，亦會造成不必要的訊息疲勞與額度浪費。

## Solution

在系統中建立一個安全的定時推播端點，配合外部定時排程服務（如 cron-job.org），在每週一至週五 08:00 自動觸發執行南區值班底片存量查詢（`area=46, s=0`）。

系統結合「零警報靜默節流（Zero-Report Suppression）」機制：若所有機台底片皆大於門檻（無剩餘張數 <= 20 張之機台），系統靜默不推播任何訊息，保護每月 200 則免費額度；僅在存在需補充底片之警報機台時，才透過 Line Broadcast API 將緊急排序且標記各機台責任維修師之值班存量清單發送至維修師的私聊室。端點實施安全金鑰驗證，防止未授權存取與額度消耗，並全面整合離線 OCR 自動重登防護。

## User Stories

1. As a 維修師, I want the system to automatically inspect machine film stocks every weekday morning at 08:00, so that I am notified of urgent replenishment needs before starting my daily maintenance rounds without needing to query manually.
2. As a 維修師, I want to receive the morning film stock alert directly in my 1-on-1 Line chat via broadcast, so that I can see the low-stock report conveniently without configuring personal user IDs or checking separate groups.
3. As a 維修師, I want low-stock machines in the morning push alert sorted by 剩餘張數 in ascending order (緊急排序), so that the most critical machines needing immediate replenishment appear at the very top.
4. As a 維修師, I want the scheduled query to cover the entire south duty area (`area=46, s=0`) and clearly display each machine's 負責維修師 (InCharge), so that my entire daily coverage scope across the team is monitored in a single consolidated alert.
5. As a 維修師, I want 異常機台 (such as known defective or test machines) automatically filtered out of the morning push alert, so that I am not distracted by false alarms.
6. As a 維修師, I want the system to remain silent and send no message when all machines have sufficient film stock (> 20 sheets), so that I am not bothered by redundant notifications on days when no action is needed.
7. As a 維修師, I want each alerted machine to clearly display its name, ID, remaining sheets, and urgency indicators (🔴/🟠/🟡), so that I can prioritize and navigate to the right location quickly.
8. As a 維修師, I want to continue using the Line bot for manual queries throughout the day via 回覆令牌, so that the scheduled push feature does not alter or disrupt on-demand checking habits.
9. As a system maintainer, I want the scheduled push endpoint protected by a secret task token, so that unauthorized public internet crawlers cannot trigger the job or exhaust the Line push quota.
10. As a system maintainer, I want the scheduled push endpoint to accept the secret task token via either an HTTP header (`X-Task-Token`) or a URL query parameter (`?token=`), so that any external cron scheduling provider can integrate flexibly.
11. As a system maintainer, I want requests missing the secret token or providing an invalid token rejected immediately with HTTP 401 Unauthorized, so that invalid requests consume minimal server resources and zero Line quota.
12. As a system maintainer, I want the push alert to utilize Line's Broadcast API, so that the message reaches all active technician friends simultaneously without maintaining user IDs in configuration files.
13. As a system maintainer, I want zero-alert suppression to strictly prevent push API calls when no machines meet the alert threshold, so that the system operates well within the 200 monthly free message quota.
14. As a system maintainer, I want the background crawler to automatically recover from expired backend sessions via offline OCR verification, so that scheduled executions at 08:00 succeed reliably without manual re-login.
15. As a system maintainer, I want the endpoint to handle circuit breaker trips gracefully and return an HTTP 503 response, so that persistent backend outages do not crash the service or produce corrupted push messages.
16. As a system maintainer, I want the scheduled push endpoint to return structured JSON describing the outcome (e.g. suppressed vs broadcast sent, with machine counts), so that external cron monitoring dashboards can easily verify execution health.
17. As a system maintainer, I want all scheduled push executions, suppressions, and delivery attempts logged with timestamps, so that auditing message volume against monthly Line quotas is straightforward.
18. As a system maintainer, I want the secret task token configurable via environment variables, so that production credentials remain decoupled from version control.
19. As a system maintainer, I want the scheduled push task to be idempotent per invocation, so that retrying a transient connection error behaves predictably.
20. As a system maintainer, I want the daily push feature to align strictly with ADR-0009 and the domain definitions in CONTEXT.md, so that system architecture and documentation remain completely coherent.

## Implementation Decisions

- **Domain Model & Architecture Alignment**:
  - Reopens and modifies the boundary of ADR-0002 via ADR-0009: push messages are strictly authorized only for the authenticated scheduled task, while user-interactive conversations remain 100% passive via Reply Tokens.
  - Formally introduces the `定時推播 (Scheduled Push)` domain term into the ubiquitous language in CONTEXT.md.
- **Task Endpoint Contract & Security**:
  - Exposes a dedicated task endpoint supporting HTTP POST (and optionally GET for constrained webhook schedulers).
  - Enforces mandatory token authentication via `X-Task-Token` request header or `token` query parameter, validated against an environment-configured secret token.
  - If the secret token is unconfigured or mismatched, the endpoint rejects the request with HTTP 401 Unauthorized.
- **Query & Filter Logic**:
  - Reuses the existing crawler service to perform a 南區值班存量查詢 (`uno=0`, `area=46`, `status=0`, `threshold=20`, `include_collaborative=False`).
  - Automatic filtering of 異常機台 and ascending urgency sorting (`remaining_sheets`) are preserved verbatim through existing domain logic.
- **Zero-Report Suppression Strategy**:
  - If the query returns 0 machines below or equal to the threshold (all machines have sufficient stock), the push dispatcher is bypassed completely.
  - The endpoint returns a successful JSON status indicating suppression (`action: "suppressed"`), consuming 0 Line push quota.
- **Line Broadcast Dispatcher**:
  - When alert machines are present, formats the report via the duty stock report message builder (`MessageBuilder.build_duty_stock_report`), displaying the area duty header and responsible technician for each machine.
  - Dispatches the report using the Line Messaging API's broadcast mechanism, reaching all added technician friends simultaneously.
- **Fault Tolerance & Session Resilience**:
  - Inherits the automatic session recovery mechanism: if the backend session is expired, the session manager performs in-memory captcha acquisition and offline OCR classification (`ddddocr`) before querying.
  - Honors circuit breaker state; if the circuit breaker is open, terminates immediately and returns an appropriate service-unavailable response.

## Testing Decisions

- **What makes a good test**: Tests must verify observable external behavior from the boundary of the system, asserting on HTTP responses, status codes, and external boundary invocations (Line API calls and backend crawler queries), without coupling to private internal state.
- **Primary Testing Seam**:
  - **The HTTP Task Boundary Seam**: Testing the system by simulating incoming HTTP requests to `/tasks/daily-push` via the test client and asserting on:
    1. Rejection of unauthenticated requests (HTTP 401).
    2. Successful suppression when machine stock is safe (HTTP 200, verifying the Line Broadcast API is NEVER called).
    3. Successful delivery when low-stock machines exist (HTTP 200, verifying the Line Broadcast API is called exactly once with properly formatted content).
    4. Proper error handling when the circuit breaker is tripped (HTTP 503).
  - External boundaries (Seiwa backend HTTP sessions and the Line Messaging API client) are mocked at the boundary layer, mirroring the prior art in existing webhook end-to-end tests.
- **Prior Art**:
  - Modeled after the existing webhook test suite (`test_webhook_e2e.py`) and keep-alive tests (`test_session_keepalive.py`), which exercise endpoints via FastAPI's TestClient while mocking external I/O.

## Out of Scope

- Native in-process cron scheduling (e.g. APScheduler / background threads) within the web service; scheduling remains delegated to external cron services to avoid hosting spin-down issues on Render.
- Calendar awareness for public holidays or make-up workdays (the trigger schedule runs on a standard Monday–Friday cadence).
- Per-user role filtering or dynamic subscription management (all official account friends receive the broadcast).
- Interactive push notifications with reply action buttons or rich carousel menus.

## Further Notes

- The external cron trigger should be scheduled at 08:00 UTC+8 (00:00 UTC) Monday through Friday.
- Line official account usage can be verified in real time via the LINE Official Account Manager console under Analytics > Messages.
