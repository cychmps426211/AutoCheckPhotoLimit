import logging
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from src.auth.session_manager import SessionManager, CircuitBreakerError
from src.bot.message_builder import MachineStock
from src.config import (
    SEIWA_BASE_URL,
    DEFAULT_TECHNICIAN_UNO,
    DEFAULT_QUERY_STATUS,
    DEFAULT_QUERY_THRESHOLD,
    EXCLUDED_MACHINE_IDS,
    EXCLUDED_MACHINE_NAMES,
)
from src.crawler.collaborative_manager import load_collaborative_config

logger = logging.getLogger(__name__)


class TechnicianNotFoundError(Exception):
    """查無維修師或維修師名下無任何機台"""

    def __init__(self, uno: int):
        self.uno = uno
        super().__init__(f"查無維修師 {uno} 負責之機台資料，請確認維修師編號是否正確。")


class PaperCrawler:
    """
    負責爬取並解析 Seiwa 後台機台底片存量資料。
    - 支援透過後台 API (PaperMachineGetPage.php) 高效取得結構化資料
    - 支援解析 HTML 表格以相容靜態快照
    - 嚴格落實 CONTEXT.md 之「緊急排序（剩餘張數由少至多）」與「剩餘張數門檻過濾」
    - 支援過濾異常機台 (如 ABC158-ND 高雄職訓中心)
    """

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        base_url: str = SEIWA_BASE_URL,
    ):
        self.session_manager = session_manager or SessionManager()
        self.base_url = base_url.rstrip("/")

    def keep_alive(self) -> str:
        """委派 SessionManager 執行心跳保活探測"""
        return self.session_manager.keep_alive()

    @staticmethod
    def _is_excluded_machine(machine_id: str, machine_name: str) -> bool:
        """判定機台是否為異常排除機台（比對代號與名稱關鍵字）"""
        m_id = machine_id.strip().upper()
        if m_id and m_id in EXCLUDED_MACHINE_IDS:
            return True

        for exc_name in EXCLUDED_MACHINE_NAMES:
            if exc_name and exc_name in machine_name:
                return True

        return False

    def _post_query(
        self,
        session: requests.Session,
        uno: int,
        status: int,
        area: int,
        page_size: int = 1000,
    ) -> list:
        api_url = f"{self.base_url}/BLL/Paper/PaperMachineGetPage.php"
        payload = {
            "PageSize": page_size,
            "PageNo": 1,
            "AreaNo": area,
            "UserNo": uno,
            "Status": status,
        }
        referer_query = f"area={area}&s={status}" if uno == 0 else f"area={area}&uno={uno}&s={status}"
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.base_url}/pc/Paper/PaperMachine.php?{referer_query}",
        }
        resp = session.post(api_url, data=payload, headers=headers, timeout=10)
        is_redirect_or_html = (
            resp.status_code != 200
            or (isinstance(resp.text, str) and resp.text.startswith("<!DOCTYPE"))
        )
        if is_redirect_or_html:
            logger.warning("後台會話可能失效，嘗試重新登入後再次查詢...")
            self.session_manager.login()
            session = self.session_manager.get_authenticated_session()
            resp = session.post(api_url, data=payload, headers=headers, timeout=10)

        if resp.status_code != 200:
            raise RuntimeError(f"後台 API 回應異常，狀態碼: {resp.status_code}")

        return resp.json()

    @classmethod
    def _parse_machine_item(
        cls,
        item: dict,
        threshold: Optional[int] = None,
        fallback_name: str = "",
    ) -> Optional[MachineStock]:
        """解析後台單筆機台資料，過濾異常機台並套用張數門檻過濾"""
        code_no = str(item.get("CodeNo", "")).strip()
        shop_name = str(item.get("ShopName", "")).strip() or fallback_name

        # 異常機台過濾 (Abnormal machine filtering)
        if cls._is_excluded_machine(code_no, shop_name):
            logger.info(f"過濾異常機台: {code_no} ({shop_name})")
            return None

        try:
            paper_str = str(item.get("Paper", "0")).strip()
            remaining_sheets = int(paper_str)
        except ValueError:
            remaining_sheets = 0

        # 剩餘張數門檻過濾 (Threshold filtering)
        if threshold is not None and remaining_sheets > threshold:
            return None

        in_charge = str(item.get("InCharge", "")).strip()

        return MachineStock(
            machine_id=code_no,
            machine_name=shop_name,
            remaining_sheets=remaining_sheets,
            status_text=str(item.get("SafeQty", "")),
            in_charge=in_charge,
        )

    def fetch_machine_stock(
        self,
        uno: int = DEFAULT_TECHNICIAN_UNO,
        status: int = DEFAULT_QUERY_STATUS,
        threshold: Optional[int] = None,
        area: int = 0,
        include_collaborative: bool = False,
    ) -> List[MachineStock]:
        """
        向後台請求指定維修師或指定區域之機台底片存量。
        - uno: 維修師編號 (預設 91；若為 0 則代表全區值班查詢)
        - status: 底片狀態類別 (0=全部, 1=充足, 2=接近底限, 3=低於底限)
        - threshold: 剩餘張數門檻，僅保留 <= threshold 的機台
        - area: 責任區域代號 (如 46 代表南區)
        - include_collaborative: 是否一併查詢並合併協同維修師之指定機台 (僅限預設維修師)
        """
        session = self.session_manager.get_authenticated_session()

        try:
            raw_data = self._post_query(session, uno=uno, status=status, area=area, page_size=1000)
        except (TechnicianNotFoundError, CircuitBreakerError):
            raise
        except Exception as e:
            logger.error(f"查詢機台資料失敗: {e}")
            raise RuntimeError(f"無法從後台取得機台資料: {e}")

        # 若後台回傳為空
        if not raw_data:
            if uno == 0:
                return []
            if status == 0:
                raise TechnicianNotFoundError(uno)
            else:
                # 查詢 status=0 確認是否有名下機台
                try:
                    existence_data = self._post_query(session, uno=uno, status=0, area=area, page_size=1)
                    if not existence_data:
                        raise TechnicianNotFoundError(uno)
                except (TechnicianNotFoundError, CircuitBreakerError):
                    raise
                except Exception as e:
                    logger.error(f"確認維修師機台總數失敗: {e}")
                    raise RuntimeError(f"無法驗證維修師機台資訊: {e}")

        machines: List[MachineStock] = []
        for item in raw_data:
            m = self._parse_machine_item(item, threshold=threshold)
            if m:
                machines.append(m)

        # 若啟用協同機台查詢且為主維修師，查詢並合併協同維修師之指定關注機台
        if include_collaborative and uno == DEFAULT_TECHNICIAN_UNO:
            collaborative_technicians = load_collaborative_config()
            for collab in collaborative_technicians:
                try:
                    collab_raw = self._post_query(
                        session,
                        uno=collab.uno,
                        status=status,
                        area=area,
                        page_size=1000,
                    )
                    for item in collab_raw:
                        code_no = str(item.get("CodeNo", "")).strip()
                        if not collab.matches(code_no):
                            continue

                        fallback = collab.resolve_name(code_no, str(item.get("ShopName", "")))
                        m = self._parse_machine_item(
                            item, threshold=threshold, fallback_name=fallback
                        )
                        if m:
                            machines.append(m)
                except Exception as e:
                    logger.warning(
                        f"查詢協同維修師 {collab.uno} 機台資料失敗: {e}，略過該協同維修師機台。"
                    )

        # 依 machine_id 去重（保留優先加入之主機台資訊）
        seen_ids = set()
        unique_machines: List[MachineStock] = []
        for m in machines:
            if m.machine_id not in seen_ids:
                seen_ids.add(m.machine_id)
                unique_machines.append(m)
        machines = unique_machines

        # 緊急排序 (Urgency Sorting)：依剩餘張數由少至多（升冪）排序
        machines.sort(key=lambda m: m.remaining_sheets)
        return machines

    @classmethod
    def parse_html_table(
        cls,
        html: str,
        threshold: Optional[int] = None,
    ) -> List[MachineStock]:
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

            # 異常機台過濾 (Abnormal machine filtering)
            if cls._is_excluded_machine(code_no, shop_name):
                logger.info(f"HTML 表格過濾異常機台: {code_no} ({shop_name})")
                continue

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
