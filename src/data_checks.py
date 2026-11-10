"""
Проверки исходных данных MOEX перед записью в moex_raw.
Возвращают (status, details) для записи в data_check.
"""
from datetime import time, date
from typing import List, Tuple, Optional

# 11 сроков MOEX (в годах), которые должны быть в ответе
EXPECTED_TENORS = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]


def check_tenors(points: List[Tuple[float, float]]) -> Tuple[str, Optional[str]]:
    """1. Присутствуют все 11 сроков MOEX."""
    actual = sorted([p[0] for p in points])
    missing = [t for t in EXPECTED_TENORS if t not in actual]
    if missing:
        return 'error', f"Отсутствуют сроки: {missing}"
    return 'ok', f"Получено {len(points)} из 11 сроков"


def check_rates(points: List[Tuple[float, float]]) -> Tuple[str, Optional[str]]:
    """2. Все ставки — числа в диапазоне 0–50 %."""
    invalid = [(t, r) for t, r in points if r < 0 or r > 50]
    if invalid:
        return 'error', f"Ставки вне диапазона 0-50%: {invalid}"
    return 'ok', f"Все {len(points)} ставок в диапазоне 0-50%"


def check_tradetime(moex_tradetime: Optional[time]) -> Tuple[str, Optional[str]]:
    """3. Время среза MOEX не раньше 18:30. Если неизвестно — error."""
    if moex_tradetime is None:
        return 'error', "Время среза MOEX неизвестно"
    cutoff = time(18, 30)
    if moex_tradetime < cutoff:
        return 'error', f"Время среза {moex_tradetime} раньше 18:30"
    return 'ok', f"Время среза {moex_tradetime}"


def check_report_date(actual_date: date, requested_date: date) -> Tuple[str, Optional[str]]:
    """4. Дата данных MOEX совпадает с запрошенной отчётной датой."""
    if actual_date != requested_date:
        return 'error', f"Дата данных {actual_date} ≠ запрошенной {requested_date}"
    return 'ok', f"Дата {actual_date} совпадает с запрошенной"


def run_all_checks(
    points: List[Tuple[float, float]],
    moex_tradetime: Optional[time],
    actual_date: date,
    requested_date: date,
) -> dict:
    """
    Запускает все 4 проверки. Возвращает dict вида:
    {
        'tenors':     ('ok'/'error', details),
        'rates':      ('ok'/'error', details),
        'tradetime':  ('ok'/'error', details),
        'report_date':('ok'/'error', details),
        'all_ok': bool,
        'error_summary': str  # для curve_run.error_message
    }
    """
    results = {
        'tenors':      check_tenors(points),
        'rates':       check_rates(points),
        'tradetime':   check_tradetime(moex_tradetime),
        'report_date': check_report_date(actual_date, requested_date),
    }
    all_ok = all(s == 'ok' for s, _ in results.values())
    errors = [f"{code}: {details}" for code, (s, details) in results.items() if s == 'error']
    return {
        **results,
        'all_ok': all_ok,
        'error_summary': '; '.join(errors) if errors else None,
    }