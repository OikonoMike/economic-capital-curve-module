import pytest
from datetime import time, date
from src.data_checks import (
    check_tenors, check_rates, check_tradetime,
    check_report_date, run_all_checks, EXPECTED_TENORS
)


class TestCheckTenors:
    def test_all_present(self):
        points = [(t, 14.0) for t in EXPECTED_TENORS]
        status, details = check_tenors(points)
        assert status == 'ok'

    def test_missing_one(self):
        points = [(t, 14.0) for t in EXPECTED_TENORS if t != 5.0]
        status, details = check_tenors(points)
        assert status == 'error'
        assert '5.0' in details


class TestCheckRates:
    def test_valid(self):
        points = [(1.0, 14.5), (5.0, 15.2)]
        status, _ = check_rates(points)
        assert status == 'ok'

    def test_negative(self):
        points = [(1.0, -1.0)]
        status, _ = check_rates(points)
        assert status == 'error'

    def test_too_high(self):
        points = [(1.0, 51.0)]
        status, _ = check_rates(points)
        assert status == 'error'


class TestCheckTradetime:
    def test_valid(self):
        assert check_tradetime(time(18, 49))[0] == 'ok'

    def test_too_early(self):
        assert check_tradetime(time(18, 00))[0] == 'error'

    def test_unknown(self):
        assert check_tradetime(None)[0] == 'error'


class TestCheckReportDate:
    def test_match(self):
        d = date(2026, 11, 10)
        assert check_report_date(d, d)[0] == 'ok'

    def test_mismatch(self):
        assert check_report_date(date(2026, 11, 9), date(2026, 11, 10))[0] == 'error'


class TestRunAllChecks:
    def test_all_ok(self):
        points = [(t, 14.0) for t in EXPECTED_TENORS]
        result = run_all_checks(points, time(18, 49), date(2026, 11, 10), date(2026, 11, 10))
        assert result['all_ok'] is True
        assert result['error_summary'] is None

    def test_one_error(self):
        points = [(t, 14.0) for t in EXPECTED_TENORS]
        result = run_all_checks(points, time(17, 00), date(2026, 11, 10), date(2026, 11, 10))
        assert result['all_ok'] is False
        assert 'tradetime' in result['error_summary']