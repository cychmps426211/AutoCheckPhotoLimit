import datetime
import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from src.auth.session_manager import SessionManager, CircuitBreakerError
from src.config import SEIWA_BASE_URL, DEFAULT_TECHNICIAN_UNO

logger = logging.getLogger(__name__)

# 台灣時區 (UTC+8)
TAIWAN_TZ = datetime.timezone(datetime.timedelta(hours=8))


def get_taiwan_today() -> datetime.date:
    """取得台灣時區 (UTC+8) 的當前日期"""
    return datetime.datetime.now(TAIWAN_TZ).date()


@dataclass
class ScheduleItem:
    order: int
    machine_id: str
    machine_name: str
    time_str: str


class ScheduleCrawler:
    """
    負責爬取並解析 Seiwa 後台維修師月曆行程資料 (UserMonth.php)。
    - 固定或自訂查詢維修師 (預設 uno=91)
    - 根據目標日期指定月份 m1 (YYYY-MM)，並解析月曆對應日期之維護行程
    - 嚴格按照到達時間先後順序回傳行程清單
    """

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        base_url: str = SEIWA_BASE_URL,
    ):
        self.session_manager = session_manager or SessionManager()
        self.base_url = base_url.rstrip("/")

    @classmethod
    def parse_schedule_table(
        cls,
        html: str,
        target_date: datetime.date,
    ) -> List[ScheduleItem]:
        """
        解析 UserMonth.php 的 HTML 月曆表格，擷取指定日期的行程項目。
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")
        target_str_ymd = target_date.strftime("%Y-%m-%d")
        target_str_md = target_date.strftime("%m/%d")

        target_content_td = None

        # 月曆表格結構：第 1 列為星期標題，之後為（日期標題列 + 內容列）交替配對
        for i in range(1, len(rows), 2):
            if i + 1 >= len(rows):
                break
            date_row = rows[i]
            content_row = rows[i + 1]

            date_tds = date_row.find_all(["td", "th"])
            content_tds = content_row.find_all("td")

            for col_idx, (d_td, c_td) in enumerate(zip(date_tds, content_tds)):
                matched = False
                a_tag = d_td.find("a")
                if a_tag and "href" in a_tag.attrs:
                    m = re.search(r"d=(\d{4}-\d{2}-\d{2})", str(a_tag["href"]))
                    if m and m.group(1) == target_str_ymd:
                        matched = True


                if not matched:
                    date_text = d_td.get_text(strip=True)
                    if date_text == target_str_md:
                        matched = True

                if matched:
                    target_content_td = c_td
                    break

            if target_content_td is not None:
                break

        if not target_content_td:
            return []

        # 解析單元格內的三元組 div 項目
        divs = target_content_td.find_all("div", recursive=False)
        items: List[ScheduleItem] = []

        idx = 0
        order = 1
        while idx < len(divs):
            d1_text = divs[idx].get_text(strip=True)
            # 移除開頭序號，例如 "1. ABC197-ST" -> "ABC197-ST"
            machine_id = re.sub(r"^\d+\.\s*", "", d1_text).strip()

            machine_name = ""
            if idx + 1 < len(divs):
                machine_name = divs[idx + 1].get_text(strip=True)

            time_str = ""
            if idx + 2 < len(divs):
                time_str = divs[idx + 2].get_text(strip=True)

            if machine_id:
                items.append(
                    ScheduleItem(
                        order=order,
                        machine_id=machine_id,
                        machine_name=machine_name,
                        time_str=time_str,
                    )
                )
                order += 1

            idx += 3

        return items

    def fetch_schedule(
        self,
        uno: int = DEFAULT_TECHNICIAN_UNO,
        target_date: Optional[datetime.date] = None,
    ) -> List[ScheduleItem]:
        """
        向 Seiwa 後台發送請求取得指定維修師與指定日期之行程清單。
        """
        if target_date is None:
            target_date = get_taiwan_today()

        m1 = target_date.strftime("%Y-%m")
        url = f"{self.base_url}/pc/Maintenance/UserMonth.php?uno={uno}&m1={m1}"
        session = self.session_manager.get_authenticated_session()

        try:
            resp = session.get(url, timeout=10)
        except CircuitBreakerError:
            raise
        except Exception as e:
            logger.error(f"請求行程月曆失敗: {e}")
            raise RuntimeError(f"無法連線至行程月曆頁面: {e}")

        # 檢測是否被重定向至未登入或錯誤頁面
        is_redirect_or_expired = (
            resp.status_code != 200
            or "500.html" in getattr(resp, "url", "")
            or ("<!DOCTYPE" in resp.text and "login" in resp.text.lower())
        )

        if is_redirect_or_expired:
            logger.warning("後台會話可能失效，嘗試重新登入後再次查詢行程...")
            self.session_manager.login()
            session = self.session_manager.get_authenticated_session()
            resp = session.get(url, timeout=10)

        if resp.status_code != 200:
            raise RuntimeError(f"行程月曆頁面回應異常，狀態碼: {resp.status_code}")

        return self.parse_schedule_table(resp.text, target_date)
