from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.curves_api.database import get_db
from src.curves_api.main import app
from src.curves_api.routers import curve_parser
from src.data_checks import EXPECTED_TENORS
from src.interpolate_curve import GRID, SCENARIO_CODES
from src.moex_loader.database import Base, CalendarDay, CurveRun, Scenario, TenorGrid

D1 = "2026-11-19"
D2 = "2026-11-20"
WEEKEND = "2026-11-21"


@pytest.fixture
def provider(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'curves.db'}"
    db = create_engine(db_url)
    Base.metadata.create_all(db)
    sql = (Path(__file__).parents[1] / "db/init/01_create_schema.sql").read_text()
    view = sql.split("CREATE OR REPLACE VIEW curve_latest AS", 1)[1].split(";", 1)[0]
    with db.begin() as conn:
        conn.exec_driver_sql(f"CREATE VIEW curve_latest AS{view}")
    with Session(db) as session:
        session.add_all(Scenario(scenario_id=i, code=code, name_ru=code)
                        for i, code in enumerate(("base", *SCENARIO_CODES)))
        session.add_all(TenorGrid(tenor_label=label, order_no=i, interval_name=label,
                                  tenor_years=tenor, t_mid_years=mid)
                        for i, (label, tenor, mid) in enumerate(GRID, start=1))
        session.add_all(CalendarDay(calendar_date=date.fromisoformat(d),
                                    is_working_day=d != WEEKEND, is_trading_day=d != WEEKEND)
                        for d in (D1, D2, WEEKEND))
        session.commit()

    class MoexFixture:
        def fetch_curve(self, requested_date):
            return [{"tradedate": requested_date.isoformat(), "tradetime": "18:55:00",
                     "period": t, "value": 12 + t / 10 + (requested_date.day - 19) * 0.5}
                    for t in EXPECTED_TENORS]

    def get_test_db():
        with db.connect() as conn:
            yield conn

    monkeypatch.setattr(curve_parser, "MoexClient", lambda **_: MoexFixture())
    monkeypatch.setattr(curve_parser, "engine", db)
    monkeypatch.setenv("CURVES_INGEST_DATABASE_URL", db_url)
    monkeypatch.setitem(app.dependency_overrides, get_db, get_test_db)
    outer = FastAPI()
    outer.mount("/api", app)
    with TestClient(outer) as client:
        yield client, db
    curve_parser.writer_repository(db_url).engine.dispose()
    curve_parser.writer_repository.cache_clear()
    db.dispose()


def test_pipeline_publishes_both_dates_for_factor_lab(provider):
    client, db = provider
    base = "/api/v1"
    assert client.get(f"{base}/ready").json() == {"status": "ok", "storage": "reachable"}
    bounds = {"from": D1, "to": WEEKEND}
    assert client.get(f"{base}/curves", params=bounds).json()["dates"] == []
    assert client.get(f"{base}/curves/{D1}").status_code == 404

    response = client.post(f"{base}/curves/ingest", json={**bounds, "refresh": False})
    assert response.status_code == 200, response.text
    assert [r["status"] for r in response.json()["dates"]] == ["stored", "stored", "no_data"]
    assert client.get(f"{base}/curves", params=bounds).json()["dates"] == [D1, D2]
    assert client.post(f"{base}/curves/ingest", json={"from": D1, "to": D2}).json()["unchanged"] == 2
    with Session(db) as session:
        assert session.scalar(select(func.count()).select_from(CurveRun)) == 3

    snapshots = [client.get(f"{base}/curves/{d}").json() for d in (D1, D2)]
    for date_, snapshot in zip((D1, D2), snapshots, strict=True):
        assert snapshot["date"] == date_
        assert [p["tenor_years"] for p in snapshot["tenors"]] == [row[2] for row in GRID]
        assert all(tuple(s["scenario"] for s in p["scenarios"]) == SCENARIO_CODES
                   for p in snapshot["tenors"])
        assert snapshot["tenors"][0]["base_rate"] == pytest.approx((12.025 + (date_ == D2) * 0.5) / 100)
        # Reapplying the same shocks should reproduce the stored rounded rates.
        points = [{k: p[k] for k in ("tenor_years", "base_rate")} for p in snapshot["tenors"]]
        calculated = client.post(f"{base}/curves/shock", json={"tenors": points}).json()["tenors"]
        for actual, stored in zip(calculated, snapshot["tenors"], strict=True):
            assert [s["rate"] for s in actual["scenarios"]] == pytest.approx(
                [s["rate"] for s in stored["scenarios"]], abs=1e-6
            )

    assert len(client.get("/api/curves", params={"date": D2}).json()) == 133
    for format_ in ("csv", "xlsx"):
        assert client.get("/api/curves/export", params={"date": D2, "format": format_}).status_code == 200


def test_write_route_is_opt_in_and_range_is_bounded(provider, monkeypatch):
    client, _ = provider
    url = "/api/v1/curves/ingest"
    assert client.post(url, json={"from": "2026-01-01", "to": D1}).status_code == 422
    assert client.post(url, json={"from": D1, "to": D2, "refresh": True}).status_code == 422
    monkeypatch.delenv("CURVES_INGEST_DATABASE_URL")
    assert client.post(url, json={"from": D1, "to": D2}).status_code == 503


def test_shock_rejects_invalid_points(provider):
    client, _ = provider
    url = "/api/v1/curves/shock"
    bad = {"tenor_years": 0, "base_rate": 0.08}
    valid = {"tenor_years": 1, "base_rate": 0.08}
    assert client.post(url, json={"tenors": [bad]}).status_code == 422
    assert client.post(url, json={"tenors": [valid, valid]}).status_code == 422
