import pandas as pd
import numpy as np

# Сырые данные MOEX (файл zcyc: первая строка 'zcyc', вторая пустая, третья - заголовок)
raw = pd.read_csv('data/gcurve_2026-07-31_moex.csv', sep=';', skiprows=2, decimal=',')
cols = [c for c in raw.columns if c.startswith('period_')]
moex_tenors = [float(c.split('_')[1]) for c in cols]
moex_rates = raw.loc[0, cols].astype(float).tolist()

# Теноры методички ЦБ (Таблица 1, 19 точек)
cb_tenors = [0.0028, 0.0417, 0.1667, 0.375, 0.625, 0.875, 1.25, 1.75,
             2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 12.5, 17.5, 25.0]

# Линейная интерполяция внутри диапазона MOEX.
# За его пределами np.interp берёт ближайшее крайнее значение (как требует п. 3.2 8-МР).
cb_rates = np.interp(cb_tenors, moex_tenors, moex_rates)

df = pd.DataFrame({'срок_в_годах': cb_tenors, 'ставка': np.round(cb_rates, 4)})
df.to_csv('data/gcurve_2026-07-31.csv', index=False, sep=';')
df.to_excel('data/gcurve_2026-07-31.xlsx', index=False)

print(f"Получено {len(df)} теноров:")
print(df)