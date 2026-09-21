import logging
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from src.auth.session_manager import SessionManager
from src.bot.message_builder import MachineStock
from src.config import SEIWA_BASE_URL, DEFAULT_TECHNICIAN_UNO

logger = logging.getLogger(__name__)


class PaperCrawler:
    """
    負責爬取並解析 Seiwa 後台機台底片存量資料。
    - 支援透過後台 API (PaperMachineGetPage.php) 高效取得結構化資料
    - 支援解析 HTML 表格以相容靜態快照
    - 嚴格落實 CONTEXT.md 之「緊急排序（剩餘張數由小到大）」與「剩餘張數門檻過濾」
    """

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        base_url: str = SEIWA_BASE_URL,
    ):
        self.session_manager = session_manager or SessionManager()
        self.base_url = base_url.rstrip("/")

    def fetch_machine_stock(
        self,
        uno: int = DEFAULT_TECHNICIAN_UNO,
        status: int = 2,
        threshold: Optional[int] = None,
        area: int = 0,
    ) -> List[MachineStock]:
        """
        向後台請求指定維修師與狀態之機台底片存量。
        - uno: 維修師編號 (預設 91)
        - status: 底片狀態類別 (0=全部, 1=充足, 2=接近底限, 3=低於底限)
        - threshold: 剩餘張數門檻，僅保留 <= threshold 的機台
        """
        api_url = f"{self.base_url}/BLL/Paper/PaperMachineGetPage.php"
        payload = {
            "PageSize": 1000,
            "PageNo": 1,
            "AreaNo": area,
            "UserNo": uno,
            "Status": status,
        }
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.base_url}/pc/Paper/PaperMachine.php?area={area}&uno={uno}&s={status}",
        }

        # 取得 Session，遇過期自動重新登入
        session = self.session_manager.get_authenticated_session()

        try:
            resp = session.post(api_url, data=payload, headers=headers, timeout=10)
            # 若重定向或非 200，可能 Session 逾期，嘗試重新登入一次
            if resp.status_code != 200 or resp.text.startswith("<!DOCTYPE"):
                logger.warning("後台會話可能失效，嘗試重新登入後再次查詢...")
                self.session_manager.login()
                session = self.session_manager.get_authenticated_session()
                resp = session.post(api_url, data=payload, headers=headers, timeout=10)

            raw_data = resp.json()
        except Exception as e:
            logger.error(f"查詢機台資料失敗: {e}")
            raise RuntimeError(f"無法從後台取得機台資料: {e}")

        machines: List[MachineStock] = []
        for item in raw_data:
            code_no = str(item.get("CodeNo", "")).strip()
            shop_name = str(item.get("ShopName", "")).strip()
            try:
                paper_str = str(item.get("Paper", "0")).strip()
                remaining_sheets = int(paper_str)
            except ValueError:
                remaining_sheets = 0

            # 剩餘張數門檻過濾 (Threshold filtering)
            if threshold is not None and remaining_sheets > threshold:
                continue

            machines.append(
                MachineStock(
                    machine_id=code_no,
                    machine_name=shop_name,
                    remaining_sheets=remaining_sheets,
                    status_text=str(item.get("SafeQty", "")),
                )
            )

        # 緊急排序 (Urgency Sorting)：依剩餘張數由少至多（升冪）排序
        machines.sort(key=lambda m: m.remaining_sheets)
        return machines

    @staticmethod
    def parse_html_table(html: str, threshold: Optional[int] = None) -> List[MachineStock]:
        """
        靜態 HTML 表格解析（提供次級整合測試 seam 驗證）
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        machines: List[MachineStock] = []
        rows = table.find_all("tr")

        for row in rows:
            tds = row.find_all("td")
            if not tds or len(tds) < 4:
                continue

            # 根據表格欄位結構：
            # col 1: 代號 + <br> + 店名
            # col 3: 剩餘張數
            col_id_name = tds[1]
            col_paper = tds[3].get_text(strip=True)

            text_parts = [t.strip() for t in col_id_name.stripped_strings]
            code_no = text_parts[0] if text_parts else ""
            shop_name = text_parts[1] if len(text_parts) > 1 else code_no

            try:
                remaining_sheets = int(col_paper)
            except ValueError:
                continue

            if threshold is not None and remaining_sheets > threshold:
                continue

            machines.append(
                MachineStock(
                    machine_id=code_no,
                    machine_name=shop_name,
                    remaining_sheets=remaining_sheets,
                )
            )

        # 緊急排序 (升冪)
        machines.sort(key=lambda m: m.remaining_sheets)
        return machines
