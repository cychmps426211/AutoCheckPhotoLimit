# 0007. 新增維修師維護行程查詢功能 (UserMonth.php)

## 背景與問題
1. **現場巡檢紀錄查詢需求**：
   現場維修師巡檢機台時，需即時確認當天已完成了哪些機台的維護，或查詢指定日期之歷史巡檢路線與時間點。
2. **後台網址與月曆呈現方式**：
   Seiwa 後台之行程紀錄網址為 `https://dl02.seiwainc.com.tw/pc/Maintenance/UserMonth.php?uno=91&m1=YYYY-MM`，固定查詢預設維修師（`uno=91`）。該頁面以整月月曆表格形式呈現，在手機上不易快速閱讀當天行程。
3. **時區與自然語言彈性**：
   Line 機器人部署於雲端主機（系統時間常為 UTC），因此計算「今日」必須鎖定台灣標準時間（`Asia/Taipei`，UTC+8）。同時維修師除了發送「今日行程」外，亦可能發送「行程 0922」或「0922行程」查詢特定日期的巡檢紀錄。

## 決策
1. **爬蟲層架構與月曆解析 (`ScheduleCrawler`)**：
   - 建立獨立模組 `src/crawler/schedule_crawler.py`，共用既有之 `SessionManager`，確保 PHPSESSID 與自動 OCR 登入機制復用。
   - 資料結構定義 `ScheduleItem(order: int, machine_id: str, machine_name: str, time_str: str)`。
   - 解析 `UserMonth.php` HTML 月曆：配對日期標題列與行程內容列，在目標日期的單元格中，以每 3 個 `div` 為一組提取機台代號（`CodeNo`）、機台名稱（`ShopName`）與維護時間（`HH:MM`）。
   - 保留項目在月曆中原生的先後時間順序。
2. **指令解析器 (`CommandParser`) 擴充**：
   - 擴充指令型態 `action="schedule_query"`，並加入 `target_date: Optional[datetime.date]`。
   - 預設指令（「今日行程」、「今天行程」、「行程」）以 `Asia/Taipei` (UTC+8) 計算當前日期。
   - 支援「昨天行程」、「明日行程」等相對日期。
   - 支援「行程 0922」、「行程 09/22」、「行程 2026-09-22」、「0922行程」等指定日期格式。
3. **訊息排版 (`MessageBuilder.build_schedule_report`)**：
   - 清晰簡明格式呈現：
     ```text
     📅 【維修師 91 維護行程】2026-09-23
     共 1 處維護紀錄（按時間順序）：

     1. 08:15 ABC061-ST 高雄楠梓監理
     ```
   - 若當日無紀錄，回傳友善提示（例如：「本日無任何維護行程紀錄」）。
   - 更新說明訊息 (`build_help_message`) 列出行程查詢指令範例。

## 影響與後果
- 現場維修師可透過 Line 隨時輸入「行程」或「行程 0922」秒查維護軌跡，無需在行動瀏覽器手動登入與縮放網頁。
- 台灣時區保證在跨日時不會因為雲端主機 UTC 時間產生落差。
- 共用 Session 機制讓行程查詢速度維持在 1~2 秒內。
