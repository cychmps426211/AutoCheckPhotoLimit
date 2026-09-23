import datetime
import re
from dataclasses import dataclass
from typing import Optional

from src.config import (
    DEFAULT_TECHNICIAN_UNO,
    DEFAULT_QUERY_STATUS,
    DEFAULT_QUERY_THRESHOLD,
    DUTY_AREA_NO,
)
from src.crawler.schedule_crawler import get_taiwan_today


@dataclass
class Command:
    action: str  # "query", "duty_query", "schedule_query", "schedule_query_invalid", "help", "unknown"
    uno: int = DEFAULT_TECHNICIAN_UNO
    status: int = DEFAULT_QUERY_STATUS  # 0: 全部, 2: 接近底限
    threshold: Optional[int] = None
    raw_text: str = ""
    include_collaborative: bool = False
    area: int = 0
    target_date: Optional[datetime.date] = None


class CommandParser:
    """
    維修師自然語言指令解析器
    支援語法：
    - 「底片」、「檢查底片」 -> 預設維修師 (91)，全部狀態門檻 20 (status=0, threshold=20)
    - 「底片 < 20」 -> 預設維修師 (91)，門檻 20 (status=0)
    - 「值班」、「值班底片」、「值班底片殘量」 -> 南區 (area=46)，全部狀態門檻 20
    - 「值班 < 20」、「值班底片 < 20」 -> 南區 (area=46)，門檻 20
    - 「今日行程」、「今天行程」、「行程」 -> 當日維護行程
    - 「行程 0922」、「0922行程」 -> 指定日期維護行程
    - 「說明」、「底片說明」、「底片 說明」、「help」 -> 幫助教學
    """

    # 說明指令
    HELP_PATTERN = re.compile(r"^(?:底片\s*(?:說明|教學)|說明|教學|help)$", re.IGNORECASE)

    # 行程預設指令（今日）
    SCHEDULE_DEFAULT_PATTERN = re.compile(r"^(?:今日行程|今天行程|行程)$")

    # 行程相對日期指令（昨天、昨日、明天、明日）
    SCHEDULE_RELATIVE_PATTERN = re.compile(r"^(昨天|昨日|明天|明日)行程$")

    # 行程指定日期指令：「行程 0922」、「行程 2026-09-22」
    SCHEDULE_PREFIX_PATTERN = re.compile(r"^行程\s+(.+)$")

    # 行程後綴指令：「0922行程」、「0922 行程」、「9/22行程」
    SCHEDULE_SUFFIX_PATTERN = re.compile(r"^(.+?)\s*行程$")


    # 值班查詢（南區 area=46，全部狀態 s=0，預設門檻 20 張）
    DUTY_QUERY_PATTERN = re.compile(
        r"^(?:值班|值班底片|值班底片殘量|值班檢查底片|檢查值班底片)$"
    )

    # 值班帶門檻查詢
    # 支援「值班 < 20」、「值班底片 < 20」、「值班底片殘量 < 20」、「值班 20張」等
    DUTY_THRESHOLD_QUERY_PATTERN = re.compile(
        r"^(?:值班|值班底片|值班底片殘量|值班檢查底片|檢查值班底片)\s*(?:(?:<=?|小於|門檻)\s*(\d+)\s*張?|(\d+)\s*張)$"
    )

    # 預設查詢（預設維修師 91，全部狀態 s=0，門檻 20 張）
    DEFAULT_QUERY_PATTERN = re.compile(r"^(?:檢查底片|底片)$")

    # 帶張數門檻查詢（預設維修師 91，張數 <= N，status=0）
    # 支援「底片 < 20」、「底片門檻 20」、「底片 20張」、「底片 <= 20」、「底片 < 20張」等
    THRESHOLD_QUERY_PATTERN = re.compile(
        r"^(?:底片|檢查底片)\s*(?:(?:<=?|小於|門檻)\s*(\d+)\s*張?|(\d+)\s*張)$"
    )

    # 指定維修師查詢（維修師 N，接近底限 status=2）
    # 支援「底片 師 88」、「底片 師88」、「底片維修師 88」、「檢查底片維修師 88」、「底片 師 88號」等
    TECHNICIAN_QUERY_PATTERN = re.compile(
        r"^(?:底片|檢查底片)\s*(?:師|維修師)\s*(\d+)\s*號?$"
    )

    # 複合查詢（維修師 N，張數 <= M，status=0）
    # 支援「底片 88 < 20」、「底片 88 <= 20」、「底片 88 小於 20」、「底片 88門檻 20」、「底片 88 20張」、「底片 師 88 < 20」等
    COMBINED_QUERY_PATTERN = re.compile(
        r"^(?:底片|檢查底片)\s*(?:(?:師|維修師)\s*)?(\d+)\s*號?\s*(?:(?:<=?|小於|門檻)\s*(\d+)\s*張?|\s+(\d+)\s*張)$"
    )

    @staticmethod
    def _parse_date_string(date_text: str, current_year: int) -> Optional[datetime.date]:
        cleaned_date = date_text.strip()
        # 1. YYYY-MM-DD or YYYY/MM/DD or YYYYMMDD
        m_full = re.match(r"^(\d{4})[-/]?(\d{1,2})[-/]?(\d{1,2})$", cleaned_date)
        if m_full:
            try:
                return datetime.date(int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3)))
            except ValueError:
                return None

        # 2. MM/DD or MM-DD (e.g. 09/22, 9/22, 09-22)
        m_slash = re.match(r"^(\d{1,2})[-/](\d{1,2})$", cleaned_date)
        if m_slash:
            try:
                return datetime.date(current_year, int(m_slash.group(1)), int(m_slash.group(2)))
            except ValueError:
                return None

        # 3. MMDD or MDD (e.g. 0922 -> 9, 22; 922 -> 9, 22)
        m_digits = re.match(r"^(\d{1,2})(\d{2})$", cleaned_date)
        if m_digits:
            try:
                return datetime.date(current_year, int(m_digits.group(1)), int(m_digits.group(2)))
            except ValueError:
                return None

        return None

    @classmethod
    def parse(cls, text: str) -> Command:
        cleaned = text.strip()

        # 1. 說明指令
        if cls.HELP_PATTERN.match(cleaned):
            return Command(action="help", raw_text=cleaned)

        # 2. 行程預設指令（今日）
        if cls.SCHEDULE_DEFAULT_PATTERN.match(cleaned):
            return Command(
                action="schedule_query",
                uno=DEFAULT_TECHNICIAN_UNO,
                target_date=get_taiwan_today(),
                raw_text=cleaned,
            )

        # 3. 行程相對日期指令（昨天、昨日、明天、明日）
        rel_match = cls.SCHEDULE_RELATIVE_PATTERN.match(cleaned)
        if rel_match:
            rel_word = rel_match.group(1)
            today = get_taiwan_today()
            delta = datetime.timedelta(days=-1) if rel_word in ("昨天", "昨日") else datetime.timedelta(days=1)
            return Command(
                action="schedule_query",
                uno=DEFAULT_TECHNICIAN_UNO,
                target_date=today + delta,
                raw_text=cleaned,
            )

        # 4. 行程指定日期前綴：「行程 0922」、「行程 2026-09-22」
        prefix_match = cls.SCHEDULE_PREFIX_PATTERN.match(cleaned)
        if prefix_match:
            date_arg = prefix_match.group(1)
            today = get_taiwan_today()
            parsed_date = cls._parse_date_string(date_arg, today.year)
            if parsed_date:
                return Command(
                    action="schedule_query",
                    uno=DEFAULT_TECHNICIAN_UNO,
                    target_date=parsed_date,
                    raw_text=cleaned,
                )
            return Command(
                action="schedule_query_invalid",
                raw_text=cleaned,
            )

        # 5. 行程指定日期後綴：「0922行程」、「0922 行程」、「9/22行程」
        suffix_match = cls.SCHEDULE_SUFFIX_PATTERN.match(cleaned)
        if suffix_match:
            date_arg = suffix_match.group(1)
            if date_arg not in ("今日", "今天", "昨天", "昨日", "明天", "明日"):
                today = get_taiwan_today()
                parsed_date = cls._parse_date_string(date_arg, today.year)
                if parsed_date:
                    return Command(
                        action="schedule_query",
                        uno=DEFAULT_TECHNICIAN_UNO,
                        target_date=parsed_date,
                        raw_text=cleaned,
                    )
                return Command(
                    action="schedule_query_invalid",
                    raw_text=cleaned,
                )

        # 6. 值班查詢：「值班」、「值班底片」、「值班底片殘量」等
        if cls.DUTY_QUERY_PATTERN.match(cleaned):
            return Command(
                action="duty_query",
                uno=0,
                area=DUTY_AREA_NO,
                status=DEFAULT_QUERY_STATUS,
                threshold=DEFAULT_QUERY_THRESHOLD,
                raw_text=cleaned,
            )


        # 3. 值班帶門檻查詢：「值班 < 20」、「值班底片 30張」等
        duty_threshold_match = cls.DUTY_THRESHOLD_QUERY_PATTERN.match(cleaned)
        if duty_threshold_match:
            threshold_val = int(
                duty_threshold_match.group(1) or duty_threshold_match.group(2)
            )
            return Command(
                action="duty_query",
                uno=0,
                area=DUTY_AREA_NO,
                status=DEFAULT_QUERY_STATUS,
                threshold=threshold_val,
                raw_text=cleaned,
            )

        # 4. 預設查詢：「底片」、「檢查底片」
        if cls.DEFAULT_QUERY_PATTERN.match(cleaned):
            return Command(
                action="query",
                uno=DEFAULT_TECHNICIAN_UNO,
                status=DEFAULT_QUERY_STATUS,
                threshold=DEFAULT_QUERY_THRESHOLD,
                raw_text=cleaned,
                include_collaborative=True,
            )

        # 3. 預設維修師帶門檻查詢：「底片 < 20」、「底片門檻 20」、「底片 20張」
        threshold_match = cls.THRESHOLD_QUERY_PATTERN.match(cleaned)
        if threshold_match:
            threshold_val = int(threshold_match.group(1) or threshold_match.group(2))
            return Command(
                action="query",
                uno=DEFAULT_TECHNICIAN_UNO,
                status=0,
                threshold=threshold_val,
                raw_text=cleaned,
                include_collaborative=True,
            )

        # 4. 複合查詢：「底片 88 < 20」、「底片 88 20張」、「底片 師 88 < 20」
        combined_match = cls.COMBINED_QUERY_PATTERN.match(cleaned)
        if combined_match:
            uno = int(combined_match.group(1))
            threshold = int(combined_match.group(2) or combined_match.group(3))
            return Command(
                action="query",
                uno=uno,
                status=0,
                threshold=threshold,
                raw_text=cleaned,
            )

        # 5. 指定維修師查詢：「底片 師 88」
        technician_match = cls.TECHNICIAN_QUERY_PATTERN.match(cleaned)
        if technician_match:
            uno = int(technician_match.group(1))
            return Command(
                action="query",
                uno=uno,
                status=2,
                threshold=None,
                raw_text=cleaned,
            )

        return Command(action="unknown", raw_text=cleaned)
