import pandas as pd
import datetime
import os

DEFAULT_CALENDAR_PATH = 'data/calendar_2026-2027.csv'

def is_trading_day(check_date: datetime.date, calendar_path: str = DEFAULT_CALENDAR_PATH) -> bool:
    """
    Проверяет, является ли дата рабочим днем (днем торгов).
    """
    if not os.path.exists(calendar_path):
        raise FileNotFoundError(f"Файл календаря не найден: {calendar_path}")

    df = pd.read_csv(calendar_path, sep=';')
    date_str = check_date.strftime('%Y-%m-%d')
    row = df[df['date'] == date_str]
    
    if not row.empty:
        return bool(row.iloc[0]['is_working_day'])
    else:
        raise ValueError(f"Дата {date_str} отсутствует в календаре {calendar_path}")

def get_previous_trading_day(target_date: datetime.date, calendar_path: str = DEFAULT_CALENDAR_PATH) -> datetime.date:
    """
    Возвращает предыдущий рабочий день (для логики догрузки).
    """
    check_date = target_date - datetime.timedelta(days=1)
    
    while not is_trading_day(check_date, calendar_path):
        check_date -= datetime.timedelta(days=1)
        if (target_date - check_date).days > 30:
            raise ValueError("Не удалось найти рабочий день в пределах 30 дней назад.")
            
    return check_date
