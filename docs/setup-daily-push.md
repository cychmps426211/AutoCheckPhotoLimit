# 工作日定時推播預設底片存量查詢設定教學 (Scheduled Daily Push Setup Guide)

本文件提供「工作日定時推播預設底片存量查詢」功能的完整架構說明、安全金鑰設定與外部排程平台（以 cron-job.org 為例）設定步驟。

---

## 1. 架構概述與零警報靜默節流 (Zero-Report Suppression)

### 背景與設計理念
現場維修師於週一至週五早晨 08:00 開始日常巡檢。本功能透過外部定時排程服務自動觸發系統查詢預設維修師（91）與協同機台之底片存量，並在發現低存量機台時主動透過 Line 發送推播警報。

依據 [ADR-0009](adr/0009-scheduled-push-with-zero-alert-suppression.md) 與 `CONTEXT.md`：
- **安全金鑰防護**：端點 `/tasks/daily-push` 受 `PUSH_TASK_TOKEN` 安全保護，防止未授權網路爬蟲惡意觸發或耗損配額。
- **全體好友廣播 (Broadcast API)**：推播使用 Line `MessagingApi.broadcast()` 發送，直接推播至現場維修師私聊室，無需在系統中維護個人 Line User ID。
- **零警報靜默節流 (Zero-Report Suppression)**：若所有機台存量皆充足（剩餘張數全部 `> 20` 張），系統**完全不呼叫 Line API**，回傳 `action: "suppressed"`，確保每月 200 則免費 Push 配額零浪費。
- **離線 OCR 自動重登**：後台 Session 過期時自動辨識驗證碼並重新登入；遇連續登入失敗則啟動熔斷保護並回傳 HTTP 503。

### 執行流程圖

```mermaid
flowchart TD
    Cron["外部定時排程 (cron-job.org)<br>週一至週五 08:00 (UTC+8)"] -->|POST /tasks/daily-push<br>Header: X-Task-Token| API["FastAPI 端點 (/tasks/daily-push)"]
    API -->|金鑰驗證未通過| Ret401["回傳 HTTP 401 Unauthorized"]
    API -->|金鑰驗證通過| Query["執行預設底片存量查詢<br>(uno=91, s=0, threshold=20, 協同機台)"]
    Query -->|熔斷保護啟動| Ret503["優雅降級回傳 HTTP 503"]
    Query -->|查詢成功| Check{"是否有警報機台？<br>(剩餘張數 <= 20)"}
    Check -->|無 (count=0)| Suppress["零警報靜默節流 (Zero-Report Suppression)<br>不調用 Line API<br>回傳 action: 'suppressed'"]
    Check -->|有 (count > 0)| Format["依緊急程度排序格式化 (ADR-0008)"]
    Format --> Broadcast["Line MessagingApi.broadcast() 發送廣播"]
    Broadcast --> Ret200["記錄審計日誌<br>回傳 action: 'broadcast_sent'"]
```

---

## 2. 環境變數設定 (`PUSH_TASK_TOKEN`)

### 產生高強度安全金鑰
建議使用終端機產生 32 位元組以上的隨機字串：

```bash
# 使用 Python 產生
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 或使用 OpenSSL
openssl rand -hex 24
```

### 設定到 Render 雲端平台
1. 登入 [Render Dashboard](https://dashboard.render.com/)。
2. 進入您的 `autocheckphotolimit` Web Service。
3. 點選左側導覽列的 **Environment**。
4. 點選 **Add Environment Variable**：
   - **Key**: `PUSH_TASK_TOKEN`
   - **Value**: 填入剛剛產生的安全金鑰字串（例如 `a1b2c3d4e5f6...`）
5. 點擊 **Save Changes**。Render 將自動重新部署使變數生效。

### 本地開發環境 (.env)
若在本地測試，請在 `.env` 中加入：
```ini
PUSH_TASK_TOKEN=your_secure_task_token_here
```

---

## 3. 外部定時排程設定 (cron-job.org)

Render 免費方案服務適合搭配外部定時排程。以下以免費的 [cron-job.org](https://cron-job.org/) 為例進行設定：

### 建立 Cronjob 步驟

1. 登入 [cron-job.org](https://cron-job.org/) 控制台。
2. 點擊 **Create Cronjob**。
3. 填寫基本資料：
   - **Title**: `AutoCheckPhotoLimit Daily Push`
   - **URL**: `https://<您的-render-網址>.onrender.com/tasks/daily-push`
4. 設定執行頻率與時間 (**Schedule**)：
   - **Execution schedule**: 選擇 `User-defined (Cron syntax)` 或自訂頻率。
   - **時區 (Timezone)**: 選擇 `Asia/Taipei (UTC+08:00)`。
   - **執行時間**: 每週一、二、三、四、五的早晨 `08:00`。
   - **Cron 表示式**:
     - 若排程時區為 `Asia/Taipei`：`0 8 * * 1-5`
     - 若排程時區為 `UTC`：`0 0 * * 1-5`（UTC 00:00 等於台灣時間 08:00）
5. 設定 HTTP 請求與金鑰 (**Request details / Advanced**)：
   - **Request method**: 選擇 `POST`（亦支援 `GET`）。
   - **Headers**：新增以下 Header：
     - **Name**: `X-Task-Token`
     - **Value**: `<您所設定的 PUSH_TASK_TOKEN>`
   > [!TIP]
   > 若您使用的排程平台不支援設定客製化 HTTP Headers，可直接在 URL 加上 Query 參數替代：  
   > `https://<您的-render-網址>.onrender.com/tasks/daily-push?token=<您所設定的 PUSH_TASK_TOKEN>`
6. 點擊 **Create** 儲存排程。

---

## 4. 驗證與測試

### 手動觸發測試
您可以在本地或透過命令列工具發送請求驗證金鑰與端點：

```bash
# 使用 curl 測試 (透過 Header)
curl -X POST "https://<您的-render-網址>.onrender.com/tasks/daily-push" \
     -H "X-Task-Token: <您的-PUSH_TASK_TOKEN>"

# 或透過 URL Query 參數測試 (適用於瀏覽器或簡易排程器)
curl -X GET "https://<您的-render-網址>.onrender.com/tasks/daily-push?token=<您的-PUSH_TASK_TOKEN>"
```

### 預期響應格式

#### 情境 A：所有機台存量充足（零警報靜默節流生效）
```json
{
  "status": "ok",
  "action": "suppressed",
  "count": 0
}
```
*說明：未調用 Line API，不扣除任何推播額度。*

#### 情境 B：發現剩餘張數 <= 20 張之機台（已發送廣播）
```json
{
  "status": "ok",
  "action": "broadcast_sent",
  "count": 2
}
```
*說明：已將排版後的警報清單透過 Line 廣播發送至全體好友（維修師私聊室）。*

#### 情境 C：金鑰未附帶或不符合
```json
{
  "detail": "Invalid or missing task token"
}
```
*(HTTP 401 Unauthorized)*

#### 情境 D：後台登入失敗觸發熔斷保護
```json
{
  "status": "error",
  "message": "Circuit breaker open"
}
```
*(HTTP 503 Service Unavailable)*

---

## 5. 每月 200 則免費配額管理與日誌稽核

1. **免費額度評估**：
   - Line 官方帳號免費方案每月提供 **200 則免費 Push/Broadcast 額度**。
   - 每月約有 20~22 個工作日，即使每天皆有警報需要推播，一個月最多僅扣 20~22 則（若有 2 位維修師好友，廣播每次發送扣 2 則，整月最多消耗 44 則），遠低於 200 則上限。
   - 搭配**零警報靜默節流**，機台底片充足時完全不發送，實際消耗預估每月僅約 10~25 則。
2. **日誌稽核**：
   - 每次執行排程任務，伺服器日誌均會記錄時間戳記、機台計數與動作標籤（例如 `action=broadcast_sent, count=2` 或 `action=suppressed, count=0`）。
   - 可以在 Render 控制台的 **Logs** 分頁搜尋 `定時推播任務` 進行對帳。
3. **Line 後台即時查驗**：
   - 可隨時登入 [LINE Official Account Manager](https://manager.line.biz/)，於 **分析 (Analytics)** -> **訊息 (Messages)** 中查看當月已使用則數與剩餘配額。
