from datetime import date
from unittest.mock import Mock

import pytest

from src.moex_loader.loader import CurveLoader
from src.moex_loader.moex_client import (
    MoexClientError,
    MoexNoDataError,
)


SAMPLE_POINTS = [
    {
        "tradedate": "2026-10-23",
        "tradetime": "18:00:00",
        "period": 0.25,
        "value": 13.4726,
    }
]


@pytest.fixture
def client():
    return Mock()


@pytest.fixture
def repository():
    repo = Mock()
    repo.has_successful_run.return_value = False
    repo.create_run.return_value = 123

    # По умолчанию будние дни считаются торговыми,
    # суббота и воскресенье — нет.
    repo.is_trading_day.side_effect = lambda day: day.weekday() < 5

    return repo


@pytest.fixture
def loader(client, repository):
    return CurveLoader(
        client=client,
        repository=repository,
        retries=3,
        retry_pause=0,
        request_pause=0,
    )


def test_successful_load(loader, client, repository):
    client.fetch_curve.return_value = SAMPLE_POINTS
    repository.save_curve.return_value = 1

    result = loader.load_date(date(2026, 10, 23), mode="manual")

    assert result == "success"
    repository.create_run.assert_called_once_with(
        requested_date=date(2026, 10, 23),
        mode="manual",
        started_by="manual",
    )
    repository.save_curve.assert_called_once()
    repository.finish_run.assert_called_once_with(123, "success")


def test_successful_date_is_skipped(loader, client, repository):
    repository.has_successful_run.return_value = True

    result = loader.load_date(date(2026, 10, 23))

    assert result == "skipped"
    client.fetch_curve.assert_not_called()
    repository.create_run.assert_not_called()


def test_no_data_is_not_error(loader, client, repository):
    repository.is_trading_day.return_value = True
    repository.is_trading_day.side_effect = None
    client.fetch_curve.side_effect = MoexNoDataError("Данных нет")

    result = loader.load_date(date(2026, 10, 24))

    assert result == "no_data"
    repository.finish_run.assert_called_once_with(
        123,
        "no_data",
        error_message="Данных нет",
    )
    assert client.fetch_curve.call_count == 1


def test_retries_then_succeeds(loader, client, repository):
    client.fetch_curve.side_effect = [
        MoexClientError("Временная ошибка"),
        SAMPLE_POINTS,
    ]

    result = loader.load_date(date(2026, 10, 23))

    assert result == "success"
    assert client.fetch_curve.call_count == 2
    repository.finish_run.assert_called_once_with(123, "success")


def test_all_retries_fail(loader, client, repository):
    client.fetch_curve.side_effect = MoexClientError("Сервер недоступен")

    result = loader.load_date(date(2026, 10, 23))

    assert result == "error"
    assert client.fetch_curve.call_count == 3

    args, kwargs = repository.finish_run.call_args
    assert args[0] == 123
    assert args[1] == "error"
    assert "Сервер недоступен" in kwargs["error_message"]


def test_range_skips_weekends(loader, repository):
    # Пятница, суббота, воскресенье, понедельник.
    repository.is_trading_day.side_effect = lambda day: day.weekday() < 5
    loader.load_date = Mock(
        side_effect=lambda day, mode: (
            "skipped" if day.weekday() >= 5 else "success"
        )
    )

    result = loader.load_range(
        date(2026, 10, 23),
        date(2026, 10, 26),
    )

    assert result["success"] == 2
    assert result["skipped"] == 2
    assert loader.load_date.call_count == 4
def test_range_continues_after_error(loader, repository):
    repository.is_trading_day.side_effect = lambda day: True
    loader.load_date = Mock(
        side_effect=["error", "no_data", "success"]
    )

    result = loader.load_range(
        date(2026, 10, 26),
        date(2026, 10, 28),
    )

    assert result == {
        "success": 1,
        "no_data": 1,
        "error": 1,
        "skipped": 0,
    }
    assert loader.load_date.call_count == 3


def test_invalid_range_is_rejected(loader):
    with pytest.raises(ValueError):
        loader.load_range(
            date(2026, 10, 28),
            date(2026, 10, 26),
        )


def test_invalid_mode_is_rejected(loader):
    with pytest.raises(ValueError):
        loader.load_date(date(2026, 10, 23), mode="automatic")