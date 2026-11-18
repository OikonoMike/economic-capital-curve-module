from datetime import date
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.pipeline.runner import run_for_date


@pytest.fixture
def repository():
    repo = Mock()
    repo.is_trading_day.return_value = True
    repo.has_successful_run.return_value = False
    repo.create_run.return_value = 123
    repo.get_moex_points.return_value = [
        (0.25, 13.4),
        (0.5, 13.3),
    ]
    repo.save_curve_points.return_value = 133
    return repo


@pytest.fixture
def loader(repository):
    obj = Mock()
    obj.repository = repository
    obj.started_by = "manual"
    return obj


def test_pipeline_success(repository, loader):
    loader.load_for_run.return_value = ("success", None)

    wide_df = pd.DataFrame({"test": [1]})
    long_df = pd.DataFrame({"test": [1]})

    with patch(
        "src.pipeline.runner.calculate_curves",
        return_value=wide_df,
    ) as calculate, patch(
        "src.pipeline.runner.to_long_format",
        return_value=long_df,
    ):
        result = run_for_date(
            date(2026, 10, 23),
            loader=loader,
            repository=repository,
        )

    assert result == "success"
    loader.load_for_run.assert_called_once_with(date(2026, 10, 23), 123)
    calculate.assert_called_once_with(repository.get_moex_points.return_value)
    repository.save_curve_points.assert_called_once()
    repository.finish_run.assert_called_once_with(123, "success")


def test_pipeline_non_working_day(repository, loader):
    repository.is_trading_day.return_value = False

    result = run_for_date(
        date(2026, 10, 24),
        loader=loader,
        repository=repository,
    )

    assert result == "skipped"
    loader.load_for_run.assert_not_called()
    repository.create_run.assert_called_once()
    repository.finish_run.assert_not_called()


def test_pipeline_no_data(repository, loader):
    loader.load_for_run.return_value = ("no_data", "Данных нет")

    with patch("src.pipeline.runner.calculate_curves") as calculate:
        result = run_for_date(
            date(2026, 10, 23),
            loader=loader,
            repository=repository,
        )

    assert result == "no_data"
    calculate.assert_not_called()
    repository.save_curve_points.assert_not_called()
    repository.finish_run.assert_called_once_with(
        123,
        "no_data",
        error_message="Данных нет",
    )


def test_pipeline_moex_error(repository, loader):
    loader.load_for_run.return_value = (
        "error",
        "MoexClientError: Сервер недоступен",
    )

    with patch("src.pipeline.runner.calculate_curves") as calculate:
        result = run_for_date(
            date(2026, 10, 23),
            loader=loader,
            repository=repository,
        )

    assert result == "error"
    calculate.assert_not_called()
    repository.save_curve_points.assert_not_called()
    repository.finish_run.assert_called_once_with(
        123,
        "error",
        error_message="MoexClientError: Сервер недоступен",
    )


def test_pipeline_calculation_error(repository, loader):
    loader.load_for_run.return_value = ("success", None)

    with patch(
        "src.pipeline.runner.calculate_curves",
        side_effect=ValueError("Ошибка расчёта"),
    ):
        result = run_for_date(
            date(2026, 10, 23),
            loader=loader,
            repository=repository,
        )

    assert result == "error"
    repository.save_curve_points.assert_not_called()

    args, kwargs = repository.finish_run.call_args
    assert args == (123, "error")
    assert "Ошибка расчёта" in kwargs["error_message"]