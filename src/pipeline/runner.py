"""Единый pipeline загрузки MOEX и расчёта кривых."""

import logging
from datetime import date
from typing import Optional

from src.interpolate_curve import calculate_curves, to_long_format
from src.moex_loader.database import CurveRepository
from src.moex_loader.loader import CurveLoader

logger = logging.getLogger(__name__)


def run_for_date(
    requested_date: date,
    mode: str = "manual",
    loader: Optional[CurveLoader] = None,
    repository: Optional[CurveRepository] = None,
) -> str:
    """Загружает данные MOEX, рассчитывает кривые и сохраняет результат.

    Все данные одного запуска связываются через единый run_id.
    Возвращает конечный статус: success, skipped, no_data или error.
    """
    if mode not in {"manual", "scheduled"}:
        raise ValueError("mode должен быть 'manual' или 'scheduled'.")

    if loader is None or repository is None:
        raise ValueError(
            "Необходимо передать loader и repository."
        )

    with repository.lock_pipeline_date(requested_date):
        return _run_for_date(requested_date, mode, loader, repository)


def _run_for_date(
    requested_date: date, mode: str, loader: CurveLoader, repository: CurveRepository
) -> str:
    # Проверяем календарь до создания запуска.
    if not repository.is_trading_day(requested_date):
        repository.create_run(
            requested_date=requested_date,
            mode=mode,
            started_by=loader.started_by,
            status="skipped",
            error_message="нерабочий день по календарю",
        )
        logger.info("%s: нерабочий день, pipeline пропущен.", requested_date)
        return "skipped"

    # Не запускаем повторный расчёт уже успешно обработанной даты.
    if repository.has_successful_run(requested_date):
        logger.info("%s: уже обработана, пропускаем.", requested_date)
        return "skipped"

    run_id = repository.create_run(
        requested_date=requested_date,
        mode=mode,
        started_by=loader.started_by,
    )

    logger.info(
        "Запуск pipeline: date=%s, run_id=%s, mode=%s",
        requested_date,
        run_id,
        mode,
    )

    # Этап 1. Загрузка и проверка исходных данных.
    status, error_message = loader.load_for_run(requested_date, run_id)

    if status != "success":
        repository.finish_run(
            run_id,
            status,
            error_message=error_message,
        )
        return status

    # Этап 2. Расчёт и сохранение кривых.
    try:
        moex_points = repository.get_moex_points(run_id)

        if not moex_points:
            message = "После загрузки отсутствуют исходные точки MOEX."
            repository.finish_run(
                run_id,
                "no_data",
                error_message=message,
            )
            return "no_data"

        wide_df = calculate_curves(moex_points)
        long_df = to_long_format(wide_df)

        inserted_count = repository.save_curve_points(
            run_id=run_id,
            requested_date=requested_date,
            long_df=long_df,
        )

        repository.finish_run(run_id, "success")

        logger.info(
            "Pipeline завершён: date=%s, run_id=%s, "
            "рассчитано точек=%s, новых записей=%s",
            requested_date,
            run_id,
            len(long_df),
            inserted_count,
        )
        return "success"

    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        logger.exception(
            "Ошибка расчёта кривых за %s (run_id=%s).",
            requested_date,
            run_id,
        )
        repository.finish_run(
            run_id,
            "error",
            error_message=message,
        )
        return "error"
