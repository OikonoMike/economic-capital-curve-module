import pandas as pd
import numpy as np

# Базовая кривая на 19 тенорах ЦБ (таблица 1 приложения к 8-МР).
# Логика совпадает с листом «базовая» в excel/IRRBB_Stress_Curves_new.xlsx.

# Сырые данные MOEX (файл zcyc: первая строка 'zcyc', вторая пустая, третья - заголовок)
raw = pd.read_csv('data/gcurve_2026-07-31_moex.csv', sep=';', skiprows=2, decimal=',')
cols = [c for c in raw.columns if c.startswith('period_')]
points = sorted((float(c.split('_')[1]), float(raw.loc[0, c])) for c in cols)

# Для расчёта используем точки MOEX до 20 лет. Тенор 30 лет получаем экстраполяцией
# (в Excel на листе MOEX тоже 11 точек, до 20 лет).
MAX_TENOR = 20
points = [p for p in points if p[0] <= MAX_TENOR]
x = [p[0] for p in points]
y = [p[1] for p in points]

# (метка тенора, тенор в годах, T - середина интервала из таблицы 1)
GRID = [
    ('1d', 0.0027, 0.0028), ('1m', 0.0833, 0.0417), ('3m', 0.25, 0.1667), ('6m', 0.5, 0.375),
    ('9m', 0.75, 0.625), ('1y', 1, 0.875), ('1.5y', 1.5, 1.25), ('2y', 2, 1.75),
    ('3y', 3, 2.5), ('4y', 4, 3.5), ('5y', 5, 4.5), ('6y', 6, 5.5), ('7y', 7, 6.5),
    ('8y', 8, 7.5), ('9y', 9, 8.5), ('10y', 10, 9.5), ('15y', 15, 12.5),
    ('20y', 20, 17.5), ('30y', 30, 25),
]


def base_rate(tenor):
    """Возвращает (ставка, метод) для тенора."""
    if tenor < x[0]:                       # короче первой точки MOEX - ближайшее значение
        return y[0], 'Ближайшее значение'
    if tenor > x[-1]:                      # длиннее последней точки - экстраполяция по двум последним
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        return y[-1] + slope * (tenor - x[-1]), 'Экстраполяция'
    if tenor in x:                         # тенор есть на MOEX - берём значение MOEX как есть
        return y[x.index(tenor)], 'Значение MOEX'
    return float(np.interp(tenor, x, y)), 'Интерполяция'


rows = []
for label, tenor, t_mid in GRID:
    rate, method = base_rate(tenor)
    rows.append({
        'тенор': label,
        'тенор_лет': tenor,
        'T_середина_интервала': t_mid,
        'ставка': round(rate, 4),
        'метод': method,
        'интерполировано': int(method == 'Интерполяция'),
        'экстраполировано': int(method == 'Экстраполяция'),
    })

df = pd.DataFrame(rows)
df.to_csv('data/gcurve_2026-07-31.csv', index=False, sep=';')
df.to_excel('data/gcurve_2026-07-31.xlsx', index=False)

print(f"Получено {len(df)} теноров:")
print(df)
