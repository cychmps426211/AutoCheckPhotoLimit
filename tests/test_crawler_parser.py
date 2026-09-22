import pytest
from src.crawler.paper_crawler import PaperCrawler
from src.bot.message_builder import MachineStock


MOCK_HTML_TABLE = """
<table>
    <thead>
        <tr>
            <th>#</th>
            <th>機台編號名稱</th>
            <th>維修師</th>
            <th>剩餘數量</th>
            <th>底片底限</th>
            <th>近三日</th>
            <th>差距</th>
            <th>更新時間</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>1</td>
            <td>ABC001<br>台北旗艦店</td>
            <td>蘇上豪</td>
            <td>45</td>
            <td>5</td>
            <td>0</td>
            <td>40</td>
            <td>2026-09-21 12:00:00</td>
            <td></td>
        </tr>
        <tr>
            <td>2</td>
            <td>ABC002<br>台中新時代</td>
            <td>蘇上豪</td>
            <td>8</td>
            <td>5</td>
            <td>0</td>
            <td>3</td>
            <td>2026-09-21 12:00:00</td>
            <td></td>
        </tr>
        <tr>
            <td>3</td>
            <td>ABC003<br>高雄巨蛋店</td>
            <td>蘇上豪</td>
            <td>19</td>
            <td>5</td>
            <td>0</td>
            <td>14</td>
            <td>2026-09-21 12:00:00</td>
            <td></td>
        </tr>
    </tbody>
</table>
"""


def test_parse_html_table_urgency_sorting():
    # 測試解析與緊急排序（8, 19, 45 升冪）
    machines = PaperCrawler.parse_html_table(MOCK_HTML_TABLE)
    assert len(machines) == 3
    assert machines[0].machine_id == "ABC002"
    assert machines[0].remaining_sheets == 8
    assert machines[1].machine_id == "ABC003"
    assert machines[1].remaining_sheets == 19
    assert machines[2].machine_id == "ABC001"
    assert machines[2].remaining_sheets == 45


def test_parse_html_table_threshold_filtering():
    # 測試門檻過濾（<= 20 張，只保留 8 與 19）
    machines = PaperCrawler.parse_html_table(MOCK_HTML_TABLE, threshold=20)
    assert len(machines) == 2
    assert machines[0].machine_id == "ABC002"
    assert machines[0].remaining_sheets == 8
    assert machines[1].machine_id == "ABC003"
    assert machines[1].remaining_sheets == 19


def test_fetch_machine_stock_with_mock_session(mocker):
    # 測試透過 API 取得資料並排序
    mock_session = mocker.MagicMock()
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"CodeNo": "M3", "ShopName": "台南店", "Paper": "50"},
        {"CodeNo": "M1", "ShopName": "台北店", "Paper": "2"},
        {"CodeNo": "M2", "ShopName": "台中店", "Paper": "15"},
    ]
    mock_session.post.return_value = mock_resp

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(uno=91, status=2)

    assert len(results) == 3
    assert results[0].machine_id == "M1"
    assert results[0].remaining_sheets == 2
    assert results[1].machine_id == "M2"
    assert results[1].remaining_sheets == 15
    assert results[2].machine_id == "M3"
    assert results[2].remaining_sheets == 50


def test_fetch_machine_stock_with_threshold(mocker):
    # 測試透過 API 請求並在記憶體中進行門檻過濾與排序
    mock_session = mocker.MagicMock()
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"CodeNo": "M3", "ShopName": "台南店", "Paper": "50"},
        {"CodeNo": "M1", "ShopName": "台北店", "Paper": "2"},
        {"CodeNo": "M2", "ShopName": "台中店", "Paper": "15"},
    ]
    mock_session.post.return_value = mock_resp

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    # 門檻 15：應保留 M1 (2) 與 M2 (15)，排除 M3 (50)
    results = crawler.fetch_machine_stock(uno=91, status=0, threshold=15)

    assert len(results) == 2
    assert results[0].machine_id == "M1"
    assert results[0].remaining_sheets == 2
    assert results[1].machine_id == "M2"
    assert results[1].remaining_sheets == 15


def test_fetch_machine_stock_threshold_empty(mocker):
    # 測試門檻過低時回傳空清單 (0 台符合)
    mock_session = mocker.MagicMock()
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"CodeNo": "M3", "ShopName": "台南店", "Paper": "50"},
        {"CodeNo": "M2", "ShopName": "台中店", "Paper": "15"},
    ]
    mock_session.post.return_value = mock_resp

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(uno=91, status=0, threshold=5)

    assert results == []


def test_fetch_machine_stock_technician_not_found_status_0(mocker):
    """驗證 status=0 查無任何機台時拋出 TechnicianNotFoundError"""
    from src.crawler.paper_crawler import TechnicianNotFoundError

    mock_session = mocker.MagicMock()
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_session.post.return_value = mock_resp

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    with pytest.raises(TechnicianNotFoundError) as exc_info:
        crawler.fetch_machine_stock(uno=88, status=0)

    assert exc_info.value.uno == 88


def test_fetch_machine_stock_technician_not_found_status_2(mocker):
    """驗證 status=2 且確認 status=0 亦無機台時拋出 TechnicianNotFoundError"""
    from src.crawler.paper_crawler import TechnicianNotFoundError

    mock_session = mocker.MagicMock()
    mock_resp_empty = mocker.MagicMock()
    mock_resp_empty.status_code = 200
    mock_resp_empty.json.return_value = []
    mock_session.post.return_value = mock_resp_empty

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    with pytest.raises(TechnicianNotFoundError) as exc_info:
        crawler.fetch_machine_stock(uno=88, status=2)

    assert exc_info.value.uno == 88


def test_fetch_machine_stock_all_sufficient_status_2(mocker):
    """驗證 status=2 為空但名下有機台 (status=0 有資料) 時回傳空清單（代表皆充足）"""
    mock_session = mocker.MagicMock()
    mock_resp_status2 = mocker.MagicMock()
    mock_resp_status2.status_code = 200
    mock_resp_status2.text = "[]"
    mock_resp_status2.json.return_value = []

    mock_resp_status0 = mocker.MagicMock()
    mock_resp_status0.status_code = 200
    mock_resp_status0.text = '[{"CodeNo": "M1"}]'
    mock_resp_status0.json.return_value = [
        {"CodeNo": "M1", "ShopName": "台北站前店", "Paper": "80"},
    ]

    # 第一次 post (status=2) 回傳空，第二次 post (status=0) 回傳機台
    mock_session.post.side_effect = [mock_resp_status2, mock_resp_status0]

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(uno=91, status=2)

    assert results == []


def test_fetch_machine_stock_existence_check_failure(mocker):
    """驗證 status=2 為空且次級查詢異常時不靜默忽略，而是拋出 RuntimeError"""
    mock_session = mocker.MagicMock()
    mock_resp_status2 = mocker.MagicMock()
    mock_resp_status2.status_code = 200
    mock_resp_status2.text = "[]"
    mock_resp_status2.json.return_value = []

    mock_resp_fail = mocker.MagicMock()
    mock_resp_fail.status_code = 500
    mock_resp_fail.text = "Internal Error"

    mock_session.post.side_effect = [mock_resp_status2, mock_resp_fail]

    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    with pytest.raises(RuntimeError) as exc_info:
        crawler.fetch_machine_stock(uno=91, status=2)

    assert "無法驗證維修師機台資訊" in str(exc_info.value)


def test_fetch_machine_stock_collaborative_merged_and_sorted(mocker):
    """驗證 include_collaborative=True 時，合併 uno=91 與 uno=19 目標機台，並過濾非目標機台且緊急排序"""
    mock_session = mocker.MagicMock()

    # uno=91 回傳 1 台機台 (sheets=18)
    mock_resp_91 = mocker.MagicMock()
    mock_resp_91.status_code = 200
    mock_resp_91.json.return_value = [
        {"CodeNo": "M91", "ShopName": "台南總店", "Paper": "18"},
    ]

    # uno=19 回傳 3 台機台：其中 2 台在目標名單內，1 台不在
    mock_resp_19 = mocker.MagicMock()
    mock_resp_19.status_code = 200
    mock_resp_19.json.return_value = [
        {"CodeNo": "ABC074-ND", "ShopName": "寶雅高雄文信", "Paper": "5"},
        {"CodeNo": "OTHER-99", "ShopName": "非協同機台", "Paper": "2"},
        {"CodeNo": "ABC079-ST", "ShopName": "寶雅高雄灣內店", "Paper": "22"},
    ]

    def mock_post(url, data, **kwargs):
        user_no = data.get("UserNo")
        if user_no == 91:
            return mock_resp_91
        elif user_no == 19:
            return mock_resp_19
        resp = mocker.MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    mock_session.post.side_effect = mock_post
    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(uno=91, status=2, include_collaborative=True)

    # 應只包含 M91、ABC074-ND、ABC079-ST，OTHER-99 被濾除
    assert len(results) == 3
    assert [m.machine_id for m in results] == ["ABC074-ND", "M91", "ABC079-ST"]
    assert [m.remaining_sheets for m in results] == [5, 18, 22]


def test_fetch_machine_stock_collaborative_threshold(mocker):
    """驗證門檻過濾 (threshold) 在合併主維修師與協同機台時均生效"""
    mock_session = mocker.MagicMock()

    mock_resp_91 = mocker.MagicMock()
    mock_resp_91.status_code = 200
    mock_resp_91.json.return_value = [
        {"CodeNo": "M91_A", "ShopName": "台南店A", "Paper": "8"},
        {"CodeNo": "M91_B", "ShopName": "台南店B", "Paper": "25"},
    ]

    mock_resp_19 = mocker.MagicMock()
    mock_resp_19.status_code = 200
    mock_resp_19.json.return_value = [
        {"CodeNo": "ABC074-ND", "ShopName": "寶雅高雄文信", "Paper": "6"},
        {"CodeNo": "ABC079-ST", "ShopName": "寶雅高雄灣內店", "Paper": "15"},
    ]

    def mock_post(url, data, **kwargs):
        user_no = data.get("UserNo")
        if user_no == 91:
            return mock_resp_91
        elif user_no == 19:
            return mock_resp_19
        resp = mocker.MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    mock_session.post.side_effect = mock_post
    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(
        uno=91, status=0, threshold=10, include_collaborative=True
    )

    # 門檻 <= 10：保留 ABC074-ND (6) 與 M91_A (8)
    assert len(results) == 2
    assert results[0].machine_id == "ABC074-ND"
    assert results[0].remaining_sheets == 6
    assert results[1].machine_id == "M91_A"
    assert results[1].remaining_sheets == 8


def test_fetch_machine_stock_collaborative_error_handled_gracefully(mocker):
    """驗證協同機台後台查詢異常時，不中斷主維修師機台結果"""
    mock_session = mocker.MagicMock()

    mock_resp_91 = mocker.MagicMock()
    mock_resp_91.status_code = 200
    mock_resp_91.json.return_value = [
        {"CodeNo": "M91", "ShopName": "台南店", "Paper": "12"},
    ]

    def mock_post(url, data, **kwargs):
        user_no = data.get("UserNo")
        if user_no == 91:
            return mock_resp_91
        elif user_no == 19:
            raise RuntimeError("Seiwa API timeout for uno 19")
        resp = mocker.MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    mock_session.post.side_effect = mock_post
    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(uno=91, status=2, include_collaborative=True)

    assert len(results) == 1
    assert results[0].machine_id == "M91"
    assert results[0].remaining_sheets == 12


def test_fetch_machine_stock_collaborative_deduplication(mocker):
    """驗證當主維修師與協同維修師後台均回傳同一機台代號時，去重僅保留第一筆"""
    mock_session = mocker.MagicMock()

    mock_resp_91 = mocker.MagicMock()
    mock_resp_91.status_code = 200
    mock_resp_91.json.return_value = [
        {"CodeNo": "ABC074-ND", "ShopName": "寶雅高雄文信(主)", "Paper": "8"},
    ]

    mock_resp_19 = mocker.MagicMock()
    mock_resp_19.status_code = 200
    mock_resp_19.json.return_value = [
        {"CodeNo": "ABC074-ND", "ShopName": "寶雅高雄文信(協同)", "Paper": "15"},
    ]

    def mock_post(url, data, **kwargs):
        user_no = data.get("UserNo")
        if user_no == 91:
            return mock_resp_91
        elif user_no == 19:
            return mock_resp_19
        resp = mocker.MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    mock_session.post.side_effect = mock_post
    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    results = crawler.fetch_machine_stock(uno=91, status=2, include_collaborative=True)

    assert len(results) == 1
    assert results[0].machine_id == "ABC074-ND"
    assert results[0].machine_name == "寶雅高雄文信(主)"
    assert results[0].remaining_sheets == 8


def test_fetch_machine_stock_collaborative_guard_non_default_technician(mocker):
    """驗證非預設維修師（例如 uno=88）即使被傳入 include_collaborative=True，亦不會混入協同機台"""
    mock_session = mocker.MagicMock()

    mock_resp_88 = mocker.MagicMock()
    mock_resp_88.status_code = 200
    mock_resp_88.json.return_value = [
        {"CodeNo": "M88", "ShopName": "台南安平店", "Paper": "10"},
    ]

    mock_resp_19 = mocker.MagicMock()
    mock_resp_19.status_code = 200
    mock_resp_19.json.return_value = [
        {"CodeNo": "ABC074-ND", "ShopName": "寶雅高雄文信", "Paper": "3"},
    ]

    def mock_post(url, data, **kwargs):
        user_no = data.get("UserNo")
        if user_no == 88:
            return mock_resp_88
        elif user_no == 19:
            return mock_resp_19
        resp = mocker.MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    mock_session.post.side_effect = mock_post
    mock_mgr = mocker.MagicMock()
    mock_mgr.get_authenticated_session.return_value = mock_session

    crawler = PaperCrawler(session_manager=mock_mgr)
    # uno=88 查詢
    results = crawler.fetch_machine_stock(uno=88, status=2, include_collaborative=True)

    # 協同機台 uno=19 不應被包含在維修師 88 的查詢結果中
    assert len(results) == 1
    assert results[0].machine_id == "M88"
    assert results[0].remaining_sheets == 10
