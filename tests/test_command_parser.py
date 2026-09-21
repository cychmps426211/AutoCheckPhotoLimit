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
    # 測試「底片 < 20」
    cmd1 = CommandParser.parse("底片 < 20")
    assert cmd1.action == "query"
    assert cmd1.uno == 91
    assert cmd1.threshold == 20
    assert cmd1.status == 0

    # 測試「檢查底片 小於 15」
    cmd2 = CommandParser.parse("檢查底片 小於 15")
    assert cmd2.action == "query"
    assert cmd2.threshold == 15
    assert cmd2.status == 0


def test_parse_technician_queries():
    cmd = CommandParser.parse("底片 師 88")
    assert cmd.action == "query"
    assert cmd.uno == 88
    assert cmd.status == 2
    assert cmd.threshold is None


def test_parse_combined_queries():
    cmd = CommandParser.parse("底片 88 < 30")
    assert cmd.action == "query"
    assert cmd.uno == 88
    assert cmd.threshold == 30
    assert cmd.status == 0


def test_parse_help_and_unknown():
    assert CommandParser.parse("說明").action == "help"
    assert CommandParser.parse("底片 說明").action == "help"
    assert CommandParser.parse("help").action == "help"
    assert CommandParser.parse("你好").action == "unknown"
