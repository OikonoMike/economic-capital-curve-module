#!/usr/bin/env python3
"""
Калькулятор кривых: читает moex_raw, считает curve_point, регистрирует запуск в curve_run.
Использует функции Александра из src/interpolate_curve.py.
"""

import sys
import os
from datetime import date, datetime, timezone
from decimal import Decimal

# Добавляем src в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from src.moex_loader.database import create_db_engine
from src.interpolate_curve import calculate_curves, to_long_format

def get_last_successful_date(engine):
    """Находит последнюю дату с успешным запуском, где есть данные в moex_raw."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT cr.report_date
            FROM curve_run cr
            JOIN moex_raw mr ON cr.run_id = mr.run_id
            WHERE cr.status = 'success'
            ORDER BY cr.report_date DESC
            LIMIT 1
        """))
        row = result.fetchone()
        return row[0] if row else None


def get_moex_points(engine, report_date):
    """Читает сырые точки MOEX за дату, сортирует по tenor_years."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT mr.tenor_years, mr.rate_pct
            FROM moex_raw mr
            JOIN curve_run cr ON mr.run_id = cr.run_id
            WHERE cr.report_date = :date AND cr.status = 'success'
            ORDER BY mr.tenor_years
        """), {"date": report_date})
        return [(float(row[0]), float(row[1])) for row in result]


def get_run_id(engine, report_date):
    """Находит существующий run_id за дату. Если нет — создаёт."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT run_id FROM curve_run
            WHERE report_date = :date AND status = 'success'
            ORDER BY run_id DESC LIMIT 1
        """), {"date": report_date})
        row = result.fetchone()
        if row:
            print(f"  Найден существующий run_id={row[0]}")
            return row[0]
        
        # Если нет — создаём (на случай, если загрузчик не сработал)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = conn.execute(text("""
            INSERT INTO curve_run (report_date, run_type, started_at, finished_at, status, started_by)
            VALUES (:date, 'scheduled', :started, :finished, 'success', :by)
            RETURNING run_id
        """), {
            "date": report_date,
            "started": now,
            "finished": now,
            "by": "calculator",
        })
        run_id = result.scalar()
        print(f"  Создан новый run_id={run_id}")
        return run_id


def save_curve_points(engine, run_id, report_date, long_df):
    """Записывает 133 строки в curve_point."""
    with engine.begin() as conn:
        for _, row in long_df.iterrows():
            method_en = row['method']
            conn.execute(text("""
                INSERT INTO curve_point 
                (run_id, report_date, scenario_id, tenor_label, tenor_years, t_mid_years,
                 rate_pct, discount_factor, method, is_interpolated, is_extrapolated)
                VALUES 
                (:run_id, :date, :scen, :tenor_label, :tenor_years, :t_mid,
                 :rate, :df, :method, :is_interp, :is_extrap)
                ON CONFLICT (run_id, scenario_id, tenor_label) DO NOTHING
            """), {
                "run_id": run_id,
                "date": report_date,
                "scen": int(row['scenario_id']),
                "tenor_label": row['tenor_label'],
                "tenor_years": float(row['tenor_years']),
                "t_mid": float(row['t_mid_years']),
                "rate": float(row['rate_pct']),
                "df": float(row['discount_factor']),
                "method": method_en,
                "is_interp": bool(row['is_interpolated']),
                "is_extrap": bool(row['is_extrapolated']),
            })


def process_date(engine, report_date):
    """Обрабатывает одну дату: читает moex_raw, считает, пишет в curve_point."""
    print(f"Обработка {report_date}...")
    
    points = get_moex_points(engine, report_date)
    if not points:
        print(f"  Нет данных в moex_raw для {report_date}, пропускаем.")
        return False
    
    print(f"  Получено {len(points)} точек из moex_raw")
    
    # Считаем кривые (функция Александра)
    wide_df = calculate_curves(points)
    long_df = to_long_format(wide_df)
    
    print(f"  Рассчитано {len(long_df)} строк (19 теноров × 7 сценариев)")
    
    # Регистрируем запуск
    run_id = get_run_id(engine, report_date)
    print(f"  Создан запуск run_id={run_id}")
    
    # Сохраняем результаты
    save_curve_points(engine, run_id, report_date, long_df)
    print(f"  Сохранено в curve_point")
    
    return True


def main():
    load_dotenv()
    engine = create_db_engine()
    
    # Если передана дата — обрабатываем её, иначе берём последнюю успешную
    if len(sys.argv) > 1:
        target_date = date.fromisoformat(sys.argv[1])
        process_date(engine, target_date)
    else:
        # Обрабатываем все даты с успешными запусками, где ещё нет curve_point
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT cr.report_date
                FROM curve_run cr
                WHERE cr.status = 'success'
                  AND cr.run_id NOT IN (SELECT DISTINCT run_id FROM curve_point)
                ORDER BY cr.report_date
            """))
            dates = [row[0] for row in result]
        
        if not dates:
            print("Нет дат для обработки.")
            return
        
        print(f"Найдено {len(dates)} дат для обработки: {dates}")
        
        for d in dates:
            process_date(engine, d)
    
    print("Готово!")


if __name__ == "__main__":
    main()
