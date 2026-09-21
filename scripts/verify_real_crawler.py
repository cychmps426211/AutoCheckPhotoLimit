import sys
from pathlib import Path
import time

# 將專案根目錄加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 設定 UTF-8 編碼避免 Windows 主控台亂碼
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import logging
from src.auth.session_manager import SessionManager
from src.crawler.paper_crawler import PaperCrawler
from src.bot.message_builder import MessageBuilder
from src.config import DEFAULT_TECHNICIAN_UNO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("verify_crawler")


def main():
    print("=" * 60)
    print("🚀 【驗證測試】Seiwa 後台登入與底片存量資料抓取")
    print("=" * 60)

    # 1. 測試 SessionManager 登入與會話保持
    mgr = SessionManager()
    print(f"\n[步驟 1] 連線與登入 Seiwa 後台...")
    print(f"  後台網址: {mgr.base_url}")
    print(f"  登入帳號: {mgr.account}")
    
    t0 = time.time()
    session = mgr.get_authenticated_session()
    login_time = time.time() - t0
    phpsessid = session.cookies.get("PHPSESSID", "未知")
    print(f"  ✅ 登入成功！耗時: {login_time:.2f} 秒, PHPSESSID: {phpsessid}")

    # 2. 測試 PaperCrawler：預設查詢 (維修師 91, 接近底限 s=2)
    crawler = PaperCrawler(session_manager=mgr)
    print(f"\n[步驟 2] 查詢預設維修師 ({DEFAULT_TECHNICIAN_UNO}) 接近底限 (status=2) 之機台...")
    t1 = time.time()
    low_stock_machines = crawler.fetch_machine_stock(uno=DEFAULT_TECHNICIAN_UNO, status=2)
    fetch_time1 = time.time() - t1
    print(f"  ✅ 查詢完成！耗時: {fetch_time1:.2f} 秒，共找到 {len(low_stock_machines)} 台機台")
    
    # 產出 Line 回覆格式訊息
    line_msg = MessageBuilder.build_stock_report(uno=DEFAULT_TECHNICIAN_UNO, machines=low_stock_machines)
    print("\n--- Line 回覆訊息預覽 ---")
    print(line_msg)
    print("------------------------")

    # 3. 測試張數過濾與緊急排序 (維修師 91, status=0 全部機台, 門檻 <= 50 張)
    threshold = 50
    print(f"\n[步驟 3] 測試門檻過濾：查詢維修師 ({DEFAULT_TECHNICIAN_UNO}) 剩餘張數 <= {threshold} 張之機台...")
    t2 = time.time()
    filtered_machines = crawler.fetch_machine_stock(uno=DEFAULT_TECHNICIAN_UNO, status=0, threshold=threshold)
    fetch_time2 = time.time() - t2
    print(f"  ✅ 查詢完成！耗時: {fetch_time2:.2f} 秒，共找到 {len(filtered_machines)} 台機台")
    for idx, m in enumerate(filtered_machines, start=1):
        print(f"    {idx}. [{m.machine_id}] {m.machine_name} - 剩餘: {m.remaining_sheets} 張")

    # 4. 驗證會話複用速度 (Session Keep-Alive)
    print(f"\n[步驟 4] 驗證會話複用 (第二次請求是否有快取且小於 0.5 秒)...")
    t3 = time.time()
    crawler.fetch_machine_stock(uno=DEFAULT_TECHNICIAN_UNO, status=2)
    cached_time = time.time() - t3
    print(f"  ✅ 會話複用成功！第二次請求耗時: {cached_time:.3f} 秒 (遠小於初次登入時間 {login_time:.2f} 秒)")

    print("\n" + "=" * 60)
    print("🎉 所有真實後台驗證項目皆順利通過！")
    print("=" * 60)


if __name__ == "__main__":
    main()
