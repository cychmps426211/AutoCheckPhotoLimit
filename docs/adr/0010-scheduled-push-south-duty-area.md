# 0010. 工作日定時推播改採南區值班底片存量查詢模式 (area=46, s=0)

## 背景與問題
1. **早晨巡檢範圍擴展與值班一致性**：
   現場維修團隊在工作日早晨展開巡檢時，關注重點已由個別維修師名下機台擴展為整個南區所有責任機台。先前 [ADR-0009](0009-scheduled-push-with-zero-alert-suppression.md) 所設計之定時推播採用預設查詢（`uno=91`, `s=0`，並合併協同機台），無法全面掌握南區其他維修師名下瀕臨缺紙之機台。
2. **與值班查詢模型的一致性**：
   系統已於 [ADR-0006](0006-on-duty-stock-query-for-south-area.md) 建立了「值班底片殘量查詢」模型（`area=46`, `s=0`, 預設門檻 20 張），並支援解析每台機台之後台責任維修師（`InCharge`）。現場維修師希望每日定時推播之資料範疇能與「值班」查詢一致，使所有收到推播的維修師皆能清楚辨識全南區之急迫機台及其對應負責同仁。

## 決策
1. **後台查詢條件變更**：
   - 定時推播任務端點 `/tasks/daily-push` 在調用 `PaperCrawler.fetch_machine_stock` 時，由原先的預設查詢條件：
     `uno=DEFAULT_TECHNICIAN_UNO (91), status=0, threshold=20, include_collaborative=True`
     變更為與值班相同的南區全區查詢條件：
     `uno=0, status=DEFAULT_QUERY_STATUS (0), threshold=DEFAULT_QUERY_THRESHOLD (20), area=DUTY_AREA_NO (46), include_collaborative=False`。
2. **警報排版格式變更**：
   - 警報訊息排版由 `MessageBuilder.build_stock_report` 調整為 `MessageBuilder.build_duty_stock_report`。
   - 推播訊息抬頭標註 `⚠️ 【南區值班 機台底片存量警報】（剩餘張數 <= 20 張）`，每台機台呈現 `[負責維修師: {InCharge}]`，便利現場跨組協調與補紙分工。
3. **維持既有節流與安全防護架構**：
   - 完整保留 ADR-0009 確立之「零警報靜默節流（Zero-Report Suppression）」機制（若全區皆大於門檻則靜默不發送，消耗 0 則配額）。
   - 完整保留 `PUSH_TASK_TOKEN` 安全金鑰驗證與熔斷防護（Circuit Breaker）機制。

## 影響與後果
- 工作日早晨 08:00 定時推播將全面覆蓋南區 130 餘台機台中剩餘張數 <= 20 張之警報機台，提升全區底片存量監控覆蓋率。
- 每台警報機台均明確標示負責維修師，使收到廣播的維修師能立即知悉責任歸屬並迅速處置。
- 零警報靜默節流機制依然嚴格守護每月 200 則免費廣播配額。
