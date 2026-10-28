"""Тесты клиента MOEX без реальных HTTP-запросов."""

from datetime import date
from unittest.mock import Mock

import pytest
import requests

from src.moex_loader.moex_client import (
    MoexClient,
    MoexClientError,
    MoexNoDataError,
)


REQUESTED_DATE = date(2026, 10, 23)


def make_response(payload: dict) -> Mock:
    """Создаёт имитацию успешного HTTP-ответа."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def make_payload(rows: list[list]) -> dict:
    """Создаёт JSON в формате, который мы получили от MOEX."""
    return {
        "yearyields": {
            "columns": ["tradedate", "tradetime", "period", "value"],
            "data": rows,
        }
    }


def test_fetch_curve_returns_points() -> None:
    """Клиент преобразует строки ответа в список словарей."""
    payload = make_payload(
        [
            ["2026-10-23", "18:54:59", 0.25, 13.4726],
            ["2026-10-23", "18:54:59", 0.5, 13.7364],
        ]
    )

    session = Mock(spec=requests.Session)
    session.get.return_value = make_response(payload)

    client = MoexClient(session=session)
    result = client.fetch_curve(REQUESTED_DATE)

    assert len(result) == 2
    assert result[0] == {
        "tradedate": "2026-10-23",
        "tradetime": "18:54:59",
        "period": 0.25,
        "value": 13.4726,
    }

    session.get.assert_called_once_with(
        "https://iss.moex.com/iss/engines/stock/zcyc.json",
        params={"date": "2026-10-23"},
        timeout=20,
    )


def test_fetch_curve_raises_no_data_error() -> None:
    """Пустой ответ означает отсутствие данных за дату."""
    session = Mock(spec=requests.Session)
    session.get.return_value = make_response(make_payload([]))

    client = MoexClient(session=session)

    with pytest.raises(MoexNoDataError):
        client.fetch_curve(REQUESTED_DATE)


def test_fetch_curve_raises_error_for_http_failure() -> None:
    """HTTP-ошибка преобразуется в ошибку клиента."""
    session = Mock(spec=requests.Session)
    session.get.side_effect = requests.Timeout("Превышено время ожидания")

    client = MoexClient(session=session)

    with pytest.raises(MoexClientError, match="Ошибка запроса к MOEX"):
        client.fetch_curve(REQUESTED_DATE)


def test_fetch_curve_raises_error_for_missing_block() -> None:
    """Ответ без yearyields считается некорректным."""
    session = Mock(spec=requests.Session)
    session.get.return_value = make_response({})

    client = MoexClient(session=session)

    with pytest.raises(MoexClientError, match="yearyields"):
        client.fetch_curve(REQUESTED_DATE)


def test_fetch_curve_rejects_wrong_date() -> None:
    """Клиент не должен возвращать данные за другую дату."""
    payload = make_payload(
        [["2026-10-22", "18:54:58", 0.25, 12.935]]
    )

    session = Mock(spec=requests.Session)
    session.get.return_value = make_response(payload)

    client = MoexClient(session=session)

    with pytest.raises(MoexClientError, match="не совпадает"):
        client.fetch_curve(REQUESTED_DATE)


def test_client_rejects_non_positive_timeout() -> None:
    """Таймаут должен быть положительным."""
    with pytest.raises(ValueError, match="Таймаут"):
        MoexClient(timeout=0)