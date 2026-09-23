import re
from dataclasses import dataclass
from typing import Optional

from src.config import (
    DEFAULT_TECHNICIAN_UNO,
    DEFAULT_QUERY_STATUS,
    DEFAULT_QUERY_THRESHOLD,
    DUTY_AREA_NO,
)


@dataclass
class Command:
    action: str  # "query", "duty_query", "help", "unknown"
    uno: int = DEFAULT_TECHNICIAN_UNO
    status: int = DEFAULT_QUERY_STATUS  # 0: 全部, 2: 接近底限
    threshold: Optional[int] = None
    raw_text: str = ""
    include_collaborative: bool = False
    area: int = 0


class CommandParser:
    """
    維修師自然語言指令解析器
    支援語法：
    - 「底片」、「檢查底片」 -> 預設維修師 (91)，全部狀態門檻 20 (status=0, threshold=20)
    - 「底片 < 20」 -> 預設維修師 (91)，門檻 20 (status=0)
    - 「值班」、「值班底片」、「值班底片殘量」 -> 南區 (area=46)，全部狀態門檻 20
    - 「值班 < 20」、「值班底片 < 20」 -> 南區 (area=46)，門檻 20
    - 「說明」、「底片說明」、「底片 說明」、「help」 -> 幫助教學
    """

    # 說明指令
    HELP_PATTERN = re.compile(r"^(?:底片\s*(?:說明|教學)|說明|教學|help)$", re.IGNORECASE)

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

    @classmethod
    def parse(cls, text: str) -> Command:
        cleaned = text.strip()

        # 1. 說明指令
        if cls.HELP_PATTERN.match(cleaned):
            return Command(action="help", raw_text=cleaned)

        # 2. 值班查詢：「值班」、「值班底片」、「值班底片殘量」等
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
