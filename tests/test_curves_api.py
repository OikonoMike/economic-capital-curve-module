from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from src.curves_api.main import app
from src.curves_api.database import get_db


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params):
        return FakeResult(self.rows)


sample_row = {
    "report_date": date(2026, 10, 30),
    "scenario_id": 0,
    "scenario_code": "BASE",
    "tenor_label": "1Y",
    "tenor_years": 1.0,
    "t_mid_years": 1.0,
    "rate_pct": 10.5,
    "discount_factor": 0.9,
    "method": "moex",
    "is_interpolated": False,
    "is_extrapolated": False,
    "calculated_at": datetime(2026, 10, 30, tzinfo=timezone.utc),
    "run_type": "manual",
    "started_by": "test",
    "started_at": datetime(2026, 10, 30, tzinfo=timezone.utc),
}


def test_get_curves_success():
    app.dependency_overrides[get_db] = lambda: FakeConnection([sample_row])

    try:
        client = TestClient(app)
        response = client.get("/curves?date=2026-10-30")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["scenario_id"] == 0
        assert response.json()[0]["scenario_code"] == "BASE"
    finally:
        app.dependency_overrides.clear()


def test_get_curves_invalid_date():
    client = TestClient(app)

    response = client.get("/curves?date=30-10-2026")

    assert response.status_code == 400


def test_get_curves_not_found():
    app.dependency_overrides[get_db] = lambda: FakeConnection([])

    try:
        client = TestClient(app)
        response = client.get("/curves?date=2026-10-30")

        assert response.status_code == 404
        assert "не найдены" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()