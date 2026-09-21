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
