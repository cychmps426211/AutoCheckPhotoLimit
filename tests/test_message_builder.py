from src.bot.message_builder import MessageBuilder, MachineStock


def test_build_stock_report_with_machines():
    machines = [
        MachineStock(machine_id="TW001", machine_name="台北站前店", remaining_sheets=5),
        MachineStock(machine_id="TW002", machine_name="板橋大遠百", remaining_sheets=18),
        MachineStock(machine_id="TW003", machine_name="台中一中街", remaining_sheets=40),
    ]

    report = MessageBuilder.build_stock_report(uno=91, machines=machines)
    assert "維修師 91 機台底片存量警報" in report
    assert "共找到 3 台機台" in report
    assert "台北站前店 (TW001)" in report
    assert "剩餘張數：5 張" in report
    assert "🔴" in report
    assert "🟠" in report
    assert "🟡" in report


def test_build_stock_report_empty():
    report = MessageBuilder.build_stock_report(uno=91, machines=[])
    assert "維修師 91 目前所有機台底片存量充足" in report


def test_build_stock_report_empty_with_threshold():
    report = MessageBuilder.build_stock_report(uno=91, machines=[], threshold=20)
    assert "維修師 91 目前負責之機台底片皆充足" in report
    assert "小於等於 20 張" in report


def test_build_stock_report_with_threshold():
    machines = [
        MachineStock(machine_id="TW001", machine_name="台北站前店", remaining_sheets=5),
        MachineStock(machine_id="TW002", machine_name="板橋大遠百", remaining_sheets=18),
    ]
    report = MessageBuilder.build_stock_report(uno=91, machines=machines, threshold=20)
    assert "維修師 91 機台底片存量警報" in report
    assert "剩餘張數 <= 20 張" in report
    assert "共找到 2 台機台需要注意" in report
    assert "台北站前店 (TW001)" in report
    assert "剩餘張數：5 張" in report
    assert "板橋大遠百 (TW002)" in report
    assert "剩餘張數：18 張" in report


def test_build_help_message():
    help_msg = MessageBuilder.build_help_message()
    assert "機台底片存量查詢指令說明" in help_msg
    assert "底片" in help_msg
