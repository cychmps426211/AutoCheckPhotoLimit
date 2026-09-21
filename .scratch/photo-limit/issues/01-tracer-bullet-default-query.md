# 01 — 基礎全通路貫通 (Tracer Bullet: Default Query & Line Reply)

**What to build:**
當維修師在 Line 聊天室中發送「底片」或「檢查底片」時，系統能解析指令並查詢後台。若當前無有效會話，系統透過開源離線 OCR 自動完成登入並快取會話（PHPSESSID）。系統抓取預設維修師（91）負責且底片狀態為「接近底限」的機台清單，將結果依剩餘張數由少至多（緊急排序）排版後，透過 Line 回覆令牌（Reply Token）即時回送文字訊息給維修師。

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] 維修師發送「底片」或「檢查底片」時，能收到預設維修師（91）接近底限之機台清單
- [x] 回傳的機台清單依剩餘張數由小到大（升冪）排列
- [x] 當沒有現成有效 Session 時，系統能調用 ddddocr 自動辨識驗證碼並登入成功
- [x] 登入成功後保存 Session，後續查詢重複利用該會話以降低延遲
- [x] 訊息回覆一律採用 Line Reply Token，不消耗 Push 額度
- [x] 提供 `/health` 基礎健康檢查端點
- [x] 具備端對端 Webhook 測試，驗證從收到 Line Webhook 請求到呼叫 Line Reply API 的完整流程
