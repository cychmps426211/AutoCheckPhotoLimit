import pytest
from src.bot.command_parser import CommandParser


def test_parse_default_queries():
    # 測試「底片」
    cmd1 = CommandParser.parse("底片")
    assert cmd1.action == "query"
    assert cmd1.uno == 91
    assert cmd1.status == 2
    assert cmd1.threshold is None

    # 測試「檢查底片」
    cmd2 = CommandParser.parse("檢查底片")
    assert cmd2.action == "query"
    assert cmd2.uno == 91
    assert cmd2.status == 2
    assert cmd2.threshold is None

    # 測試前後空白
    cmd3 = CommandParser.parse("  底片  ")
    assert cmd3.action == "query"
    assert cmd3.uno == 91


def test_parse_threshold_queries():
    # 測試「底片 < 20」與「檢查底片 小於 15」
    cmd1 = CommandParser.parse("底片 < 20")
    assert cmd1.action == "query"
    assert cmd1.uno == 91
    assert cmd1.threshold == 20
    assert cmd1.status == 0

    cmd2 = CommandParser.parse("檢查底片 小於 15")
    assert cmd2.action == "query"
    assert cmd2.threshold == 15
    assert cmd2.status == 0

    # 測試「底片門檻 20」、「底片門檻20」
    cmd3 = CommandParser.parse("底片門檻 20")
    assert cmd3.action == "query"
    assert cmd3.threshold == 20
    assert cmd3.status == 0

    cmd4 = CommandParser.parse("底片門檻20")
    assert cmd4.action == "query"
    assert cmd4.threshold == 20

    # 測試「底片 20張」、「底片 20 張」、「底片20張」
    cmd5 = CommandParser.parse("底片 20張")
    assert cmd5.action == "query"
    assert cmd5.threshold == 20
    assert cmd5.status == 0

    cmd6 = CommandParser.parse("底片 20 張")
    assert cmd6.action == "query"
    assert cmd6.threshold == 20

    cmd7 = CommandParser.parse("底片20張")
    assert cmd7.action == "query"
    assert cmd7.threshold == 20

    # 測試「檢查底片 30張」、「檢查底片門檻 25」
    cmd8 = CommandParser.parse("檢查底片 30張")
    assert cmd8.action == "query"
    assert cmd8.threshold == 30

    cmd9 = CommandParser.parse("檢查底片門檻 25")
    assert cmd9.action == "query"
    assert cmd9.threshold == 25

    # 測試「底片 <= 20」、「底片 < 20張」、「底片門檻 20張」
    cmd10 = CommandParser.parse("底片 <= 20")
    assert cmd10.action == "query"
    assert cmd10.threshold == 20

    cmd11 = CommandParser.parse("底片 < 20張")
    assert cmd11.action == "query"
    assert cmd11.threshold == 20

    cmd12 = CommandParser.parse("底片門檻 20張")
    assert cmd12.action == "query"
    assert cmd12.threshold == 20


def test_parse_technician_queries():
    # 測試「底片 師 88」、「底片 師88」
    cmd1 = CommandParser.parse("底片 師 88")
    assert cmd1.action == "query"
    assert cmd1.uno == 88
    assert cmd1.status == 2
    assert cmd1.threshold is None

    cmd2 = CommandParser.parse("底片 師88")
    assert cmd2.action == "query"
    assert cmd2.uno == 88
    assert cmd2.status == 2

    # 測試「底片維修師 88」、「底片維修師88」
    cmd3 = CommandParser.parse("底片維修師 88")
    assert cmd3.action == "query"
    assert cmd3.uno == 88
    assert cmd3.status == 2

    cmd4 = CommandParser.parse("底片維修師88")
    assert cmd4.action == "query"
    assert cmd4.uno == 88

    # 測試「檢查底片 師 88」、「檢查底片維修師 88」
    cmd5 = CommandParser.parse("檢查底片 師 88")
    assert cmd5.action == "query"
    assert cmd5.uno == 88
    assert cmd5.status == 2

    cmd6 = CommandParser.parse("檢查底片維修師 88")
    assert cmd6.action == "query"
    assert cmd6.uno == 88

    # 測試帶「號」後綴：「底片 師 88號」
    cmd7 = CommandParser.parse("底片 師 88號")
    assert cmd7.action == "query"
    assert cmd7.uno == 88


def test_parse_combined_queries():
    # 測試「底片 88 < 30」與「底片 88 <= 20」
    cmd1 = CommandParser.parse("底片 88 < 30")
    assert cmd1.action == "query"
    assert cmd1.uno == 88
    assert cmd1.threshold == 30
    assert cmd1.status == 0

    cmd2 = CommandParser.parse("底片 88 <= 20")
    assert cmd2.action == "query"
    assert cmd2.uno == 88
    assert cmd2.threshold == 20
    assert cmd2.status == 0

    # 測試「底片 88 小於 20」、「底片 88門檻 20」、「底片 88 門檻 20」
    cmd3 = CommandParser.parse("底片 88 小於 20")
    assert cmd3.action == "query"
    assert cmd3.uno == 88
    assert cmd3.threshold == 20

    cmd4 = CommandParser.parse("底片 88門檻 20")
    assert cmd4.action == "query"
    assert cmd4.uno == 88
    assert cmd4.threshold == 20

    cmd5 = CommandParser.parse("底片 88 門檻 20")
    assert cmd5.action == "query"
    assert cmd5.uno == 88
    assert cmd5.threshold == 20

    # 測試「底片 88 20張」、「底片 88 20 張」
    cmd6 = CommandParser.parse("底片 88 20張")
    assert cmd6.action == "query"
    assert cmd6.uno == 88
    assert cmd6.threshold == 20
    assert cmd6.status == 0

    cmd7 = CommandParser.parse("底片 88 20 張")
    assert cmd7.action == "query"
    assert cmd7.uno == 88
    assert cmd7.threshold == 20

    # 測試帶「張」後綴之門檻：「底片 88 < 20張」、「底片 88門檻 20張」
    cmd8 = CommandParser.parse("底片 88 < 20張")
    assert cmd8.action == "query"
    assert cmd8.uno == 88
    assert cmd8.threshold == 20

    cmd9 = CommandParser.parse("底片 88門檻 20張")
    assert cmd9.action == "query"
    assert cmd9.uno == 88
    assert cmd9.threshold == 20

    # 測試前綴帶「師/維修師」之複合語法
    cmd10 = CommandParser.parse("底片 師 88 < 20")
    assert cmd10.action == "query"
    assert cmd10.uno == 88
    assert cmd10.threshold == 20

    cmd11 = CommandParser.parse("底片維修師 88 門檻 20")
    assert cmd11.action == "query"
    assert cmd11.uno == 88
    assert cmd11.threshold == 20

    cmd12 = CommandParser.parse("底片 師 88 20張")
    assert cmd12.action == "query"
    assert cmd12.uno == 88
    assert cmd12.threshold == 20

    # 測試「檢查底片 88 < 20」、「檢查底片 師 88 20張」
    cmd13 = CommandParser.parse("檢查底片 88 < 20")
    assert cmd13.action == "query"
    assert cmd13.uno == 88
    assert cmd13.threshold == 20

    cmd14 = CommandParser.parse("檢查底片 師 88 20張")
    assert cmd14.action == "query"
    assert cmd14.uno == 88
    assert cmd14.threshold == 20


def test_parse_help_and_unknown():
    # 各種說明與教學指令變體
    assert CommandParser.parse("說明").action == "help"
    assert CommandParser.parse("  說明  ").action == "help"
    assert CommandParser.parse("底片 說明").action == "help"
    assert CommandParser.parse("底片說明").action == "help"
    assert CommandParser.parse("底片  說明").action == "help"
    assert CommandParser.parse("教學").action == "help"
    assert CommandParser.parse("底片教學").action == "help"
    assert CommandParser.parse("底片 教學").action == "help"
    assert CommandParser.parse("help").action == "help"
    assert CommandParser.parse("HELP").action == "help"

    # 未知與無效指令
    cmd_unk1 = CommandParser.parse("你好")
    assert cmd_unk1.action == "unknown"
    assert cmd_unk1.raw_text == "你好"

    cmd_unk2 = CommandParser.parse("天氣如何")
    assert cmd_unk2.action == "unknown"
    assert cmd_unk2.raw_text == "天氣如何"

    cmd_unk3 = CommandParser.parse("隨便查查")
    assert cmd_unk3.action == "unknown"
    assert cmd_unk3.raw_text == "隨便查查"

