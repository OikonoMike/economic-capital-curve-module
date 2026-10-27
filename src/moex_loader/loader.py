"""Логика загрузки кривой MOEX и сохранения в PostgreSQL"""

import logging
import time
from datetime import date, timedelta
from typing import Any

from src.moex_loader.database import CurveRepository
from src.moex_loader.moex_client import (
    MoexClient,
    MoexClientError,
    MoexNoDataError,
)

logger = logging.getLogger(__name__)


class CurveLoader:
    """Загружает кривую за дату или диапазон дат"""

    def __init__(
        self,
        client: MoexClient,
        repository: CurveRepository,
        retries: int = 3,
        retry_pause: float = 2.0,
        request_pause: float = 1.0,
        started_by: str = "manual",
    ) -> None:
        if retries < 1:
            raise ValueError("retries должен быть не меньше 1.")
        if retry_pause < 0 or request_pause < 0:
            raise ValueError("Паузы не могут быть отрицательными.")
        if not started_by.strip():
            raise ValueError("started_by не должен быть пустым.")

        self.client = client
        self.repository = repository
        self.retries = retries
        self.retry_pause = retry_pause
        self.request_pause = request_pause
        self.started_by = started_by

    def load_date(self, requested_date: date, mode: str = "manual") -> str:
        """Загружает одну дату и возвращает конечный статус"""
        if mode not in {"manual", "scheduled"}:
            raise ValueError("mode должен быть 'manual' или 'scheduled'.")

        # Фиксируем пропуск загрузки для нерабочего дня
        if not self.repository.is_trading_day(requested_date):
            self.repository.create_run(
                requested_date=requested_date,
                mode=mode,
                started_by=self.started_by,
                status="skipped",
                error_message="нерабочий день по календарю",
            )
            logger.info(
                "%s: нерабочий день по календарю, загрузка пропущена.",
                requested_date,
            )
            return "skipped"

        if self.repository.has_successful_run(requested_date):
            logger.info("%s: уже загружена, пропускаем.", requested_date)
            return "skipped"

        run_id = self.repository.create_run(
            requested_date=requested_date,
            mode=mode,
            started_by=self.started_by,
        )
        logger.info(
            "Начинаем загрузку %s (mode=%s, run_id=%s).",
            requested_date,
            mode,
            run_id,
        )

        try:
            points = self._fetch_with_retries(requested_date)

            inserted_count = self.repository.save_curve(
                run_id=run_id,
                requested_date=requested_date,
                points=points,
            )

            self.repository.finish_run(run_id, "success")
            logger.info(
                "%s: успешно, получено точек: %s, добавлено новых: %s.",
                requested_date,
                len(points),
                inserted_count,
            )
            return "success"

        except MoexNoDataError as exc:
            message = str(exc)
            self.repository.finish_run(
                run_id,
                "no_data",
                error_message=message,
            )
            logger.info("%s: данных нет (%s).", requested_date, message)
            return "no_data"

        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            logger.exception("Ошибка загрузки за %s.", requested_date)

            try:
                self.repository.finish_run(
                    run_id,
                    "error",
                    error_message=message,
                )
            except Exception:
                logger.exception(
                    "Не удалось записать статус error для run_id=%s.",
                    run_id,
                )

            return "error"

    def _fetch_with_retries(
        self,
        requested_date: date,
    ) -> list[dict[str, Any]]:
        """Повторяет запрос при ошибках клиента MOEX"""
        for attempt in range(1, self.retries + 1):
            try:
                return self.client.fetch_curve(requested_date)

            except MoexNoDataError:
                raise

            except MoexClientError:
                if attempt == self.retries:
                    raise

                logger.warning(
                    "%s: ошибка запроса, попытка %s из %s. "
                    "Повтор через %.1f сек.",
                    requested_date,
                    attempt,
                    self.retries,
                    self.retry_pause,
                )
                time.sleep(self.retry_pause)

        raise RuntimeError("Не удалось получить данные MOEX.")

    def load_range(
            self,
            from_date: date,
            to_date: date,
            mode: str = "manual",
    ) -> dict[str, int]:
        """Загружает даты в диапазоне включительно."""
        if from_date > to_date:
            raise ValueError("--from-date не может быть позже --to-date.")

        results = {
            "success": 0,
            "no_data": 0,
            "error": 0,
            "skipped": 0,
        }

        current_date = from_date

        while current_date <= to_date:
            status = self.load_date(current_date, mode)
            results[status] += 1

            if current_date < to_date and self.request_pause > 0:
                time.sleep(self.request_pause)

            current_date += timedelta(days=1)

        logger.info("Обработка диапазона завершена: %s", results)
        return results