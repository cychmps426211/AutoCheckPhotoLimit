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
