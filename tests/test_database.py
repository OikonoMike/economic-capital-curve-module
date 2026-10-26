"""Тесты операций с базой данных"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.moex_loader.database import (
    Base,
    CurveRepository,
    CurveRun,
    MoexRaw,
)


@pytest.fixture
def repository():
    """Создаёт временную базу SQLite для каждого теста"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    yield CurveRepository(engine)

    engine.dispose()


def test_create_and_finish_run(repository):
    """Запуск создаётся и получает конечный статус"""
    requested_date = date(2026, 10, 23)

    run_id = repository.create_run(requested_date, "manual")
    repository.finish_run(run_id, "success")

    with Session(repository.engine) as session:
        run = session.get(CurveRun, run_id)

        assert run is not None
        assert run.report_date == requested_date
        assert run.run_type == "manual"
        assert run.started_by == "unknown"
        assert run.status == "success"
        assert run.finished_at is not None
        assert run.error_message is None


def test_successful_run_is_detected(repository):
    """Успешная загрузка отмечается как выполненная"""
    requested_date = date(2026, 10, 23)

    run_id = repository.create_run(requested_date, "manual")

    assert repository.has_successful_run(requested_date) is False

    repository.finish_run(run_id, "success")

    assert repository.has_successful_run(requested_date) is True


def test_no_data_is_not_success(repository):
    """Статус no_data не считается успешной загрузкой"""
    requested_date = date(2026, 10, 25)

    run_id = repository.create_run(requested_date, "manual")
    repository.finish_run(run_id, "no_data")

    assert repository.has_successful_run(requested_date) is False


def test_save_curve(repository):
    """Точки кривой сохраняются в таблицу moex_raw"""
    requested_date = date(2026, 10, 23)
    run_id = repository.create_run(requested_date, "manual")

    points = [
        {
            "tradedate": "2026-10-23",
            "tradetime": "18:54:59",
            "period": 0.25,
            "value": 13.4726,
        },
        {
            "tradedate": "2026-10-23",
            "tradetime": "18:54:59",
            "period": 0.5,
            "value": 13.7364,
        },
    ]

    inserted = repository.save_curve(run_id, requested_date, points)

    assert inserted == 2

    with Session(repository.engine) as session:
        rows = session.scalars(select(MoexRaw)).all()

        assert len(rows) == 2
        assert rows[0].tenor_years == 0.2500
        assert rows[0].rate_pct == Decimal("13.4726")
        assert rows[0].moex_tradetime.isoformat() == "18:54:59"
        assert rows[0].run_id == run_id


def test_duplicate_points_are_not_inserted(repository):
    """Повторная запись тех же точек не создаёт дубликаты"""
    requested_date = date(2026, 10, 23)
    run_id = repository.create_run(requested_date, "manual")

    points = [
        {
            "tradedate": "2026-10-23",
            "tradetime": "18:54:59",
            "period": 0.25,
            "value": 13.4726,
        }
    ]

    first_insert = repository.save_curve(run_id, requested_date, points)
    second_insert = repository.save_curve(run_id, requested_date, points)

    assert first_insert == 1
    assert second_insert == 0

    with Session(repository.engine) as session:
        rows = session.scalars(select(MoexRaw)).all()
        assert len(rows) == 1


def test_save_curve_rejects_wrong_date(repository):
    """Нельзя сохранить точку с другой датой"""
    requested_date = date(2026, 10, 23)
    run_id = repository.create_run(requested_date, "manual")

    points = [
        {
            "tradedate": "2026-10-22",
            "tradetime": "18:54:58",
            "period": 0.25,
            "value": 12.935,
        }
    ]

    with pytest.raises(ValueError, match="не совпадает"):
        repository.save_curve(run_id, requested_date, points)