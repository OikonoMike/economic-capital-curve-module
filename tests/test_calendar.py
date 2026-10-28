import pytest
import datetime
from src.calendar_checker import is_trading_day, get_previous_trading_day

def test_weekend_24_25_october_2026():
    """ТЕСТ ИЗ ТЗ: проверка выходных дней 24 и 25 октября 2026."""
    saturday = datetime.date(2026, 10, 24)
    sunday = datetime.date(2026, 10, 25)
    
    assert is_trading_day(saturday) is False
    assert is_trading_day(sunday) is False

def test_regular_working_day():
    """Проверка обычного рабочего дня (среда)."""
    wednesday = datetime.date(2026, 10, 21)
    assert is_trading_day(wednesday) is True

def test_holidays():
    """Проверка праздничных дней."""
    new_year = datetime.date(2026, 1, 1)
    assert is_trading_day(new_year) is False

def test_working_saturday():
    """Проверка перенесенной рабочей субботы (20 февраля 2027)."""
    working_sat = datetime.date(2027, 2, 20)
    assert is_trading_day(working_sat) is True

def test_get_previous_trading_day_from_monday():
    """Проверка логики догрузки: если сегодня понедельник, прошлый день - пятница."""
    monday = datetime.date(2026, 10, 26)
    expected_friday = datetime.date(2026, 10, 23)
    assert get_previous_trading_day(monday) == expected_friday

def test_date_out_of_bounds():
    """Проверка ошибки, если даты нет в календаре (например, 2030 год)."""
    future_date = datetime.date(2030, 1, 1)
    with pytest.raises(ValueError, match="отсутствует в календаре"):
        is_trading_day(future_date)
