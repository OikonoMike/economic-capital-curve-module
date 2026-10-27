import pandas as pd
import numpy as np
import os

# Параметры рубля (из readme.md)
D_PAR = 4.0
S_K_S = 5.0
S_D_S = 3.0
T_SWITCH = 4.0

# Сетка теноров: (метка, срок в годах, T - середина интервала)
GRID = [
    ('1d', 0.0027, 0.0028), ('1m', 0.0833, 0.0417), ('3m', 0.25, 0.1667), ('6m', 0.5, 0.375),
    ('9m', 0.75, 0.625), ('1y', 1, 0.875), ('1.5y', 1.5, 1.25), ('2y', 2, 1.75),
    ('3y', 3, 2.5), ('4y', 4, 3.5), ('5y', 5, 4.5), ('6y', 6, 5.5), ('7y', 7, 6.5),
    ('8y', 8, 7.5), ('9y', 9, 8.5), ('10y', 10, 9.5), ('15y', 15, 12.5),
    ('20y', 20, 17.5), ('30y', 30, 25),
]

def get_base_rate(tenor, x_moex, y_moex):
    """Возвращает (ставка, метод) для тенора на основе точек MOEX."""
    if tenor < x_moex[0]:
        return y_moex[0], 'Ближайшее значение'
    if tenor > x_moex[-1]:
        slope = (y_moex[-1] - y_moex[-2]) / (x_moex[-1] - x_moex[-2])
        return y_moex[-1] + slope * (tenor - x_moex[-1]), 'Экстраполяция'
    if tenor in x_moex:
        return y_moex[x_moex.index(tenor)], 'Значение MOEX'
    return float(np.interp(tenor, x_moex, y_moex)), 'Интерполяция'

def read_moex_csv(filepath):
    """Читает сырой файл MOEX (zcyc) и возвращает отфильтрованный список точек."""
    raw = pd.read_csv(filepath, sep=';', header=1, decimal=',')
    cols = [c for c in raw.columns if c.startswith('period_')]
    points_raw = sorted((float(c.split('_')[1]), float(raw.loc[0, c])) for c in cols)
    # Берем точки до 20 лет (30-летний тенор будет экстраполироваться)
    return [p for p in points_raw if p[0] <= 20]

def calculate_curves(moex_points: list, output_path: str) -> pd.DataFrame:
    """
    Считает базовую кривую, 6 сценариев и DF.
    Возвращает широкую таблицу (19 строк) и сохраняет в Excel.
    """
    x_moex = [p[0] for p in moex_points]
    y_moex = [p[1] for p in moex_points]
    
    result_rows = []
    for label, tenor, t_mid in GRID:
        base, method = get_base_rate(tenor, x_moex, y_moex)
        
        # Экспоненциальное затухание (EXP(-T/t))
        exp_term = np.exp(-t_mid / T_SWITCH)
        
        # Формулы сценариев
        s1 = base + D_PAR
        s2 = base - D_PAR
        s3 = base - 0.65 * S_K_S * exp_term + 0.9 * S_D_S * (1 - exp_term)
        s4 = base + 0.8 * S_K_S * exp_term - 0.6 * S_D_S * (1 - exp_term)
        s5 = base + S_K_S * exp_term
        s6 = base - S_K_S * exp_term
        
        # Коэффициенты дисконтирования DF = (1+r)^(-T)
        def calc_df(rate_pct):
            r = rate_pct / 100.0
            return round((1 + r) ** (-t_mid), 6) if r > -1 else np.nan
        
        result_rows.append({
            'тенор': label,
            'срок_лет': tenor,
            'T_середина': t_mid,
            'метод': method,
            'is_interpolated': int(method == 'Интерполяция'),
            'is_extrapolated': int(method == 'Экстраполяция'),
            
            'Ставка_БС': round(base, 4),
            'DF_БС': calc_df(base),
            
            'Ставка_С1': round(s1, 4),
            'DF_С1': calc_df(s1),
            
            'Ставка_С2': round(s2, 4),
            'DF_С2': calc_df(s2),
            
            'Ставка_С3': round(s3, 4),
            'DF_С3': calc_df(s3),
            
            'Ставка_С4': round(s4, 4),
            'DF_С4': calc_df(s4),
            
            'Ставка_С5': round(s5, 4),
            'DF_С5': calc_df(s5),
            
            'Ставка_С6': round(s6, 4),
            'DF_С6': calc_df(s6),
        })
            
    df = pd.DataFrame(result_rows)
    # Сортируем по порядку теноров
    order = [row[0] for row in GRID]
    df['тенор'] = pd.Categorical(df['тенор'], categories=order, ordered=True)
    
    # Создаем папку, если её нет
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_excel(output_path, index=False)
    
    return df

if __name__ == "__main__":
    input_file = 'data/gcurve_2026-07-31_moex.csv'
    output_file = 'data/curves_with_scenarios_and_df.xlsx'
    
    try:
        points = read_moex_csv(input_file)
        df = calculate_curves(points, output_file)
        print(f"Расчет завершен. Файл сохранен: {output_file}")
        print(df[['тенор', 'Ставка_БС', 'Ставка_С3']].head())
    except FileNotFoundError:
        print(f"Ошибка: Файл {input_file} не найден. Проверьте путь.")
