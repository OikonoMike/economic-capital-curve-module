import pandas as pd
import numpy as np

# Параметры
D_PAR = 4.0
S_K_S = 5.0
S_D_S = 3.0
T_SWITCH = 4.0

GRID = [
    ('1d', 0.0027, 0.0028), ('1m', 0.0833, 0.0417), ('3m', 0.25, 0.1667), ('6m', 0.5, 0.375),
    ('9m', 0.75, 0.625), ('1y', 1, 0.875), ('1.5y', 1.5, 1.25), ('2y', 2, 1.75),
    ('3y', 3, 2.5), ('4y', 4, 3.5), ('5y', 5, 4.5), ('6y', 6, 5.5), ('7y', 7, 6.5),
    ('8y', 8, 7.5), ('9y', 9, 8.5), ('10y', 10, 9.5), ('15y', 15, 12.5),
    ('20y', 20, 17.5), ('30y', 30, 25),
]

def get_base_rate(tenor, x_moex, y_moex):
    if tenor < x_moex[0]:
        return y_moex[0], 'Ближайшее значение'
    if tenor > x_moex[-1]:
        slope = (y_moex[-1] - y_moex[-2]) / (x_moex[-1] - x_moex[-2])
        return y_moex[-1] + slope * (tenor - x_moex[-1]), 'Экстраполяция'
    if tenor in x_moex:
        return y_moex[x_moex.index(tenor)], 'Значение MOEX'
    return float(np.interp(tenor, x_moex, y_moex)), 'Интерполяция'

# Разделенные рассчет и сохранение
def calculate_curves(moex_points: list) -> pd.DataFrame:
    """Считает базовую кривую, сценарии и DF. Возвращает таблицу (19 строк)."""
    x_moex = [p[0] for p in moex_points]
    y_moex = [p[1] for p in moex_points]
    
    result_rows = []
    for label, tenor, t_mid in GRID:
        base, method = get_base_rate(tenor, x_moex, y_moex)
        exp_term = np.exp(-t_mid / T_SWITCH)
        
        s1 = base + D_PAR
        s2 = base - D_PAR
        s3 = base - 0.65 * S_K_S * exp_term + 0.9 * S_D_S * (1 - exp_term)
        s4 = base + 0.8 * S_K_S * exp_term - 0.6 * S_D_S * (1 - exp_term)
        s5 = base + S_K_S * exp_term
        s6 = base - S_K_S * exp_term
        
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
            'Ставка_БС': round(base, 4), 'DF_БС': calc_df(base),
            'Ставка_С1': round(s1, 4), 'DF_С1': calc_df(s1),
            'Ставка_С2': round(s2, 4), 'DF_С2': calc_df(s2),
            'Ставка_С3': round(s3, 4), 'DF_С3': calc_df(s3),
            'Ставка_С4': round(s4, 4), 'DF_С4': calc_df(s4),
            'Ставка_С5': round(s5, 4), 'DF_С5': calc_df(s5),
            'Ставка_С6': round(s6, 4), 'DF_С6': calc_df(s6),
        })
            
    df = pd.DataFrame(result_rows)
    order = [row[0] for row in GRID]
    df['тенор'] = pd.Categorical(df['тенор'], categories=order, ordered=True)
    return df

# Функция для "длинного" формата (19 * 7 = 133 строки)
def to_long_format(wide_df: pd.DataFrame) -> pd.DataFrame:
    """
    Переводит широкую таблицу в длинный формат.
    Схема: scenario_id (0-6), tenor_label, tenor_years, t_mid_years, rate_pct, discount_factor, method, is_interpolated, is_extrapolated
    """
    long_rows = []
    
    # Маппинг сценариев
    scenarios = {
        'БС': 0, 'С1': 1, 'С2': 2, 'С3': 3, 'С4': 4, 'С5': 5, 'С6': 6
    }

    method_mapping = {
        'Значение MOEX': 'moex',
        'Ближайшее значение': 'nearest',
        'Интерполяция': 'interpolation',
        'Экстраполяция': 'extrapolation'
    }
    
    for _, row in wide_df.iterrows():
        for scen_name, scen_id in scenarios.items():
            long_rows.append({
                'scenario_id': scen_id,
                'tenor_label': row['тенор'],
                'tenor_years': row['срок_лет'],
                't_mid_years': row['T_середина'],
                'rate_pct': row[f'Ставка_{scen_name}'],
                'discount_factor': row[f'DF_{scen_name}'],
                'method': row['метод'],
                'is_interpolated': row['is_interpolated'],
                'is_extrapolated': row['is_extrapolated'],
            })
            
    return pd.DataFrame(long_rows)
