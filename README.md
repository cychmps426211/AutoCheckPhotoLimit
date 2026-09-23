# AutoCheckPhotoLimit Line 機器人

[![Tests](https://img.shields.io/badge/tests-106%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)]()
[![Free Tier](https://img.shields.io/badge/cost-100%25%20free-success.svg)]()

自動查詢與監控 Seiwa 後台機台底片存量的 Line 機器人系統。現場維修師僅需在 Line 聊天室中發送簡單指令，機器人便會自動登入後台、擷取負責機台的最新底片存量，並依照緊急程度由少至多排序回傳警報清單。

---

## 核心設計與特色

1. **100% 免費運作模式**：
   - 嚴格僅透過 Line Webhook 事件中的單次**回覆令牌 (Reply Token)** 進行被動回覆，絕不使用主動推播 (Push Message)，徹底避開 Line 每月免費額度限制。
   - 託管於 Render 免費方案，搭配外部定時服務達成零主機營運成本。

2. **本地離線驗證碼辨識 (Captcha OCR)**：
   - 使用開源 `ddddocr` 引擎於記憶體 Byte Stream 進行辨識，無外部視覺 API 訂閱費用，亦不落地儲存任何圖片檔案，安全高效。

3. **會話快取與自適應重試**：
   - 自動保存與複用 `PHPSESSID` 會話。在會話有效期間，查詢僅需約 0.3~0.6 秒。遇會話過期自動重新辨識登入（最多 3 次）。

4. **登入熔斷保護機制 (Circuit Breaker)**：
   - 當後台登入連續失敗達門檻（3 次）時自動啟動熔斷保護，暫停連線 60 秒，避免對後台造成雪崩效應或導致帳號被鎖定。

5. **定時心跳保活機制 (Keep-Alive)**：
   - 提供專屬 `/health` 端點，供外部定時排程（如 cron-job.org）每 10 分鐘發送 GET 請求，同時防止 Render 免費方案 15 分鐘閒置休眠（Spin-down）並探測後台維持 Session 活躍。

---

## 支援指令集與操作範例

| 指令類別 | 指令範例 | 說明 |
| :--- | :--- | :--- |
| **預設查詢** | `底片` 或 `檢查底片` | 查詢預設維修師 (91) 及協同機台（如維修師 19 之高雄指定機台）全部狀態（s=0）剩餘張數 <= 20 張的機台，依剩餘張數由少至多排序 |
| **張數門檻過濾** | `底片 < 20`<br>`底片 小於 30`<br>`檢查底片 門檻 50` | 查詢預設維修師 (91) 及協同機台剩餘張數小於等於指定門檻的機台（不限後台狀態分類） |
| **值班底片殘量查詢** | `值班`<br>`值班底片`<br>`值班底片殘量`<br>`值班 < 30` | 查詢南區 (`area=46`) 全區值班負責機台（預設門檻 20 張，亦支援自訂門檻），自動標註各機台責任維修師，並依緊急程度由少至多排序 |
| **跨維修師查詢** | `底片 師 92`<br>`底片維修師 88`<br>`檢查底片 師 88` | 查詢指定編號維修師名下「接近底限」的機台，便於同事間代班或跨組支援 |
| **複合查詢** | `底片 92 < 30`<br>`底片 88 小於 20`<br>`底片 92 門檻 15` | 指定維修師編號並自訂剩餘張數門檻，精確篩選特定同事需補充底片的機台 |
| **指令教學說明** | `說明`、`底片 說明`、`教學`、`help` | 顯示完整指令清單、語法規範與實際範例 |

### 回覆訊息範例

```text
⚠️ 【南區值班 機台底片存量警報】（剩餘張數 <= 20 張）
共找到 2 台機台需要注意（已依緊急程度由少至多排序）：

1. 🔴 台南第一診所 (ABC461-ND) [負責維修師: 蕭睿呈]
   剩餘張數：0 張

2. 🔴 小港第二辦公處 (ABC192-ST) [負責維修師: 蘇上豪]
   剩餘張數：6 張
```

---

## 系統環境與設定

### 環境變數說明

請參考 [`.env.example`](file:///e:/AutoCheckPhotoLimit/.env.example) 進行設定：

| 變數名稱 | 必要性 | 預設值 | 說明 |
| :--- | :---: | :---: | :--- |
| `SEIWA_BASE_URL` | 選填 | `https://dl02.seiwainc.com.tw` | Seiwa 後台網站根網址 |
| `SEIWA_ACCOUNT` | **必要** | 無 | Seiwa 後台登入帳號 |
| `SEIWA_PASSWORD` | **必要** | 無 | Seiwa 後台登入密碼 |
| `DEFAULT_TECHNICIAN_UNO` | 選填 | `91` | 未指定維修師時之預設維修師編號 |
| `DEFAULT_QUERY_STATUS` | 選填 | `0` | 預設查詢狀態類別（0=全部狀態，2=接近底限） |
| `DEFAULT_QUERY_THRESHOLD` | 選填 | `20` | 預設查詢之剩餘張數門檻（<= 20 張） |
| `EXCLUDED_MACHINE_IDS` | 選填 | `ABC158-ND` | 排除機台代號清單（支援逗號、分號 `,` `;` 或換行分隔多筆，不區分大小寫） |
| `EXCLUDED_MACHINE_NAMES` | 選填 | `高雄職訓中心` | 排除機台名稱關鍵字清單（支援逗號、分號 `,` `;` 或換行分隔多筆，包含比對） |
| `DUTY_AREA_NO` | 選填 | `46` | 值班查詢之預設責任區域編號（預設 46 南區） |
| `DUTY_AREA_NAME` | 選填 | `南區` | 值班查詢之責任區域名稱 |
| `COLLABORATIVE_CONFIG_PATH` | 選填 | `config/collaborative_machines.json` | 跨維修師協同機台清單設定檔路徑 |
| `LINE_CHANNEL_SECRET` | **必要** | 無 | Line Developers Messaging API Channel Secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | **必要** | 無 | Line Developers Messaging API Channel Access Token |
| `PORT` | 選填 | `8000` | 伺服器監聽埠號（雲端平台通常自動提供） |

### 協同機台設定 (`config/collaborative_machines.json`)

系統支援將跨維修師負責的機台獨立配置於 JSON 設定檔中。當現場維修師發送預設指令（如「底片」）時，系統會自動將這些機台與預設維修師的機台合併查詢並統一排序。

```json
{
  "collaborative_technicians": [
    {
      "uno": 19,
      "description": "高雄協同機台",
      "machines": [
        {"id": "ABC074-ND", "name": "寶雅高雄文信"},
        {"id": "ABC079-ST", "name": "寶雅高雄灣內店"}
      ]
    }
  ]
}
```

---

## 本地開發與測試

### 1. 安裝環境與相依套件

```bash
# 建立虛擬環境
python -m venv .venv

# 啟動虛擬環境 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 安裝相依套件
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 填入後台與 Line 憑證
```

### 3. 執行測試套件與型別檢查

```bash
# 執行所有單元測試與端對端測試
pytest

# 執行靜態型別檢查
mypy --ignore-missing-imports src tests
```

### 4. 本地啟動伺服器

```bash
python src/main.py
# 服務將於 http://127.0.0.1:8000 啟動
```

---

## Render 雲端平台部署指南

本系統已配置完整 Render 設定，支援 Blueprint 自動部署或手動 Web Service 建立。

### 方法 A：手動建立 Web Service（推薦）

1. 登入 [Render Dashboard](https://dashboard.render.com/)。
2. 點擊 **New +** -> **Web Service**。
3. 連結存放此專案的 GitHub 倉庫。
4. 設定基本參數：
   - **Name**: `autocheckphotolimit`（或自訂名稱）
   - **Region**: 建議選擇 `Singapore` 或鄰近台灣之地區
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
5. 在 **Environment Variables** 區域新增下列變數：
   - `PYTHON_VERSION`: `3.13.1`
   - `SEIWA_BASE_URL`: `https://dl02.seiwainc.com.tw`
   - `SEIWA_ACCOUNT`: `您的後台帳號`
   - `SEIWA_PASSWORD`: `您的後台密碼`
   - `DEFAULT_TECHNICIAN_UNO`: `91`
   - `LINE_CHANNEL_SECRET`: `您的 Line Channel Secret`
   - `LINE_CHANNEL_ACCESS_TOKEN`: `您的 Line Channel Access Token`
6. 點擊 **Create Web Service**，等待建置完成。部署成功後將取得專屬網址，例如：`https://autocheckphotolimit.onrender.com`。

---

## 外部定時心跳保活設定 (cron-job.org)

Render 免費方案在**閒置 15 分鐘後會自動休眠 (Spin-down)**，首次喚醒需耗時約 50 秒，會直接導致 Line Webhook 逾時（Line 要求 1 秒左右完成被動回覆）。

本系統實作了強化版 `/health` 端點，透過外部免費排程服務每 10 分鐘探測一次，達成**永不休眠**且**後台 Session 永不過期**的雙重效果。

### 設定步驟（以 cron-job.org 為例）：

1. 註冊並登入免費的 [cron-job.org](https://cron-job.org/)。
2. 點擊 **Create Cronjob**。
3. 設定任務屬性：
   - **Title**: `AutoCheckPhotoLimit Keep-Alive`
   - **URL**: `https://<您的-render-網址>.onrender.com/health`（請替換為實際網址）
   - **Execution schedule**: 選擇 `Every 10 minutes`（每 10 分鐘執行一次）
   - **Request method**: `GET`
4. 點擊 **Create** 儲存。
5. 檢查執行日誌：每次請求應回傳 HTTP 200，且內容為 `{"status": "ok", "session": "active"}`。

---

## Line 機器人 Webhook 設定

1. 登入 [Line Developers Console](https://developers.line.biz/console/)。
2. 進入您的 Messaging API Channel。
3. 切換至 **Messaging API** 分頁：
   - **Webhook URL**: 填入 `https://<您的-render-網址>.onrender.com/callback`
   - 點擊 **Verify** 按鈕，確認顯示 `Success`。
   - 開啟 **Use webhook** 開關。
4. 前往 [Line Official Account Manager](https://manager.line.biz/)：
   - 點擊右上角 **設定** -> **回應設定**。
   - **回應模式**: 選擇 `聊天室 (Chat)` 或 `Bot`。
   - **自動回應訊息**: 設定為 `關閉`（避免 Line 官方自動發出「感謝您的訊息」干擾）。
   - **Webhook**: 設定為 `開啟`。
5. 在 Line 中將機器人加入好友，發送「`底片`」或「`說明`」開始使用！

---

## 相關架構決策 (ADRs)

- [ADR-0001: 離線 OCR 驗證碼辨識與連線會話保持](file:///e:/AutoCheckPhotoLimit/docs/adr/0001-captcha-ocr-and-session-retention.md)
- [ADR-0002: 嚴格透過 Line 被動回覆令牌 (replyToken) 回傳訊息](file:///e:/AutoCheckPhotoLimit/docs/adr/0002-line-reply-token-only.md)
- [ADR-0003: 託管於 Render 免費方案並結合外部定期心跳 (Keep-Alive)](file:///e:/AutoCheckPhotoLimit/docs/adr/0003-free-hosting-with-external-keepalive.md)
- [ADR-0004: 採用獨立設定檔管理跨維修師協同機台與預設查詢合併策略](file:///e:/AutoCheckPhotoLimit/docs/adr/0004-collaborative-machines-configuration.md)
- [ADR-0005: 預設查詢改為全部狀態門檻20張並過濾異常機台 (ABC158-ND)](file:///e:/AutoCheckPhotoLimit/docs/adr/0005-default-query-threshold-and-abnormal-machine-filter.md)
- [ADR-0006: 新增南區值班底片殘量查詢模式 (area=46, s=0)](file:///e:/AutoCheckPhotoLimit/docs/adr/0006-on-duty-stock-query-for-south-area.md)
- [ADR-0007: 新增維修師維護行程查詢功能 (UserMonth.php)](file:///e:/AutoCheckPhotoLimit/docs/adr/0007-maintenance-schedule-query.md)
- [ADR-0008: 精簡機器人自動回覆訊息格式](file:///e:/AutoCheckPhotoLimit/docs/adr/0008-simplify-bot-reply-messages.md)
