"""
Клиент для отправки кривых в API калькулятора Команды 1.
Пока API не готов, используется заглушка.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class CalculatorClient:
    """Клиент для API калькулятора Команды 1"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        retries: int = 3,
        use_stub: bool = False,
    ):
        load_dotenv()
        self.base_url = base_url or os.getenv("CALCULATOR_API_URL")
        self.api_key = api_key or os.getenv("CALCULATOR_API_KEY")
        self.timeout = timeout
        self.retries = retries
        self.use_stub = use_stub or os.getenv("USE_CALCULATOR_STUB", "false").lower() == "true"

        if not self.base_url and not self.use_stub:
            raise ValueError("Не задан CALCULATOR_API_URL и не включён режим заглушки")

    def send_curves(
        self,
        run_id: int,
        report_date: str,
        curves_data: list[dict],
    ) -> dict:
        """
        Отправляет кривые в API калькулятора.
        
        Args:
            run_id: ID запуска
            report_date: Дата кривой (YYYY-MM-DD)
            curves_data: Список словарей с кривыми (19 теноров × 7 сценариев)
        
        Returns:
            dict с результатом: {'status': 'ok'/'error', 'response': ..., 'error': ...}
        """
        if self.use_stub:
            return self._stub_send(run_id, report_date, curves_data)

        payload = {
            "run_id": run_id,
            "report_date": report_date,
            "curves": curves_data,
        }

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        for attempt in range(1, self.retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/calculate",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return {
                    "status": "ok",
                    "response": response.json(),
                    "error": None,
                }
            except requests.exceptions.RequestException as e:
                if attempt == self.retries:
                    return {
                        "status": "error",
                        "response": None,
                        "error": f"{type(e).__name__}: {e}",
                    }
                logger.warning(
                    "Попытка %s/%s не удалась: %s", attempt, self.retries, e
                )

        return {"status": "error", "response": None, "error": "Неизвестная ошибка"}

    def _stub_send(self, run_id: int, report_date: str, curves_data: list) -> dict:
        """Заглушка для тестирования без реального API"""
        logger.info(
            "STUB: Отправка кривых за %s (run_id=%s), точек: %d",
            report_date, run_id, len(curves_data),
        )
        return {
            "status": "ok",
            "response": {
                "message": "Stub response",
                "run_id": run_id,
                "report_date": report_date,
                "curves_received": len(curves_data),
            },
            "error": None,
        }