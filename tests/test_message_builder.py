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


def test_build_stock_report_dynamic_uno():
    """驗證跨維修師查詢時，訊息抬頭動態反映 uno 代號"""
    machines = [
        MachineStock(machine_id="TW088", machine_name="高雄夢時代", remaining_sheets=12),
    ]
    report = MessageBuilder.build_stock_report(uno=88, machines=machines)
    assert "維修師 88 機台底片存量警報" in report
    assert "高雄夢時代 (TW088)" in report
    assert "剩餘張數：12 張" in report


def test_build_stock_report_dynamic_uno_empty():
    """驗證跨維修師無缺紙機台時之動態 uno 抬頭"""
    report = MessageBuilder.build_stock_report(uno=88, machines=[])
    assert "維修師 88 目前所有機台底片存量充足" in report

    report_thresh = MessageBuilder.build_stock_report(uno=88, machines=[], threshold=15)
    assert "維修師 88 目前負責之機台底片皆充足" in report_thresh
    assert "小於等於 15 張" in report_thresh


def test_build_technician_not_found_message():
    """驗證查無維修師或無效編號之提示訊息"""
    msg = MessageBuilder.build_technician_not_found_message(88)
    assert "查無維修師 88 負責之機台資料" in msg
    assert "請確認維修師編號是否正確" in msg


def test_build_help_message():
    help_msg = MessageBuilder.build_help_message()
    assert "機台底片存量查詢指令說明" in help_msg
    assert "預設查詢" in help_msg
    assert "底片" in help_msg
    assert "門檻查詢" in help_msg
    assert "底片 < 20" in help_msg
    assert "指定維修師查詢" in help_msg
    assert "底片 師 88" in help_msg
    assert "複合查詢" in help_msg
    assert "底片 88 < 20" in help_msg
    assert "教學說明" in help_msg
    assert "說明" in help_msg


def test_build_unknown_message():
    msg = MessageBuilder.build_unknown_message("未知測試字串")
    assert "無法辨識指令：「未知測試字串」" in msg
    assert "輸入「底片」" in msg
    assert "輸入「說明」" in msg


def test_build_circuit_breaker_message():
    msg = MessageBuilder.build_circuit_breaker_message()
    assert "熔斷保護已啟動" in msg
    assert "連續失敗達 3 次" in msg
    assert "暫停重複登入重試" in msg
    assert "稍候（約 1 分鐘後）再試" in msg
