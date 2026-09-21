# 0003. 託管於 Render 免費方案並結合外部定期心跳（Keep-Alive）

## 背景與問題
系統需以 100% 免費方式託管，並提供 HTTPS Webhook 接收 Line 平台請求。免費雲端平台（如 Render）通常具備閒置 15 分鐘休眠機制（Spin-down），喚醒需約 50 秒，會直接導致 Line Webhook 逾時報錯；同時後台管理網站的 PHP Session 亦有閒置逾期失效問題。

## 決策
1. 採用 Render Free Web Service 託管 FastAPI 服務。
2. 搭配外部免費定時排程服務（cron-job.org 或 UptimeRobot），設定每 10 分鐘 GET 一次伺服器的 `/health` 端點。
3. `/health` 處理程序除了維持伺服器常駐不休眠外，同時對後台管理系統發送輕量探測以保持 `PHPSESSID` 活躍。

## 影響與後果
- 達成 100% 免費運作，且無休眠喚醒延遲。
- Line 查詢能穩定在 0.3~0.8 秒內完成並以 `replyToken` 回覆。
- 未來若遷移至自建設備（如家中 Mac 或 NAS），僅需關閉外部定時服務並轉為內部定時工作，應用程式架構無需改動。
