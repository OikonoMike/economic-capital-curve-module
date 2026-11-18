import pytest
from src.calculator_client import CalculatorClient


class TestCalculatorClientStub:
    def test_stub_send(self):
        client = CalculatorClient(use_stub=True)
        result = client.send_curves(
            run_id=1,
            report_date="2026-11-10",
            curves_data=[{"tenor": "1y", "rate": 14.0}],
        )
        assert result["status"] == "ok"
        assert result["response"]["curves_received"] == 1

    def test_stub_without_url(self):
        """Заглушка должна работать даже без CALCULATOR_API_URL"""
        client = CalculatorClient(use_stub=True, base_url=None)
        result = client.send_curves(1, "2026-11-10", [])
        assert result["status"] == "ok"


class TestCalculatorClientReal:
    def test_missing_url_raises(self):
        """Без URL и без заглушки должен быть ValueError"""
        with pytest.raises(ValueError):
            CalculatorClient(use_stub=False, base_url=None)

    def test_invalid_url_returns_error(self):
        """Невалидный URL должен вернуть error после retries"""
        client = CalculatorClient(
            base_url="http://invalid-host-12345:9999",
            retries=1,
            timeout=1.0,
        )
        result = client.send_curves(1, "2026-11-10", [])
        assert result["status"] == "error"