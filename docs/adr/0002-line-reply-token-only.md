# 0002. Line 訊息回覆全面採用 ReplyToken 被動回覆機制

## 背景與問題
Line Official Account（官方帳號）免費方案每個月僅提供 200 則主動推播（Push Message）額度，超過需付費升級方案；然而使用者的 `replyToken` 被動回覆（Reply Message）是完全免費且不限則數。

## 決策
系統內所有查詢結果與錯誤提示，一律透過 Webhook 傳入的 `replyToken` 呼叫 Line Reply API 進行回覆。禁止使用 `push_message`，以保證系統長期運行在零費用的邊界內。

## 影響與後果
- 運作成本為 $0，無訊息發送量限制。
- 查詢與解析邏輯必須在 Webhook 回應時限（通常建議 1~3 秒內）完成並送出 reply，不可拖延超過 replyToken 的生命週期。
