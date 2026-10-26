"""Клиент для получения кривой доходности с MOEX ISS API."""

from datetime import date
from typing import Any

import requests


MOEX_URL = "https://iss.moex.com/iss/engines/stock/zcyc.json"
DEFAULT_TIMEOUT = 20


class MoexClientError(Exception):
    """Базовая ошибка клиента MOEX."""


class MoexNoDataError(MoexClientError):
    """MOEX не вернула точки кривой за запрошенную дату."""


class MoexClient:
    """Получает точки кривой доходности государственных облигаций с MOEX."""

    def __init__(
        self,
        base_url: str = MOEX_URL,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Таймаут должен быть положительным числом.")

        self.base_url = base_url
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_curve(self, requested_date: date) -> list[dict[str, Any]]:
        """
        Получает кривую доходности за указанную дату.

        Возвращает список словарей с полями:
        tradedate, tradetime, period, value.

        Если данных нет, выбрасывает MoexNoDataError.
        Если произошла ошибка HTTP или формат ответа некорректен,
        выбрасывает MoexClientError.
        """
        try:
            response = self.session.get(
                self.base_url,
                params={"date": requested_date.isoformat()},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise MoexClientError(
                f"Ошибка запроса к MOEX за {requested_date}: {exc}"
            ) from exc
        except ValueError as exc:
            raise MoexClientError(
                f"MOEX вернула некорректный JSON за {requested_date}."
            ) from exc

        if not isinstance(payload, dict):
            raise MoexClientError("Ожидался JSON-объект от MOEX.")

        block = payload.get("yearyields")
        if not isinstance(block, dict):
            raise MoexClientError(
                "В ответе MOEX отсутствует блок yearyields."
            )

        columns = block.get("columns")
        rows = block.get("data")

        if not isinstance(columns, list) or not isinstance(rows, list):
            raise MoexClientError(
                "Блок yearyields имеет некорректную структуру."
            )

        required_columns = {"tradedate", "tradetime", "period", "value"}
        if not required_columns.issubset(columns):
            raise MoexClientError(
                "В блоке yearyields отсутствуют необходимые столбцы."
            )

        records: list[dict[str, Any]] = []

        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise MoexClientError(
                    "MOEX вернула строку с некорректным количеством полей."
                )

            record = dict(zip(columns, row))

            if record["tradedate"] != requested_date.isoformat():
                raise MoexClientError(
                    "Дата данных MOEX не совпадает с запрошенной: "
                    f"{record['tradedate']} вместо {requested_date}."
                )

            if record["period"] is None or record["value"] is None:
                raise MoexClientError(
                    "MOEX вернула точку кривой без срока или доходности."
                )

            records.append(record)

        if not records:
            raise MoexNoDataError(
                f"MOEX не вернула данных за {requested_date}."
            )

        return records