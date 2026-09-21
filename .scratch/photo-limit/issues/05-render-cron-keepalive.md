# 05 — 雲端部署配置與定時心跳保活 (Render & Keep-Alive Cron)

**What to build:**
為系統提供 Render 雲端平台部署所需的配置（Procfile、依賴與環境變數文件）。強化 `/health` 心跳端點，支援外部免費定時服務（如 cron-job.org 或 UptimeRobot）每 10 分鐘 GET 請求，同時觸發對後台管理系統之輕量探測以保持 `PHPSESSID` 活躍，達到 Render 免費方案零休眠與後台會話永不過期的雙重保活效果。

**Blocked by:** 01 (Issue #2), 02 (Issue #3), 03 (Issue #4), 04 (Issue #5)

**Status:** ready-for-agent

- [ ] 提供完整的部署設定檔（如 Procfile）以支援 Render Web Service 啟動
- [ ] `/health` 端點可正常回應健康狀態且帶動 Session 心跳保活
- [ ] 撰寫 README 部署與 cron-job.org 設定指引
- [ ] 驗證部署環境啟動與心跳機制運作正常
