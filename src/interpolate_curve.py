import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

# Теноры MOEX (из скачанного файла)
moex_tenors = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]

# Ставки MOEX на 31.07.2026 (из файла)
moex_rates = [13.59, 13.35, 13.42, 13.63, 14.58, 15.06, 15.42, 15.57, 15.69, 15.84, 15.95]

# Теноры методички ЦБ (Таблица 1, 19 точек)
cb_tenors = [0.0028, 0.0417, 0.1667, 0.375, 0.625, 0.875, 1.25, 1.75, 
             2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 12.5, 17.5, 25.0]

# Интерполяция (линейная)
# Для точек за пределами диапазона MOEX (0.0028, 0.0417, 0.1667 < 0.25 и 25 > 20)
# используем экстраполяцию крайними значениями
interp_func = interp1d(moex_tenors, moex_rates, kind='linear', 
                       fill_value='extrapolate')

cb_rates = interp_func(cb_tenors)

# Создаём DataFrame
df = pd.DataFrame({
    'срок_в_годах': cb_tenors,
    'ставка': cb_rates
})

# Сохраняем
df.to_csv('data/gcurve_2026-07-31.csv', index=False, sep=';')
df.to_excel('data/gcurve_2026-07-31.xlsx', index=False)

print("Интерполяция завершена!")
print(f"Получено {len(df)} теноров:")
print(df)