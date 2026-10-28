import pandas as pd
from sqlalchemy.orm import Session

from src.moex_loader.database import create_db_engine, CalendarDay


def load_calendar_from_csv(csv_path: str = 'data/calendar_2026-2027.csv'):
    print(f"Загрузка календаря из {csv_path}...")
    
    engine = create_db_engine()
    
    df = pd.read_csv(csv_path, sep=';')

    df = df.rename(columns={
        'date': 'calendar_date',
        'comment': 'note'
    })
    
    df['is_trading_day'] = df['is_working_day']
    
    df['calendar_date'] = pd.to_datetime(df['calendar_date']).dt.date
    df['is_working_day'] = df['is_working_day'].astype(bool)
    df['is_trading_day'] = df['is_trading_day'].astype(bool)

    inserted = 0
    updated = 0
    
    with Session(engine) as session:
        for _, row in df.iterrows():
            existing_day = session.get(CalendarDay, row['calendar_date'])
            
            if existing_day:
                existing_day.is_working_day = row['is_working_day']
                existing_day.is_trading_day = row['is_trading_day']
                existing_day.note = row['note']
                updated += 1
            else:
                new_day = CalendarDay(
                    calendar_date=row['calendar_date'],
                    is_working_day=row['is_working_day'],
                    is_trading_day=row['is_trading_day'],
                    note=row['note']
                )
                session.add(new_day)
                inserted += 1
                
        session.commit()
        
    print(f"Добавлено новых записей: {inserted}. Обновлено существующих: {updated}.")

if __name__ == "__main__":
    load_calendar_from_csv()
