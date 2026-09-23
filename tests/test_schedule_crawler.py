import datetime
from unittest.mock import MagicMock
import pytest

from src.crawler.schedule_crawler import ScheduleCrawler, ScheduleItem
from src.auth.circuit_breaker import CircuitBreakerError


SAMPLE_CALENDAR_HTML = """
<table class="table table-bordered table-striped bg-white">
    <thead>
        <tr>
            <th>日</th><th>一</th><th>二</th><th>三</th><th>四</th><th>五</th><th>六</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td class="text-center"><a href="ReportList.php?uno=91&d=2026-09-20">09/20</a></td>
            <td class="text-center"><a href="ReportList.php?uno=91&d=2026-09-21">09/21</a></td>
            <td class="text-center"><a href="ReportList.php?uno=91&d=2026-09-22">09/22</a></td>
            <td class="text-center"><a href="ReportList.php?uno=91&d=2026-09-23">09/23</a></td>
            <td class="text-center">09/24</td>
            <td class="text-center">09/25</td>
            <td class="text-center">09/26</td>
        </tr>
        <tr>
            <td>
                <div>1. ABC232-ST</div>
                <div class="pl-3"><a href="ReportView.php?no=14306">旗津一</a></div>
                <div class="pl-3 mb-2 color-purple">09:13</div>
            </td>
            <td></td>
            <td>
                <div>1. ABC197-ST</div>
                <div class="pl-3"><a href="ReportView.php?no=14417">旗津辦公處</a></div>
                <div class="pl-3 mb-2 color-purple">09:13</div>
                <div>2. ABC192-ST</div>
                <div class="pl-3"><a href="ReportView.php?no=14419">旗津第二辦公處</a></div>
                <div class="pl-3 mb-2 color-purple">09:27</div>
                <div>3. ABC220-ST</div>
                <div class="pl-3">仁武</div>
                <div class="pl-3 mb-2 color-purple">15:30</div>
            </td>
            <td>
                <div>1. ABC061-ST</div>
                <div class="pl-3"><a href="ReportView.php?no=14502">高雄楠梓監理</a></div>
                <div class="pl-3 mb-2 color-purple">08:15</div>
            </td>
            <td></td>
            <td></td>
            <td></td>
        </tr>
    </tbody>
</table>
"""


class TestScheduleCrawler:
    def test_parse_schedule_table_multiple_items(self):
        target = datetime.date(2026, 9, 22)
        items = ScheduleCrawler.parse_schedule_table(SAMPLE_CALENDAR_HTML, target)
        assert len(items) == 3
        assert items[0] == ScheduleItem(
            order=1,
            machine_id="ABC197-ST",
            machine_name="旗津辦公處",
            time_str="09:13",
        )
        assert items[1] == ScheduleItem(
            order=2,
            machine_id="ABC192-ST",
            machine_name="旗津第二辦公處",
            time_str="09:27",
        )
        assert items[2] == ScheduleItem(
            order=3,
            machine_id="ABC220-ST",
            machine_name="仁武",
            time_str="15:30",
        )

    def test_parse_schedule_table_single_item(self):
        target = datetime.date(2026, 9, 23)
        items = ScheduleCrawler.parse_schedule_table(SAMPLE_CALENDAR_HTML, target)
        assert len(items) == 1
        assert items[0] == ScheduleItem(
            order=1,
            machine_id="ABC061-ST",
            machine_name="高雄楠梓監理",
            time_str="08:15",
        )

    def test_parse_schedule_table_empty_day(self):
        target = datetime.date(2026, 9, 24)
        items = ScheduleCrawler.parse_schedule_table(SAMPLE_CALENDAR_HTML, target)
        assert items == []

    def test_parse_schedule_table_date_not_in_table(self):
        target = datetime.date(2026, 8, 1)
        items = ScheduleCrawler.parse_schedule_table(SAMPLE_CALENDAR_HTML, target)
        assert items == []

    def test_parse_schedule_table_malformed_html(self):
        items = ScheduleCrawler.parse_schedule_table("<div>No table here</div>", datetime.date(2026, 9, 22))
        assert items == []

    def test_fetch_schedule_success(self):
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_CALENDAR_HTML
        mock_resp.url = "https://dl02.seiwainc.com.tw/pc/Maintenance/UserMonth.php?uno=91&m1=2026-09"
        mock_session.get.return_value = mock_resp
        mock_session_manager.get_authenticated_session.return_value = mock_session

        crawler = ScheduleCrawler(session_manager=mock_session_manager)
        target = datetime.date(2026, 9, 22)
        items = crawler.fetch_schedule(uno=91, target_date=target)

        assert len(items) == 3
        mock_session.get.assert_called_once()
        called_url = mock_session.get.call_args[0][0]
        assert "uno=91" in called_url
        assert "m1=2026-09" in called_url

    def test_fetch_schedule_retry_on_session_expiry(self):
        mock_session_manager = MagicMock()
        mock_session = MagicMock()

        # First request redirected to 500.html
        resp_expired = MagicMock()
        resp_expired.status_code = 302
        resp_expired.url = "https://dl02.seiwainc.com.tw/Common/500.html"
        resp_expired.text = "Redirecting..."

        # Second request success
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.url = "https://dl02.seiwainc.com.tw/pc/Maintenance/UserMonth.php"
        resp_ok.text = SAMPLE_CALENDAR_HTML

        mock_session.get.side_effect = [resp_expired, resp_ok]
        mock_session_manager.get_authenticated_session.return_value = mock_session

        crawler = ScheduleCrawler(session_manager=mock_session_manager)
        items = crawler.fetch_schedule(uno=91, target_date=datetime.date(2026, 9, 23))

        assert len(items) == 1
        assert mock_session_manager.login.called
        assert mock_session.get.call_count == 2

    def test_parse_schedule_real_snapshot(self):
        from pathlib import Path
        sample_path = Path(__file__).resolve().parent.parent / ".scratch" / "usermonth_sample.html"
        if not sample_path.exists():
            pytest.skip("No real snapshot file available")

        html = sample_path.read_text(encoding="utf-8")
        items_0922 = ScheduleCrawler.parse_schedule_table(html, datetime.date(2026, 9, 22))
        assert len(items_0922) == 10
        assert items_0922[0].machine_id == "ABC197-ST"
        assert items_0922[0].time_str == "09:13"
        assert items_0922[-1].machine_id == "ABC220-ST"
        assert items_0922[-1].time_str == "15:30"

        items_0923 = ScheduleCrawler.parse_schedule_table(html, datetime.date(2026, 9, 23))
        assert len(items_0923) == 1
        assert items_0923[0].machine_id == "ABC061-ST"
        assert items_0923[0].time_str == "08:15"

