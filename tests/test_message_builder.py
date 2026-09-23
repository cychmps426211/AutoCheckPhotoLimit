from src.bot.message_builder import MessageBuilder, MachineStock


def test_build_stock_report_with_machines():
    machines = [
        MachineStock(machine_id="TW001", machine_name="台北站前店", remaining_sheets=5),
        MachineStock(machine_id="TW002", machine_name="板橋大遠百", remaining_sheets=18),
        MachineStock(machine_id="TW003", machine_name="台中一中街", remaining_sheets=40),
    ]

    report = MessageBuilder.build_stock_report(uno=91, machines=machines)
    assert "機台底片存量警報" in report
    assert "共找到 3 台機台" in report
    assert "台北站前店 (TW001)" in report
    assert "剩餘張數：5 張" in report
    assert "🔴" in report
    assert "🟠" in report
    assert "🟡" in report


def test_build_stock_report_empty():
    report = MessageBuilder.build_stock_report(uno=91, machines=[])
    assert "目前所有機台底片存量充足" in report


def test_build_stock_report_empty_with_threshold():
    report = MessageBuilder.build_stock_report(uno=91, machines=[], threshold=20)
    assert "目前負責之機台底片皆充足" in report
    assert "小於等於 20 張" in report


def test_build_stock_report_with_threshold():
    machines = [
        MachineStock(machine_id="TW001", machine_name="台北站前店", remaining_sheets=5),
        MachineStock(machine_id="TW002", machine_name="板橋大遠百", remaining_sheets=18),
    ]
    report = MessageBuilder.build_stock_report(uno=91, machines=machines, threshold=20)
    assert "機台底片存量警報" in report
    assert "剩餘張數 <= 20 張" in report
    assert "共找到 2 台機台需要注意" in report
    assert "台北站前店 (TW001)" in report
    assert "剩餘張數：5 張" in report
    assert "板橋大遠百 (TW002)" in report
    assert "剩餘張數：18 張" in report


def test_build_stock_report_dynamic_uno():
    """驗證跨維修師查詢時正常產生存量警報"""
    machines = [
        MachineStock(machine_id="TW088", machine_name="高雄夢時代", remaining_sheets=12),
    ]
    report = MessageBuilder.build_stock_report(uno=88, machines=machines)
    assert "機台底片存量警報" in report
    assert "高雄夢時代 (TW088)" in report
    assert "剩餘張數：12 張" in report


def test_build_stock_report_dynamic_uno_empty():
    """驗證跨維修師無缺紙機台時之充足提示"""
    report = MessageBuilder.build_stock_report(uno=88, machines=[])
    assert "目前所有機台底片存量充足" in report

    report_thresh = MessageBuilder.build_stock_report(uno=88, machines=[], threshold=15)
    assert "目前負責之機台底片皆充足" in report_thresh
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
    assert "輸入「說明」" in msg


def test_build_circuit_breaker_message():
    msg = MessageBuilder.build_circuit_breaker_message()
    assert "熔斷保護已啟動" in msg
    assert "連續失敗達 3 次" in msg
    assert "暫停重複登入重試" in msg
    assert "稍候（約 1 分鐘後）再試" in msg


def test_build_duty_stock_report_with_machines():
    machines = [
        MachineStock(
            machine_id="ABC461-ND",
            machine_name="台南第一診所",
            remaining_sheets=0,
            in_charge="蕭睿呈",
        ),
        MachineStock(
            machine_id="ABC192-ST",
            machine_name="小港第二辦公處",
            remaining_sheets=6,
            in_charge="蘇上豪",
        ),
        MachineStock(
            machine_id="ABC099-XX",
            machine_name="鳳山自強站",
            remaining_sheets=15,
        ),
    ]

    report = MessageBuilder.build_duty_stock_report(
        area_name="南區", machines=machines, threshold=20
    )
    assert "南區值班 機台底片存量警報" in report
    assert "剩餘張數 <= 20 張" in report
    assert "共找到 3 台機台需要注意" in report
    assert "台南第一診所 (ABC461-ND) [負責維修師: 蕭睿呈]" in report
    assert "小港第二辦公處 (ABC192-ST) [負責維修師: 蘇上豪]" in report
    assert "鳳山自強站 (ABC099-XX)" in report


def test_build_duty_stock_report_empty():
    report = MessageBuilder.build_duty_stock_report(
        area_name="南區", machines=[], threshold=20
    )
    assert "南區值班 目前負責機台底片皆充足" in report
    assert "小於等於 20 張" in report

    report_no_thresh = MessageBuilder.build_duty_stock_report(
        area_name="南區", machines=[]
    )
    assert "南區值班 目前所有機台底片存量充足" in report_no_thresh


def test_build_help_message_includes_duty():
    help_msg = MessageBuilder.build_help_message()
    assert "值班" in help_msg
    assert "值班底片" in help_msg
    assert "南區" in help_msg
    assert "行程" in help_msg


def test_build_schedule_report_with_items():
    import datetime
    from src.crawler.schedule_crawler import ScheduleItem

    items = [
        ScheduleItem(order=1, machine_id="ABC061-ST", machine_name="高雄楠梓監理", time_str="08:15"),
        ScheduleItem(order=2, machine_id="ABC197-ST", machine_name="旗津辦公處", time_str="09:13"),
    ]
    target_date = datetime.date(2026, 9, 23)
    report = MessageBuilder.build_schedule_report(uno=91, target_date=target_date, items=items)

    assert "維護行程" in report
    assert "2026-09-23" in report
    assert "共 2 處維護紀錄" in report
    assert "1. 08:15 ABC061-ST 高雄楠梓監理" in report
    assert "2. 09:13 ABC197-ST 旗津辦公處" in report


def test_build_schedule_report_empty():
    import datetime
    target_date = datetime.date(2026, 9, 24)
    report = MessageBuilder.build_schedule_report(uno=91, target_date=target_date, items=[])

    assert "維護行程" in report
    assert "2026-09-24" in report
    assert "本日無任何維護行程紀錄" in report


def test_build_invalid_schedule_date_message():
    msg = MessageBuilder.build_invalid_schedule_date_message("行程 9999")
    assert "日期格式不正確" in msg
    assert "行程 9999" in msg
    assert "行程 0922" in msg

